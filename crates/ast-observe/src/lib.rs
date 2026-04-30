use std::collections::{HashMap, VecDeque};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use async_trait::async_trait;
use axum::extract::{Path, State};
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use thiserror::Error;
use tokio::net::TcpListener;
use tokio::sync::{Mutex, RwLock, broadcast};
use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
use tracing::{info, warn};
use tracing_subscriber::{EnvFilter, fmt};

use ast_core::{Position, PositionState, StrategyProfile};

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

        let _ = self.tx.send(event);
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
    pub control_state: String,
    pub last_event_timestamp: Option<u64>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StrategyControlState {
    Starting,
    Running,
    Paused,
    Stopped,
    Error,
}

impl StrategyControlState {
    fn as_str(self) -> &'static str {
        match self {
            StrategyControlState::Starting => "starting",
            StrategyControlState::Running => "running",
            StrategyControlState::Paused => "paused",
            StrategyControlState::Stopped => "stopped",
            StrategyControlState::Error => "error",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AgentCapability {
    pub agent: String,
    pub mode: String,
    pub summary: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct StrategyCapabilityView {
    pub strategy: String,
    pub capabilities: Vec<AgentCapability>,
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
                    control_state: StrategyControlState::Starting.as_str().to_owned(),
                    last_event_timestamp: None,
                },
            );
        }
    }

    pub async fn mark_running(&self, strategy: &str) {
        self.update(strategy, "running", Some(StrategyControlState::Running)).await;
    }

    pub async fn mark_paused(&self, strategy: &str) {
        self.update(strategy, "paused", Some(StrategyControlState::Paused)).await;
    }

    pub async fn mark_stopped(&self, strategy: &str) {
        self.update(strategy, "stopped", Some(StrategyControlState::Stopped)).await;
    }

    pub async fn mark_error(&self, strategy: &str) {
        self.update(strategy, "error", Some(StrategyControlState::Error)).await;
    }

    pub async fn set_control_state(&self, strategy: &str, control_state: StrategyControlState) {
        let state = match control_state {
            StrategyControlState::Running => "running",
            StrategyControlState::Paused => "paused",
            StrategyControlState::Stopped => "stopped",
            StrategyControlState::Starting => "starting",
            StrategyControlState::Error => "error",
        };
        self.update(strategy, state, Some(control_state)).await;
    }

    pub async fn control_state_for(&self, strategy: &str) -> StrategyControlState {
        let statuses = self.statuses.read().await;
        statuses
            .get(strategy)
            .and_then(|status| match status.control_state.as_str() {
                "running" => Some(StrategyControlState::Running),
                "paused" => Some(StrategyControlState::Paused),
                "stopped" => Some(StrategyControlState::Stopped),
                "error" => Some(StrategyControlState::Error),
                _ => Some(StrategyControlState::Starting),
            })
            .unwrap_or(StrategyControlState::Starting)
    }

    async fn update(&self, strategy: &str, state: &str, control_state: Option<StrategyControlState>) {
        let mut statuses = self.statuses.write().await;
        let entry = statuses
            .entry(strategy.to_owned())
            .or_insert(StrategyRuntimeStatus {
                name: strategy.to_owned(),
                state: state.to_owned(),
                control_state: control_state.unwrap_or(StrategyControlState::Starting).as_str().to_owned(),
                last_event_timestamp: None,
            });
        entry.state = state.to_owned();
        if let Some(control_state) = control_state {
            entry.control_state = control_state.as_str().to_owned();
        }
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
    pub capabilities: Vec<StrategyCapabilityView>,
    pub operator: OperatorView,
    pub started_at: Instant,
    pub state_dir: PathBuf,
    pub initial_balance_usd: Decimal,
}

#[derive(Debug, Clone, Serialize)]
pub struct OperatorQuickActionView {
    pub label: String,
    pub command: String,
    pub summary: String,
    pub availability: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct OperatorView {
    pub selected_mode: String,
    pub effective_mode: String,
    pub live_execution_ready: bool,
    pub allow_live: bool,
    pub state_dir: String,
    pub dashboard_url: String,
    pub warnings: Vec<String>,
    pub quick_actions: Vec<OperatorQuickActionView>,
}

pub async fn serve_http(
    state: ObserveHttpState,
    shutdown: impl std::future::Future<Output = ()> + Send + 'static,
) -> Result<()> {
    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/operator", get(operator_handler))
        .route("/strategies", get(strategies_handler))
        .route("/strategies/{strategy}/control", post(strategy_control_handler))
        .route("/capabilities", get(capabilities_handler))
        .route("/events", get(events_handler))
        .route("/portfolio", get(portfolio_handler))
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
                    control_state: "unknown".to_owned(),
                    last_event_timestamp: None,
                }),
        })
        .collect::<Vec<_>>();

    (StatusCode::OK, Json(strategies))
}

async fn operator_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    (StatusCode::OK, Json(state.operator))
}

#[derive(Debug, Deserialize)]
struct StrategyControlRequest {
    action: String,
}

#[derive(Debug, Serialize)]
struct StrategyControlResponse {
    strategy: String,
    state: String,
    control_state: String,
}

async fn strategy_control_handler(
    Path(strategy): Path<String>,
    State(state): State<ObserveHttpState>,
    Json(request): Json<StrategyControlRequest>,
) -> impl IntoResponse {
    let action = request.action.to_lowercase();
    let control_state = match action.as_str() {
        "start" => StrategyControlState::Running,
        "pause" => StrategyControlState::Paused,
        "stop" => StrategyControlState::Stopped,
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": "action must be start, pause, or stop"})),
            )
                .into_response();
        }
    };

    state.statuses.set_control_state(&strategy, control_state).await;
    let statuses = state.statuses.list().await;
    if let Some(status) = statuses.into_iter().find(|status| status.name == strategy) {
        return (
            StatusCode::OK,
            Json(serde_json::json!(StrategyControlResponse {
                strategy: status.name,
                state: status.state,
                control_state: status.control_state,
            })),
        )
            .into_response();
    }

    (
        StatusCode::NOT_FOUND,
        Json(serde_json::json!({"error": "unknown strategy"})),
    )
        .into_response()
}

async fn events_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    let events = state.event_bus.recent_events().await;
    (StatusCode::OK, Json(events))
}

async fn capabilities_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    (StatusCode::OK, Json(state.capabilities))
}

async fn portfolio_handler(State(state): State<ObserveHttpState>) -> impl IntoResponse {
    let portfolio = build_portfolio_view(&state).await;
    (StatusCode::OK, Json(portfolio))
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

#[derive(Debug, Serialize)]
struct PortfolioResponse {
    initial_balance_usd: f64,
    cash_balance_usd: f64,
    equity_usd: f64,
    invested_usd: f64,
    realized_pnl_usd: f64,
    unrealized_pnl_usd: f64,
    open_positions: usize,
    holdings: Vec<HoldingView>,
}

#[derive(Debug, Serialize)]
struct HoldingView {
    strategy: String,
    token_symbol: String,
    chain: String,
    quantity: f64,
    entry_notional_usd: f64,
    market_value_usd: f64,
    realized_pnl_usd: f64,
    unrealized_pnl_usd: f64,
    state: String,
    updated_at_ms: u64,
}

async fn build_portfolio_view(state: &ObserveHttpState) -> PortfolioResponse {
    let mut holdings = Vec::new();
    let mut invested = Decimal::ZERO;
    let mut realized = Decimal::ZERO;
    let mut unrealized = Decimal::ZERO;

    for strategy in &state.strategies {
        let path = state
            .state_dir
            .join("positions")
            .join(format!("{}.json", strategy.name));
        let Ok(bytes) = tokio::fs::read(&path).await else {
            continue;
        };
        let Ok(positions) = serde_json::from_slice::<Vec<Position>>(&bytes) else {
            continue;
        };

        for position in positions {
            realized += position.realized_pnl_usd.0;
            if is_active_position(&position.state) {
                invested += position.entry_notional_usd.0;
                let market_value = position.current_price_usd.0 * position.quantity.0;
                let unrealized_value = position.unrealized_pnl_usd.0;
                unrealized += unrealized_value;

                holdings.push(HoldingView {
                    strategy: position.strategy.clone(),
                    token_symbol: position.token.symbol.clone(),
                    chain: position.token.chain.to_string(),
                    quantity: decimal_to_f64(position.quantity.0),
                    entry_notional_usd: decimal_to_f64(position.entry_notional_usd.0),
                    market_value_usd: decimal_to_f64(market_value),
                    realized_pnl_usd: decimal_to_f64(position.realized_pnl_usd.0),
                    unrealized_pnl_usd: decimal_to_f64(unrealized_value),
                    state: format!("{:?}", position.state).to_lowercase(),
                    updated_at_ms: position.updated_at_ms,
                });
            }
        }
    }

    holdings.sort_by(|left, right| right.updated_at_ms.cmp(&left.updated_at_ms));

    let cash_balance = state.initial_balance_usd + realized - invested;
    let equity = cash_balance + invested + unrealized;

    PortfolioResponse {
        initial_balance_usd: decimal_to_f64(state.initial_balance_usd),
        cash_balance_usd: decimal_to_f64(cash_balance),
        equity_usd: decimal_to_f64(equity),
        invested_usd: decimal_to_f64(invested),
        realized_pnl_usd: decimal_to_f64(realized),
        unrealized_pnl_usd: decimal_to_f64(unrealized),
        open_positions: holdings.len(),
        holdings,
    }
}

fn is_active_position(state: &PositionState) -> bool {
    matches!(
        state,
        PositionState::Pending | PositionState::Open | PositionState::FreeRide | PositionState::Closing
    )
}

fn decimal_to_f64(value: Decimal) -> f64 {
    value.to_f64().unwrap_or_default()
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
