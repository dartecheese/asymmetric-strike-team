use std::time::Duration;

use ast_core::{LlmConfig, Position, Signal, StrategyProfile};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::warn;

#[derive(Debug, Clone)]
pub struct LocalBrain {
    config: LlmConfig,
    client: Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalIntent {
    pub intent: String,
    pub thesis: String,
    pub expected_move_pct: f64,
    pub max_holding_minutes: u64,
    pub invalidation: Vec<String>,
    pub confidence: u8,
    pub model: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeReflection {
    pub verdict: String,
    pub matched_intent: bool,
    pub score: u8,
    pub what_happened: String,
    pub lesson: String,
    pub adjustment: String,
    pub model: String,
}

#[derive(Debug, Deserialize)]
struct OllamaGenerateResponse {
    response: String,
}

impl LocalBrain {
    pub fn new(config: LlmConfig) -> Self {
        let timeout = Duration::from_millis(config.request_timeout_ms.max(1_000));
        let client = Client::builder()
            .timeout(timeout)
            .build()
            .unwrap_or_else(|_| Client::new());
        Self { config, client }
    }

    pub fn enabled_for(&self, strategy: &StrategyProfile) -> bool {
        self.config.enabled
            && self
                .config
                .enabled_strategies
                .iter()
                .any(|name| name == &strategy.name)
    }

    pub fn live_model(&self) -> &str {
        &self.config.live_model
    }

    pub fn critic_model(&self) -> &str {
        &self.config.critic_model
    }

    pub async fn signal_intent(
        &self,
        strategy: &StrategyProfile,
        signal: &Signal,
    ) -> Option<SignalIntent> {
        if !self.enabled_for(strategy) {
            return None;
        }

        let prompt = format!(
            "You are the Whisperer/Planner for a paper-trading strategy named {strategy_name}.\nReturn strict JSON only.\n\nContext:\n- strategy_description: {strategy_description}\n- token: {token}\n- chain: {chain}\n- price_usd: {price}\n- volume_24h_usd: {volume}\n- liquidity_usd: {liquidity}\n- target_notional_usd: {notional}\n\nRespond with this JSON schema exactly:\n{{\n  \"intent\": \"short statement of what you are trying to capture\",\n  \"thesis\": \"one sentence in first person\",\n  \"expected_move_pct\": number,
  \"max_holding_minutes\": integer,
  \"invalidation\": [\"string\"],
  \"confidence\": integer_0_to_100
}}",
            strategy_name = strategy.name,
            strategy_description = strategy.description,
            token = signal.token.symbol,
            chain = signal.token.chain,
            price = signal.price_usd.0.round_dp(6),
            volume = signal.volume_24h_usd.0.round_dp(2),
            liquidity = signal.liquidity_usd.0.round_dp(2),
            notional = signal.target_notional_usd.0.round_dp(2),
        );

        let value = self.generate_json(self.live_model(), &prompt).await?;
        let mut intent: SignalIntent = serde_json::from_value(value).ok()?;
        intent.model = self.live_model().to_owned();
        Some(intent)
    }

    pub async fn reflect_position(
        &self,
        strategy: &StrategyProfile,
        signal: &Signal,
        position: &Position,
        intent: &SignalIntent,
    ) -> Option<TradeReflection> {
        if !self.enabled_for(strategy) {
            return None;
        }

        let pnl = position.realized_pnl_usd.0.round_dp(2);
        let prompt = format!(
            "You are the Critic for a paper-trading strategy named {strategy_name}.\nReturn strict JSON only.\n\nOriginal intent:\n- intent: {intent}\n- thesis: {thesis}\n- expected_move_pct: {expected_move_pct}\n- max_holding_minutes: {max_holding_minutes}\n- invalidation: {invalidation}\n- confidence: {confidence}\n\nObserved outcome:\n- token: {token}\n- state: {state:?}\n- entry_price_usd: {entry}\n- current_price_usd: {current}\n- realized_pnl_usd: {pnl}\n- monitor_passes: {monitor_passes}\n\nRespond with this JSON schema exactly:\n{{\n  \"verdict\": \"one sentence in first person\",\n  \"matched_intent\": true,
  \"score\": integer_0_to_100,
  \"what_happened\": \"short factual summary\",
  \"lesson\": \"one lesson\",
  \"adjustment\": \"one prompt or threshold adjustment\"
}}",
            strategy_name = strategy.name,
            intent = intent.intent,
            thesis = intent.thesis,
            expected_move_pct = intent.expected_move_pct,
            max_holding_minutes = intent.max_holding_minutes,
            invalidation = intent.invalidation.join(", "),
            confidence = intent.confidence,
            token = signal.token.symbol,
            state = position.state,
            entry = position.entry_price_usd.0.round_dp(6),
            current = position.current_price_usd.0.round_dp(6),
            pnl = pnl,
            monitor_passes = position.monitor_passes,
        );

        let value = self.generate_json(self.critic_model(), &prompt).await?;
        let mut reflection: TradeReflection = serde_json::from_value(value).ok()?;
        reflection.model = self.critic_model().to_owned();
        Some(reflection)
    }

    async fn generate_json(&self, model: &str, prompt: &str) -> Option<Value> {
        let url = format!("{}/api/generate", self.config.base_url.trim_end_matches('/'));
        let payload = json!({
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": false,
            "options": {
                "temperature": 0.2
            }
        });

        let response = self.client.post(url).json(&payload).send().await.ok()?;
        if !response.status().is_success() {
            warn!(status = %response.status(), model, "ollama request failed");
            return None;
        }

        let generated: OllamaGenerateResponse = response.json().await.ok()?;
        match serde_json::from_str::<Value>(&generated.response) {
            Ok(value) => Some(value),
            Err(error) => {
                warn!(error = %error, model, "ollama returned non-json response");
                None
            }
        }
    }
}
