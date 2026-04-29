use std::collections::{HashMap, VecDeque};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use async_trait::async_trait;
use axum::extract::State;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use serde::Serialize;
use serde_json::{Map, Value};
use thiserror::Error;
use tokio::net::TcpListener;
use tokio::sync::{Mutex, RwLock, broadcast};
use tracing::{info, warn};
use tracing_subscriber::{EnvFilter, fmt};

use ast_core::{StrategyProfile};

#[derive(Debug, Error)]
pub enum ObserveError {
    #[error("invalid log filter: {0}")]
    InvalidFilter(String),
    #[error("http server failed: {0}")]
    Http(String),
}

#[async_trait]
pub trait TelemetrySink: Send + Sync {
    async fn record_event(&self, event: &str);
    async fn record_metric(&self, metric: &str, value: u64);
    async fn record_error(&self, scope: &str, message: &str);
}

#[derive(Debug, Default)]
pub struct NoopTelemetry;

#[async_trait]
impl TelemetrySink for NoopTelemetry {
    async fn record_event(&self, event: &str) {
        info!(event, "telemetry event");
    }

    async fn record_metric(&self, metric: &str, value: u64) {
        info!(metric, value, "telemetry metric");
    }

    async fn record_error(&self, scope: &str, message: &str) {
        info!(scope, message, "telemetry error");
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AgentEvent {
    pub strategy: String,
    pub agent: String,
    pub action: String,
    pub summary: String,
    pub data: Value,
    pub timestamp: u64,
}

impl AgentEvent {
    pub fn report_in(
        strategy: impl Into<String>,
        agent: impl Into<String>,
        summary: impl Into<String>,
    ) -> Self {
        Self {
            strategy: strategy.into(),
            agent: agent.into(),
            action: "report_in".to_owned(),
            summary: summary.into(),
            data: Value::Object(Map::new()),
            timestamp: timestamp_ms(),
        }
    }

    pub fn action(
        strategy: impl Into<String>,
        agent: impl Into<String>,
        action: impl Into<String>,
        summary: impl Into<String>,
        data: impl Serialize,
    ) -> Self {
        Self {
            strategy: strategy.into(),
            agent: agent.into(),
            action: action.into(),
            summary: summary.into(),
            data: to_value(data),
            timestamp: timestamp_ms(),
        }
    }

    pub fn error(
        strategy: impl Into<String>,
        agent: impl Into<String>,
        message: impl Into<String>,
    ) -> Self {
        let message = message.into();
        let mut data = Map::new();
        data.insert("message".to_owned(), Value::String(message.clone()));

        Self {
            strategy: strategy.into(),
            agent: agent.into(),
            action: "error".to_owned(),
            summary: format!("Error: {message}"),
            data: Value::Object(data),
            timestamp: timestamp_ms(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct EventBus {
    tx: broadcast::Sender<AgentEvent>,
    recent: Arc<Mutex<VecDeque<AgentEvent>>>,
    capacity: usize,
}

impl EventBus {
    pub fn new(capacity: usize) -> Self {
        let (tx, _) = broadcast::channel(capacity.max(16));
        Self {
            tx,
            recent: Arc::new(Mutex::new(VecDeque::with_capacity(capacity))),
            capacity,
        }
    }

    pub async fn publish(&self, event: AgentEvent) {
        {
            let mut recent = self.recent.lock().await;
            if recent.len() == self.capacity {
                recent.pop_front();
            }
            recent.push_back(event.clone());
        }

        if self.tx.send(event).is_err() {
            warn!("event emitted without active subscribers");
        }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<AgentEvent> {
        self.tx.subscribe()
    }

    pub async fn recent_events(&self) -> Vec<AgentEvent> {
        let recent = self.recent.lock().await;
        recent.iter().cloned().collect()
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct StrategyRuntimeStatus {
    pub name: String,
    pub state: String,
    pub last_event_timestamp: Option<u64>,
}

#[derive(Debug, Clone, Default)]
pub struct StrategyStatusRegistry {
    statuses: Arc<RwLock<HashMap<String, StrategyRuntimeStatus>>>,
}

impl StrategyStatusRegistry {
    pub async fn initialize(&self, strategies: &[StrategyProfile]) {
        let mut statuses = self.statuses.write().await;
        for strategy in strategies {
            statuses.insert(
                strategy.name.clone(),
                StrategyRuntimeStatus {
                    name: strategy.name.clone(),
                    state: "starting".to_owned(),
                    last_event_timestamp: None,
                },
            );
        }
    }

    pub async fn mark_running(&self, strategy: &str) {
        self.update(strategy, "running").await;
    }

    pub async fn mark_stopped(&self, strategy: &str) {
        self.update(strategy, "stopped").await;
    }

    pub async fn mark_error(&self, strategy: &str) {
        self.update(strategy, "error").await;
    }

    async fn update(&self, strategy: &str, state: &str) {
        let mut statuses = self.statuses.write().await;
        let entry = statuses
            .entry(strategy.to_owned())
            .or_insert(StrategyRuntimeStatus {
                name: strategy.to_owned(),
                state: state.to_owned(),
                last_event_timestamp: None,
            });
        entry.state = state.to_owned();
        entry.last_event_timestamp = Some(timestamp_ms());
    }

    pub async fn list(&self) -> Vec<StrategyRuntimeStatus> {
        let statuses = self.statuses.read().await;
        let mut list: Vec<_> = statuses.values().cloned().collect();
        list.sort_by(|left, right| left.name.cmp(&right.name));
        list
    }
}

#[derive(Clone)]
pub struct ObserveHttpState {
    pub event_bus: EventBus,
    pub strategies: Vec<StrategyProfile>,
    pub statuses: StrategyStatusRegistry,
    pub started_at: Instant,
}

pub async fn serve_http(
    state: ObserveHttpState,
    shutdown: impl std::future::Future<Output = ()> + Send + 'static,
) -> Result<()> {
    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/strategies", get(strategies_handler))
        .route("/events", get(events_handler))
        .route("/ws", get(ws_handler))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 8989));
    let listener = TcpListener::bind(addr)
        .await
        .map_err(|error| ObserveError::Http(error.to_string()))?;
    info!(address = %addr, "observe server listening");

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await
        .map_err(|error| anyhow::anyhow!(ObserveError::Http(error.to_string())))
}

pub fn init_tracing(filter: &str) -> Result<()> {
    let env_filter = EnvFilter::try_new(filter)
        .map_err(|error| ObserveError::InvalidFilter(error.to_string()))?;

    fmt()
        .with_env_filter(env_filter)
        .with_target(false)
        .try_init()
        .map_err(|error| anyhow::anyhow!(error.to_string()))?;
    Ok(())
}

async fn health_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    let statuses = state.statuses.list().await;
    let body = HealthResponse {
        status: "ok".to_owned(),
        uptime_seconds: state.started_at.elapsed().as_secs(),
        active_strategies: statuses.iter().filter(|status| status.state == "running").count(),
        strategies: statuses,
    };
    (StatusCode::OK, Json(body))
}

async fn strategies_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    let statuses = state.statuses.list().await;
    let by_name: HashMap<_, _> = statuses
        .into_iter()
        .map(|status| (status.name.clone(), status))
        .collect();

    let strategies = state
        .strategies
        .iter()
        .map(|strategy| StrategyView {
            profile: strategy.clone(),
            status: by_name
                .get(&strategy.name)
                .cloned()
                .unwrap_or(StrategyRuntimeStatus {
                    name: strategy.name.clone(),
                    state: "unknown".to_owned(),
                    last_event_timestamp: None,
                }),
        })
        .collect::<Vec<_>>();

    (StatusCode::OK, Json(strategies))
}

async fn events_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    let events = state.event_bus.recent_events().await;
    (StatusCode::OK, Json(events))
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<ObserveHttpState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| websocket_task(socket, state))
}

async fn websocket_task(mut socket: WebSocket, state: ObserveHttpState) {
    let mut receiver = state.event_bus.subscribe();
    while let Ok(event) = receiver.recv().await {
        match serde_json::to_string(&event) {
            Ok(json) => {
                if socket.send(Message::Text(json.into())).await.is_err() {
                    break;
                }
            }
            Err(error) => {
                warn!(error = %error, "failed to serialize websocket event");
            }
        }
    }
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    status: String,
    uptime_seconds: u64,
    active_strategies: usize,
    strategies: Vec<StrategyRuntimeStatus>,
}

#[derive(Debug, Serialize)]
struct StrategyView {
    profile: StrategyProfile,
    status: StrategyRuntimeStatus,
}

fn to_value(data: impl Serialize) -> Value {
    match serde_json::to_value(data) {
        Ok(value) => value,
        Err(error) => {
            let mut fallback = Map::new();
            fallback.insert(
                "serialization_error".to_owned(),
                Value::String(error.to_string()),
            );
            Value::Object(fallback)
        }
    }
}

fn timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::{AgentEvent, EventBus};

    #[tokio::test]
    async fn event_bus_keeps_recent_events() {
        let bus = EventBus::new(2);
        bus.publish(AgentEvent::action(
            "swift",
            "whisperer",
            "signal_discovered",
            "Signal found",
            serde_json::json!({"symbol": "AST"}),
        ))
        .await;

        assert_eq!(bus.recent_events().await.len(), 1);
    }
}
