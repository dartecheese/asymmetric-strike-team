/// Bridge module — receives AgenticTradingSignals from CryptoAgent (Python)
/// and injects them into the AST trading pipeline.
///
/// Protocol: POST /bridge/signal with JSON body matching
/// cryptoagent/bridge/signal_builder.py AgenticTradingSignal schema.

use super::ObserveHttpState;

use ast_core::{
    AgenticTradingSignal, BridgeDirection, BridgeRating, BridgeSignalResponse,
    Chain, Signal, Token, Usd, Venue,
};
use alloy_primitives::Address;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use rust_decimal::Decimal;
use tokio::sync::broadcast;
use tracing::{info, warn};


/// Queue for bridge signals — HTTP endpoint pushes, all strategy pipelines drain.
/// Uses broadcast so every strategy receives every signal.
#[derive(Clone)]
pub struct BridgeSignalQueue {
    tx: broadcast::Sender<(Signal, AgenticTradingSignal)>,
}

impl BridgeSignalQueue {
    pub fn new(capacity: usize) -> Self {
        let (tx, _) = broadcast::channel(capacity.max(16));
        Self { tx }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<(Signal, AgenticTradingSignal)> {
        self.tx.subscribe()
    }

    pub fn send(&self, signal: Signal, agentic: AgenticTradingSignal) {
        if let Err(error) = self.tx.send((signal, agentic)) {
            warn!(error = %error, "bridge signal broadcast failed");
        }
    }
}

/// Convert CryptoAgent's JSON signal into an AST Signal + validate.
pub fn agentic_to_signal(agentic: &AgenticTradingSignal) -> Result<(Signal, AgenticTradingSignal), String> {
    // Parse chain
    let chain = match agentic.chain.to_lowercase().as_str() {
        "ethereum" => Chain::Ethereum,
        "arbitrum" => Chain::Arbitrum,
        "base" => Chain::Base,
        "solana" => Chain::Solana,
        other => return Err(format!("unsupported chain: {}", other)),
    };

    // Parse token address — fall back to zero address if invalid
    let address = agentic.token_address.parse::<Address>().unwrap_or(Address::ZERO);
    if address == Address::ZERO {
        return Err(format!("invalid token address: {}", agentic.token_address));
    }

    // Map direction
    let _direction = &agentic.direction;

    // Only LONG signals are actionable for entry
    if agentic.direction != BridgeDirection::Long {
        return Err(format!(
            "signal direction {:?} not actionable for entry — only Long signals are accepted",
            agentic.direction
        ));
    }

    // Map rating → must be Buy or Overweight to act
    if !matches!(agentic.rating, BridgeRating::Buy | BridgeRating::Overweight) {
        return Err(format!(
            "signal rating {:?} not actionable — only Buy/Overweight generate entries",
            agentic.rating
        ));
    }

    let price_usd = agentic.entry_price_usd.map(|p| {
        Usd::new(Decimal::from_f64_retain(p).unwrap_or_default()).unwrap_or(Usd::zero())
    }).unwrap_or(Usd::zero());

    let position_size = agentic.position_size_usd
        .and_then(|s| Decimal::from_f64_retain(s))
        .unwrap_or(Decimal::new(100, 0));

    let volume_24h = position_size * Decimal::new(10, 0);

    let signal = Signal {
        id: format!("bridge-{}", timestamp_ms()),
        token: Token {
            address,
            chain: chain.clone(),
            symbol: format!("token-{}", &agentic.token_address[..8.min(agentic.token_address.len())]),
            decimals: 18,
        },
        venue: Venue::Dex {
            chain,
            router: Address::ZERO, // Will be resolved by slinger's venue resolver
        },
        price_usd,
        volume_24h_usd: Usd::new(volume_24h).unwrap_or(Usd::zero()),
        liquidity_usd: Usd::new(position_size * Decimal::new(5, 0)).unwrap_or(Usd::zero()),
        target_notional_usd: Usd::new(position_size).unwrap_or(Usd::zero()),
        timestamp_ms: timestamp_ms(),
        metadata: {
            let mut meta = std::collections::BTreeMap::new();
            meta.insert("source".to_owned(), "cryptoagent-bridge".to_owned());
            meta.insert("rationale".to_owned(), agentic.rationale.clone());
            meta.insert("time_horizon".to_owned(), agentic.time_horizon.clone());
            meta.insert("conviction".to_owned(), format!("{:?}", agentic.conviction));
            meta.insert("narrative_tags".to_owned(), agentic.narrative_tags.join(","));
            if let Some(ref entry_type) = agentic.entry_type {
                meta.insert("entry_type".to_owned(), entry_type.clone());
            }
            if let Some(slippage) = agentic.max_slippage_bps {
                meta.insert("max_slippage_bps".to_owned(), slippage.to_string());
            }
            if let Some(stop_loss) = agentic.stop_loss_pct {
                meta.insert("stop_loss_pct".to_owned(), stop_loss.to_string());
            }
            if let Some(take_profit) = agentic.take_profit_pct {
                meta.insert("take_profit_pct".to_owned(), take_profit.to_string());
            }
            if !agentic.risk_flags.is_empty() {
                meta.insert("risk_flags".to_owned(), agentic.risk_flags.join(","));
            }
            meta
        },
    };

    Ok((signal, agentic.clone()))
}

/// POST /bridge/signal — receives an AgenticTradingSignal from CryptoAgent.
pub async fn bridge_signal_handler(
    State(state): State<ObserveHttpState>,
    Json(signal): Json<AgenticTradingSignal>,
) -> impl IntoResponse {
    if state.bridge_queue.is_none() {
        let response = BridgeSignalResponse {
            accepted: false,
            reason: "bridge not enabled — start AST with bridge support".to_owned(),
            stage: "disabled".to_owned(),
            position_id: None,
            details: None,
        };
        return (StatusCode::SERVICE_UNAVAILABLE, Json(response)).into_response();
    };
    info!(
        token = %signal.token_address,
        chain = %signal.chain,
        rating = ?signal.rating,
        direction = ?signal.direction,
        "bridge signal received from CryptoAgent"
    );

    match agentic_to_signal(&signal) {
        Ok((ast_signal, _agentic)) => {
            let signal_id = ast_signal.id.clone();
            let token_symbol = ast_signal.token.symbol.clone();
            let token_chain = ast_signal.token.chain.to_string();
            info!(
                signal_id = %signal_id,
                token = %token_symbol,
                chain = %token_chain,
                "bridge signal converted — enqueuing for pipeline"
            );
            if let Some(ref queue) = state.bridge_queue {
                queue.send(ast_signal, signal.clone());
            }

            let response = BridgeSignalResponse {
                accepted: true,
                reason: "signal enqueued for trading pipeline".to_owned(),
                stage: "received".to_owned(),
                position_id: None,
                details: Some(serde_json::json!({
                    "signal_id": signal_id,
                    "token": token_symbol,
                    "chain": token_chain,
                })),
            };
            (StatusCode::OK, Json(response)).into_response()
        }
        Err(error) => {
            warn!(error = %error, "bridge signal validation failed");
            let response = BridgeSignalResponse {
                accepted: false,
                reason: error,
                stage: "validation_failed".to_owned(),
                position_id: None,
                details: None,
            };
            (StatusCode::BAD_REQUEST, Json(response)).into_response()
        }
    }
}

/// GET /bridge/health — health check for the bridge.
pub async fn bridge_health_handler() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "status": "ok",
            "bridge": "cryptoagent-ast",
            "version": "0.1.0",
            "protocol": "agentic_trading_signal_v1",
        })),
    )
}

fn timestamp_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or_default()
}
