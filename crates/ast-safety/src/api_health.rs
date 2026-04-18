use std::collections::{HashMap, HashSet};
use std::time::{Duration, Instant};

use tokio::sync::RwLock;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EndpointStatus {
    Healthy,
    /// Failures observed but below the trip threshold.
    Degraded { failure_count: u32 },
    /// Circuit breaker tripped — this endpoint is considered down.
    Down,
}

#[derive(Debug, Clone)]
pub struct HealthConfig {
    /// Number of failures within `window` to trip the circuit breaker.
    pub failure_threshold: u32,
    /// Time window over which failures are counted.
    pub window: Duration,
    /// Endpoints whose `Down` status halts trading (e.g. RPC nodes).
    pub critical_endpoints: HashSet<String>,
}

impl Default for HealthConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 3,
            window: Duration::from_secs(300),
            critical_endpoints: HashSet::new(),
        }
    }
}

struct EndpointRecord {
    failures: Vec<Instant>,
    status: EndpointStatus,
}

impl EndpointRecord {
    fn new() -> Self {
        Self {
            failures: Vec::new(),
            status: EndpointStatus::Healthy,
        }
    }
}

/// Tracks the health of external API dependencies and trips a per-endpoint circuit breaker
/// after too many failures within the configured window.
pub struct ApiHealthMonitor {
    endpoints: RwLock<HashMap<String, EndpointRecord>>,
    config: HealthConfig,
}

impl ApiHealthMonitor {
    pub fn new(config: HealthConfig) -> Self {
        Self {
            endpoints: RwLock::new(HashMap::new()),
            config,
        }
    }

    /// Record a successful response from an endpoint, resetting its failure count.
    pub async fn report_success(&self, endpoint: &str) {
        let mut map = self.endpoints.write().await;
        let record = map
            .entry(endpoint.to_string())
            .or_insert_with(EndpointRecord::new);
        record.failures.clear();
        record.status = EndpointStatus::Healthy;
    }

    /// Record a failure from an endpoint. Returns the updated status after accounting
    /// for this failure. May trip the circuit breaker.
    pub async fn report_failure(&self, endpoint: &str) -> EndpointStatus {
        let now = Instant::now();
        let mut map = self.endpoints.write().await;
        let record = map
            .entry(endpoint.to_string())
            .or_insert_with(EndpointRecord::new);

        record.failures.push(now);
        // Prune failures that have aged out of the window
        record
            .failures
            .retain(|t| now.duration_since(*t) <= self.config.window);

        let count = record.failures.len() as u32;
        record.status = if count >= self.config.failure_threshold {
            EndpointStatus::Down
        } else if count > 0 {
            EndpointStatus::Degraded {
                failure_count: count,
            }
        } else {
            EndpointStatus::Healthy
        };

        record.status.clone()
    }

    /// Current health status of an endpoint.
    pub async fn status(&self, endpoint: &str) -> EndpointStatus {
        let map = self.endpoints.read().await;
        map.get(endpoint)
            .map(|r| r.status.clone())
            .unwrap_or(EndpointStatus::Healthy)
    }

    /// Returns true if `endpoint` is a critical dependency and is currently Down.
    /// When true, the caller should halt trading on the affected chain.
    pub async fn is_trading_halted(&self, endpoint: &str) -> bool {
        if !self.config.critical_endpoints.contains(endpoint) {
            return false;
        }
        self.status(endpoint).await == EndpointStatus::Down
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn monitor_with_threshold(n: u32) -> ApiHealthMonitor {
        ApiHealthMonitor::new(HealthConfig {
            failure_threshold: n,
            window: Duration::from_secs(60),
            critical_endpoints: HashSet::from_iter(["rpc_eth".to_string()]),
        })
    }

    #[tokio::test]
    async fn trips_after_threshold_failures() {
        let m = monitor_with_threshold(3);
        m.report_failure("dexscreener").await;
        m.report_failure("dexscreener").await;
        assert_eq!(
            m.status("dexscreener").await,
            EndpointStatus::Degraded { failure_count: 2 }
        );
        let final_status = m.report_failure("dexscreener").await;
        assert_eq!(final_status, EndpointStatus::Down);
    }

    #[tokio::test]
    async fn resets_on_success() {
        let m = monitor_with_threshold(3);
        m.report_failure("goplus").await;
        m.report_failure("goplus").await;
        m.report_failure("goplus").await;
        assert_eq!(m.status("goplus").await, EndpointStatus::Down);
        m.report_success("goplus").await;
        assert_eq!(m.status("goplus").await, EndpointStatus::Healthy);
    }

    #[tokio::test]
    async fn critical_endpoint_down_halts_trading() {
        let m = monitor_with_threshold(1);
        m.report_failure("rpc_eth").await;
        assert!(m.is_trading_halted("rpc_eth").await);
    }

    #[tokio::test]
    async fn non_critical_endpoint_down_does_not_halt_trading() {
        let m = monitor_with_threshold(1);
        m.report_failure("dexscreener").await;
        assert!(!m.is_trading_halted("dexscreener").await);
    }
}
