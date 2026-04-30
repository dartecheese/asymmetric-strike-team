use std::collections::BTreeMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use serde_json::Value;

static HUB: OnceLock<Mutex<MarketDataHubState>> = OnceLock::new();

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProviderFailureKind {
    RateLimited,
    Other,
}

#[derive(Debug, Clone)]
pub struct ProviderCooldown {
    pub retry_after: Duration,
}

#[derive(Debug, Default)]
struct MarketDataHubState {
    providers: BTreeMap<&'static str, ProviderState>,
    cache: BTreeMap<String, CacheEntry>,
}

#[derive(Debug)]
struct ProviderState {
    next_request_at: Instant,
    cooldown_until: Option<Instant>,
    consecutive_failures: u32,
    consecutive_rate_limits: u32,
}

impl Default for ProviderState {
    fn default() -> Self {
        Self {
            next_request_at: Instant::now(),
            cooldown_until: None,
            consecutive_failures: 0,
            consecutive_rate_limits: 0,
        }
    }
}

#[derive(Debug, Clone)]
struct CacheEntry {
    value: Value,
    stored_at: Instant,
}

fn hub() -> &'static Mutex<MarketDataHubState> {
    HUB.get_or_init(|| Mutex::new(MarketDataHubState::default()))
}

pub fn cached_json(key: &str, max_age: Duration) -> Option<Value> {
    let state = hub().lock().ok()?;
    let entry = state.cache.get(key)?;
    if entry.stored_at.elapsed() <= max_age {
        Some(entry.value.clone())
    } else {
        None
    }
}

pub fn cache_json(key: impl Into<String>, value: &Value) {
    if let Ok(mut state) = hub().lock() {
        state.cache.insert(
            key.into(),
            CacheEntry {
                value: value.clone(),
                stored_at: Instant::now(),
            },
        );
        if state.cache.len() > 1024 {
            let stale_keys: Vec<String> = state
                .cache
                .iter()
                .filter(|(_, entry)| entry.stored_at.elapsed() > Duration::from_secs(300))
                .map(|(key, _)| key.clone())
                .collect();
            for key in stale_keys {
                state.cache.remove(&key);
            }
        }
    }
}

pub fn prepare_request(
    provider: &'static str,
    min_spacing: Duration,
) -> Result<Duration, ProviderCooldown> {
    let now = Instant::now();
    let mut state = hub()
        .lock()
        .expect("market data hub mutex poisoned");
    let provider_state = state.providers.entry(provider).or_default();

    if let Some(cooldown_until) = provider_state.cooldown_until {
        if cooldown_until > now {
            return Err(ProviderCooldown {
                retry_after: cooldown_until.saturating_duration_since(now),
            });
        }
        provider_state.cooldown_until = None;
    }

    let scheduled_at = provider_state.next_request_at.max(now);
    provider_state.next_request_at = scheduled_at + min_spacing;
    Ok(scheduled_at.saturating_duration_since(now))
}

pub fn record_success(provider: &'static str) {
    if let Ok(mut state) = hub().lock() {
        let provider_state = state.providers.entry(provider).or_default();
        provider_state.cooldown_until = None;
        provider_state.consecutive_failures = 0;
        provider_state.consecutive_rate_limits = 0;
    }
}

pub fn record_failure(provider: &'static str, kind: ProviderFailureKind) {
    if let Ok(mut state) = hub().lock() {
        let provider_state = state.providers.entry(provider).or_default();
        provider_state.consecutive_failures = provider_state.consecutive_failures.saturating_add(1);
        match kind {
            ProviderFailureKind::RateLimited => {
                provider_state.consecutive_rate_limits = provider_state.consecutive_rate_limits.saturating_add(1);
                let seconds = match provider_state.consecutive_rate_limits {
                    1 => 10,
                    2 => 30,
                    3 => 90,
                    _ => 180,
                };
                provider_state.cooldown_until = Some(Instant::now() + Duration::from_secs(seconds));
            }
            ProviderFailureKind::Other => {
                if provider_state.consecutive_failures >= 3 {
                    provider_state.cooldown_until = Some(Instant::now() + Duration::from_secs(15));
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{cache_json, cached_json, prepare_request, record_failure, record_success, ProviderFailureKind};
    use serde_json::json;
    use std::time::Duration;

    #[test]
    fn cache_round_trip_works() {
        cache_json("test-key", &json!({"ok": true}));
        let value = cached_json("test-key", Duration::from_secs(1)).expect("cached value");
        assert_eq!(value["ok"], true);
    }

    #[test]
    fn provider_cools_down_after_rate_limit() {
        record_success("test-provider");
        record_failure("test-provider", ProviderFailureKind::RateLimited);
        let result = prepare_request("test-provider", Duration::from_millis(1));
        assert!(result.is_err());
    }
}
