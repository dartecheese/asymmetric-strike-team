mod learning;
mod llm;

use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use ast_actuary::{GoPlusActuary, RiskAssessor};
use ast_core::{AppConfig, CliOverrides, ExecutionOrder, Position, Signal, StrategyProfile};
use ast_observe::{
    init_tracing, serve_http, AgentCapability, AgentEvent, EventBus, ObserveHttpState,
    StrategyCapabilityView, StrategyControlState, StrategyStatusRegistry,
};
use ast_reaper::{FileReaper, PositionTracker};
use ast_safety::{CircuitBreaker, PaperSafety};
use ast_slinger::{DefaultVenueResolver, ExecutionRouter, PaperSlinger};
use ast_whisperer::{DexScreenerWhisperer, SignalScanner};
use clap::{Parser, ValueEnum};
use dotenvy::dotenv;
use learning::EpisodeJournal;
use llm::{LocalBrain, SignalIntent};
use rust_decimal::Decimal;
use serde_json::json;
use tokio::sync::broadcast;
use tracing::{error, info};

#[derive(Debug, Parser)]
#[command(name = "asymmetric-strike-team")]
#[command(about = "Phase 1 paper-trading orchestration for the Asymmetric Strike Team")]
struct Cli {
    #[arg(long, default_value = "config/default.toml")]
    config: PathBuf,
    #[arg(long)]
    log_filter: Option<String>,
    #[arg(long, value_enum, default_value_t = LaunchMode::Paper)]
    mode: LaunchMode,
    #[arg(long, default_value_t = false)]
    fresh_paper: bool,
    #[arg(long, default_value_t = false)]
    allow_live: bool,
}

#[derive(Debug, Clone, Copy, ValueEnum, PartialEq, Eq)]
enum LaunchMode {
    Paper,
    Live,
}

#[derive(Debug, Clone)]
struct OperatorOverview {
    selected_mode: String,
    effective_mode: String,
    live_execution_ready: bool,
    allow_live: bool,
    state_dir: String,
    dashboard_url: String,
    warnings: Vec<String>,
    quick_actions: Vec<OperatorQuickAction>,
}

#[derive(Debug, Clone)]
struct OperatorQuickAction {
    label: String,
    command: String,
    summary: String,
    availability: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let _ = dotenv();
    let cli = Cli::parse();
    let mut operator = build_operator_overview(&cli);
    enforce_operator_mode(&cli, &operator)?;
    let config = AppConfig::load(
        &cli.config,
        CliOverrides {
            log_filter: cli.log_filter,
            paper_trading_enabled: Some(true),
        },
    )?;
    init_tracing(&config.observe.log_filter)?;
    operator.state_dir = config.runtime.state_dir.clone();

    if cli.fresh_paper {
        archive_paper_state(&config.runtime.state_dir).await?;
    }

    print_startup_banner(&config, &operator);

    let event_bus = EventBus::new(config.runtime.recent_event_capacity);
    let statuses = StrategyStatusRegistry::default();
    let local_brain = Arc::new(LocalBrain::new(config.llm.clone()));
    let episode_journal = Arc::new(EpisodeJournal::new(&config.runtime.state_dir));
    statuses.initialize(&config.strategies).await;

    let (shutdown_tx, _) = broadcast::channel::<()>(1);
    let http_state = ObserveHttpState {
        event_bus: event_bus.clone(),
        strategies: config.strategies.clone(),
        statuses: statuses.clone(),
        capabilities: build_capabilities(&config),
        operator: ast_observe::OperatorView {
            selected_mode: operator.selected_mode.clone(),
            effective_mode: operator.effective_mode.clone(),
            live_execution_ready: operator.live_execution_ready,
            allow_live: operator.allow_live,
            state_dir: operator.state_dir.clone(),
            dashboard_url: operator.dashboard_url.clone(),
            warnings: operator.warnings.clone(),
            quick_actions: operator
                .quick_actions
                .iter()
                .map(|action| ast_observe::OperatorQuickActionView {
                    label: action.label.clone(),
                    command: action.command.clone(),
                    summary: action.summary.clone(),
                    availability: action.availability.clone(),
                })
                .collect(),
        },
        started_at: std::time::Instant::now(),
        state_dir: PathBuf::from(&config.runtime.state_dir),
        initial_balance_usd: config.paper_trading.initial_balance_usd.0,
    };
    let mut server_shutdown_rx = shutdown_tx.subscribe();
    let server_handle = tokio::spawn(async move {
        serve_http(http_state, async move {
            let _ = server_shutdown_rx.recv().await;
        })
        .await
    });
    tokio::pin!(server_handle);

    let mut pipeline_handles = Vec::with_capacity(config.strategies.len());
    for strategy in config.strategies.clone() {
        let mut shutdown_rx = shutdown_tx.subscribe();
        let status_registry = statuses.clone();
        let event_bus_for_task = event_bus.clone();
        let runtime = config.runtime.clone();
        let paper_trading = config.paper_trading.clone();
        let local_brain = local_brain.clone();
        let episode_journal = episode_journal.clone();

        pipeline_handles.push(tokio::spawn(async move {
            if let Err(error) = run_strategy_pipeline(
                strategy,
                runtime.state_dir,
                paper_trading,
                local_brain,
                episode_journal,
                event_bus_for_task,
                status_registry,
                &mut shutdown_rx,
            )
            .await
            {
                error!(error = %error, "strategy pipeline failed");
            }
        }));
    }

    tokio::select! {
        result = &mut server_handle => {
            match result {
                Ok(Ok(())) => info!("http server exited"),
                Ok(Err(error)) => error!(error = %error, "http server failed"),
                Err(error) => error!(error = %error, "http server task panicked"),
            }
        }
        signal = shutdown_signal() => {
            if let Err(error) = signal {
                error!(error = %error, "shutdown signal handler failed");
            } else {
                info!("shutdown signal received");
            }
        }
    }

    let _ = shutdown_tx.send(());
    for handle in pipeline_handles {
        match handle.await {
            Ok(()) => {}
            Err(error) => error!(error = %error, "pipeline task join failed"),
        }
    }

    match server_handle.await {
        Ok(Ok(())) => {}
        Ok(Err(error)) => error!(error = %error, "http server shutdown failed"),
        Err(error) => error!(error = %error, "http server join failed"),
    }

    info!("asymmetric strike team stopped");
    Ok(())
}

async fn run_strategy_pipeline(
    strategy: StrategyProfile,
    state_dir: String,
    paper_trading: ast_core::PaperTradingConfig,
    local_brain: Arc<LocalBrain>,
    episode_journal: Arc<EpisodeJournal>,
    event_bus: EventBus,
    statuses: StrategyStatusRegistry,
    shutdown_rx: &mut broadcast::Receiver<()>,
) -> Result<()> {
    let whisperer: Arc<dyn SignalScanner> =
        Arc::new(DexScreenerWhisperer::new(
            strategy.clone(),
            paper_trading.enabled,
            paper_trading.use_live_market_data,
        ));
    let actuary: Arc<dyn RiskAssessor> = Arc::new(GoPlusActuary::new(
        strategy.clone(),
        paper_trading.enabled,
        paper_trading.use_live_risk_checks,
    ));
    let slinger: Arc<dyn ExecutionRouter> =
        Arc::new(PaperSlinger::new(
            strategy.clone(),
            DefaultVenueResolver,
            paper_trading.default_slippage_model.clone(),
        ));
    let safety: Arc<dyn CircuitBreaker> = Arc::new(PaperSafety::new(strategy.clone()));
    let reaper: Arc<dyn PositionTracker> =
        Arc::new(FileReaper::new(state_dir, &strategy.name).await?);

    statuses.mark_running(&strategy.name).await;
    emit_report_ins(&strategy, &paper_trading, &event_bus).await;
    let mut interval = tokio::time::interval(Duration::from_secs(strategy.scan_interval_seconds));
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

    loop {
        tokio::select! {
            _ = shutdown_rx.recv() => {
                statuses.mark_stopped(&strategy.name).await;
                break;
            }
            _ = interval.tick() => {
                match statuses.control_state_for(&strategy.name).await {
                    StrategyControlState::Paused => {
                        statuses.mark_paused(&strategy.name).await;
                        continue;
                    }
                    StrategyControlState::Stopped => {
                        statuses.mark_stopped(&strategy.name).await;
                        continue;
                    }
                    StrategyControlState::Running | StrategyControlState::Starting => {
                        statuses.mark_running(&strategy.name).await;
                    }
                    StrategyControlState::Error => {
                        continue;
                    }
                }

                if let Err(error) = process_strategy_iteration(
                    &strategy,
                    whisperer.as_ref(),
                    actuary.as_ref(),
                    safety.as_ref(),
                    slinger.as_ref(),
                    reaper.as_ref(),
                    local_brain.as_ref(),
                    episode_journal.as_ref(),
                    paper_trading.initial_balance_usd.0,
                    &event_bus,
                    &statuses,
                ).await {
                    statuses.mark_error(&strategy.name).await;
                    event_bus
                        .publish(AgentEvent::error(
                            strategy.name.clone(),
                            "pipeline",
                            error.to_string(),
                        ))
                        .await;
                }
            }
        }
    }

    Ok(())
}

async fn process_strategy_iteration(
    strategy: &StrategyProfile,
    whisperer: &dyn SignalScanner,
    actuary: &dyn RiskAssessor,
    safety: &dyn CircuitBreaker,
    slinger: &dyn ExecutionRouter,
    reaper: &dyn PositionTracker,
    local_brain: &LocalBrain,
    episode_journal: &EpisodeJournal,
    initial_balance_usd: Decimal,
    event_bus: &EventBus,
    statuses: &StrategyStatusRegistry,
) -> Result<()> {
    let signals = whisperer.scan().await.map_err(anyhow::Error::from)?;
    for signal in signals {
        let _ = episode_journal.record_signal(&strategy.name, &signal).await;
        let signal_intent = local_brain.signal_intent(strategy, &signal).await;
        if let Some(intent) = &signal_intent {
            let _ = episode_journal.record_intent(&strategy.name, &signal, intent).await;
        }

        event_bus
            .publish(AgentEvent::action(
                strategy.name.clone(),
                "whisperer",
                "signal_discovered",
                format!(
                    "Found {} on {} at ${}",
                    signal.token.symbol,
                    signal.token.chain,
                    signal.price_usd.0.round_dp(6)
                ),
                json!({
                    "signal_id": signal.id,
                    "token_symbol": signal.token.symbol,
                    "chain": signal.token.chain.to_string(),
                    "price_usd": signal.price_usd.0,
                    "volume_24h_usd": signal.volume_24h_usd.0,
                    "liquidity_usd": signal.liquidity_usd.0,
                    "source": signal.metadata.get("source").cloned().unwrap_or_else(|| "unknown".to_owned()),
                    "intent": signal_intent.as_ref().map(|intent| intent.intent.clone()),
                    "thesis": signal_intent.as_ref().map(|intent| intent.thesis.clone()),
                    "expected_move_pct": signal_intent.as_ref().map(|intent| intent.expected_move_pct),
                    "max_holding_minutes": signal_intent.as_ref().map(|intent| intent.max_holding_minutes),
                    "llm_model": signal_intent.as_ref().map(|intent| intent.model.clone()),
                    "explanation": explain_signal(strategy, &signal, signal_intent.as_ref()),
                }),
            ))
            .await;

        let assessment = match actuary.assess(&signal).await {
            Ok(assessment) => assessment,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::error(strategy.name.clone(), "actuary", error.to_string()))
                    .await;
                continue;
            }
        };

        let _ = episode_journal.record_risk(&strategy.name, &signal, &assessment).await;

        event_bus
            .publish(AgentEvent::action(
                strategy.name.clone(),
                "actuary",
                "risk_assessed",
                format!(
                    "{} {} as {:?}",
                    match assessment.decision {
                        ast_core::RiskDecision::Accept => "Accepted",
                        ast_core::RiskDecision::Reject => "Rejected",
                        ast_core::RiskDecision::Review => "Flagged",
                    },
                    signal.token.symbol,
                    assessment.level
                ),
                json!({
                    "signal_id": signal.id,
                    "decision": format!("{:?}", assessment.decision).to_lowercase(),
                    "level": format!("{:?}", assessment.level).to_lowercase(),
                    "approved_notional_usd": assessment.approved_notional_usd.0,
                    "acceptable": assessment.acceptable(),
                    "rationale": assessment.rationale,
                    "factors": assessment.factors,
                    "explanation": explain_risk(strategy, &signal, &assessment),
                }),
            ))
            .await;

        if !assessment.acceptable() {
            continue;
        }

        let safety_decision = match safety.evaluate(&signal, &assessment).await {
            Ok(decision) => decision,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::error(strategy.name.clone(), "safety", error.to_string()))
                    .await;
                continue;
            }
        };

        event_bus
            .publish(AgentEvent::action(
                strategy.name.clone(),
                "safety",
                "safety_evaluated",
                if safety_decision.should_trade {
                    format!("Safety approved {}", signal.token.symbol)
                } else {
                    format!("Safety blocked {}", signal.token.symbol)
                },
                json!({
                    "signal_id": signal.id,
                    "should_trade": safety_decision.should_trade,
                    "reason": safety_decision.reason,
                    "explanation": explain_safety(strategy, &signal, &safety_decision),
                }),
            ))
            .await;

        let _ = episode_journal
            .record_safety(
                &strategy.name,
                &signal,
                safety_decision.should_trade,
                &safety_decision.reason,
            )
            .await;

        if !safety_decision.should_trade {
            continue;
        }

        let order = match slinger.route(&signal, &assessment).await {
            Ok(order) => order,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::error(strategy.name.clone(), "slinger", error.to_string()))
                    .await;
                continue;
            }
        };

        let _ = episode_journal.record_order(&strategy.name, &signal, &order).await;

        emit_order_constructed(strategy, &order, event_bus).await;

        let result = match slinger.execute(&order).await {
            Ok(result) => result,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::error(strategy.name.clone(), "slinger", error.to_string()))
                    .await;
                continue;
            }
        };

        let _ = episode_journal
            .record_fill(&strategy.name, &signal, &order, &result)
            .await;

        event_bus
            .publish(AgentEvent::action(
                strategy.name.clone(),
                "slinger",
                "order_filled",
                format!(
                    "Paper-filled {} {} at ${}",
                    result.filled_amount.0.round_dp(6),
                    signal.token.symbol,
                    result.fill_price_usd.0.round_dp(6)
                ),
                json!({
                    "order_id": order.id,
                    "filled_amount": result.filled_amount.0,
                    "fill_price_usd": result.fill_price_usd.0,
                    "slippage_bps": result.slippage_bps,
                    "fill_ratio_bps": result.fill_ratio_bps,
                    "requested_notional_usd": result.requested_notional_usd.0,
                    "notional_usd": result.notional_usd.0,
                    "fee_usd": result.fee_usd.0,
                    "venue": result.venue,
                }),
            ))
            .await;

        match reaper.track_fill(&order, &signal, &result).await {
            Ok(position) => {
                emit_position(
                    strategy,
                    &signal,
                    position,
                    local_brain,
                    episode_journal,
                    initial_balance_usd,
                    event_bus,
                ).await
            }
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::error(strategy.name.clone(), "reaper", error.to_string()))
                    .await;
            }
        }
    }

    let positions = reaper.monitor_positions().await.map_err(anyhow::Error::from)?;
    let _ = episode_journal
        .record_strategy_portfolio(&strategy.name, &positions)
        .await;
    let _ = episode_journal.record_global_portfolio(initial_balance_usd).await;
    for position in positions {
        let shadow_signal = signal_from_position(&position);
        emit_position(
            strategy,
            &shadow_signal,
            position,
            local_brain,
            episode_journal,
            initial_balance_usd,
            event_bus,
        ).await;
    }
    statuses.mark_running(&strategy.name).await;
    Ok(())
}

async fn emit_order_constructed(strategy: &StrategyProfile, order: &ExecutionOrder, event_bus: &EventBus) {
    event_bus
        .publish(AgentEvent::action(
            strategy.name.clone(),
            "slinger",
            "order_constructed",
            format!(
                "Built paper order for {} ${}",
                order.token.symbol,
                order.notional_usd.0.round_dp(2)
            ),
            json!({
                "order_id": order.id,
                "token_symbol": order.token.symbol,
                "amount": order.amount.0,
                "notional_usd": order.notional_usd.0,
                "limit_price_usd": order.limit_price_usd.0,
                "max_slippage_bps": order.max_slippage_bps,
                "explanation": explain_order(strategy, order),
            }),
        ))
        .await;
}

async fn emit_position(
    strategy: &StrategyProfile,
    signal: &Signal,
    position: Position,
    local_brain: &LocalBrain,
    episode_journal: &EpisodeJournal,
    initial_balance_usd: Decimal,
    event_bus: &EventBus,
) {
    let prior_intent = episode_journal
        .latest_intent(&strategy.name, &position.signal_id)
        .await
        .ok()
        .flatten();
    let reflection = if position.monitor_passes > 0 {
        match prior_intent.as_ref() {
            Some(intent) => local_brain.reflect_position(strategy, signal, &position, intent).await,
            None => None,
        }
    } else {
        None
    };

    if let Some(reflection) = &reflection {
        let _ = episode_journal
            .record_reflection(&strategy.name, signal, &position, reflection)
            .await;
    }

    let _ = episode_journal
        .record_position(&strategy.name, signal, &position)
        .await;
    let _ = episode_journal.record_global_portfolio(initial_balance_usd).await;

    event_bus
        .publish(AgentEvent::action(
            strategy.name.clone(),
            "reaper",
            "position_updated",
            format!(
                "{} {} at ${}",
                format!("{:?}", position.state),
                position.token.symbol,
                position.current_price_usd.0.round_dp(6)
            ),
            json!({
                "position_id": position.id,
                "signal_id": position.signal_id,
                "token_symbol": position.token.symbol,
                "state": format!("{:?}", position.state).to_lowercase(),
                "entry_price_usd": position.entry_price_usd.0,
                "current_price_usd": position.current_price_usd.0,
                "realized_pnl_usd": position.realized_pnl_usd.0,
                "unrealized_pnl_usd": position.unrealized_pnl_usd.0,
                "fees_paid_usd": position.fees_paid_usd.0,
                "monitor_passes": position.monitor_passes,
                "reflection": reflection,
                "explanation": explain_position(strategy, &position),
            }),
        ))
        .await;

    if let Some(reflection) = reflection {
        event_bus
            .publish(AgentEvent::action(
                strategy.name.clone(),
                "critic",
                "intent_reflected",
                format!("Reviewed {} against original intent", signal.token.symbol),
                json!({
                    "signal_id": signal.id,
                    "token_symbol": signal.token.symbol,
                    "matched_intent": reflection.matched_intent,
                    "score": reflection.score,
                    "adjustment": reflection.adjustment,
                    "explanation": reflection.verdict,
                }),
            ))
            .await;
    }
}

fn explain_signal(strategy: &StrategyProfile, signal: &ast_core::Signal, intent: Option<&SignalIntent>) -> String {
    if let Some(intent) = intent {
        return format!(
            "I surfaced {} on {} because {}. I expect about {}% follow-through within {} minutes.",
            signal.token.symbol,
            signal.token.chain,
            intent.thesis.trim_end_matches('.'),
            intent.expected_move_pct,
            intent.max_holding_minutes,
        );
    }

    format!(
        "I surfaced {} on {} because it matches my {} mandate, shows ${} liquidity, ${} of 24h volume, and a live price near ${}.",
        signal.token.symbol,
        signal.token.chain,
        strategy.description.to_lowercase(),
        signal.liquidity_usd.0.round_dp(2),
        signal.volume_24h_usd.0.round_dp(2),
        signal.price_usd.0.round_dp(6),
    )
}

fn explain_risk(
    _strategy: &StrategyProfile,
    signal: &ast_core::Signal,
    assessment: &ast_core::RiskAssessment,
) -> String {
    let top_factors = assessment
        .factors
        .iter()
        .take(2)
        .map(|factor| format!("{} ({})", factor.name, factor.details))
        .collect::<Vec<_>>()
        .join(", ");

    format!(
        "I rated {} as {:?} / {:?}. Approved notional is ${}. Main drivers: {}.",
        signal.token.symbol,
        assessment.decision,
        assessment.level,
        assessment.approved_notional_usd.0.round_dp(2),
        if top_factors.is_empty() { "none recorded" } else { &top_factors },
    )
}

fn explain_safety(
    _strategy: &StrategyProfile,
    signal: &ast_core::Signal,
    decision: &ast_safety::SafetyDecision,
) -> String {
    format!(
        "I {} {} because {}.",
        if decision.should_trade { "approved" } else { "blocked" },
        signal.token.symbol,
        decision.reason.trim_end_matches('.'),
    )
}

fn explain_order(_strategy: &StrategyProfile, order: &ExecutionOrder) -> String {
    format!(
        "I sized a paper order for {} worth ${} with a limit near ${}, using ${} liquidity and ${} of 24h volume as the execution context, with a max slippage cap of {} bps.",
        order.token.symbol,
        order.notional_usd.0.round_dp(2),
        order.limit_price_usd.0.round_dp(6),
        order.observed_liquidity_usd.0.round_dp(2),
        order.observed_volume_24h_usd.0.round_dp(2),
        order.max_slippage_bps,
    )
}

fn explain_position(_strategy: &StrategyProfile, position: &Position) -> String {
    format!(
        "I am monitoring {} in state {:?}. Entry ${}, current ${}, realized PnL ${}, unrealized PnL ${}, fees ${}, monitor passes {}.",
        position.token.symbol,
        position.state,
        position.entry_price_usd.0.round_dp(6),
        position.current_price_usd.0.round_dp(6),
        position.realized_pnl_usd.0.round_dp(2),
        position.unrealized_pnl_usd.0.round_dp(2),
        position.fees_paid_usd.0.round_dp(2),
        position.monitor_passes,
    )
}

async fn emit_report_ins(
    strategy: &StrategyProfile,
    paper_trading: &ast_core::PaperTradingConfig,
    event_bus: &EventBus,
) {
    let source_summary = if paper_trading.use_live_market_data {
        "live DexScreener → GeckoTerminal → cached-live → paper fallback chain, filtered to Uniswap / Aerodrome / PancakeSwap / SushiSwap / Camelot"
    } else {
        "mock paper market feed"
    };
    let risk_summary = if paper_trading.use_live_risk_checks {
        "GoPlus + Honeypot.is risk checks with heuristic paper fallback"
    } else {
        "heuristic paper risk model"
    };

    for (agent, summary) in [
        ("whisperer", format!("Whisperer online: {source_summary}")),
        ("actuary", format!("Actuary online: {risk_summary}")),
        (
            "slinger",
            format!(
                "Slinger online: paper execution using {} slippage",
                paper_trading.default_slippage_model
            ),
        ),
        (
            "safety",
            "Safety online: paper circuit breaker guarding auto-execution".to_owned(),
        ),
        ("reaper", "Reaper online: local position tracking active".to_owned()),
        ("critic", "Critic online: Bridge reflections compare intended vs observed outcomes".to_owned()),
    ] {
        event_bus
            .publish(AgentEvent::report_in(strategy.name.clone(), agent, summary))
            .await;
    }
}

fn build_capabilities(config: &AppConfig) -> Vec<StrategyCapabilityView> {
    config
        .strategies
        .iter()
        .map(|strategy| StrategyCapabilityView {
            strategy: strategy.name.clone(),
            capabilities: vec![
                AgentCapability {
                    agent: "whisperer".to_owned(),
                    mode: if config.llm.enabled && config.llm.enabled_strategies.iter().any(|name| name == &strategy.name) {
                        "local-qwen+live".to_owned()
                    } else if config.paper_trading.use_live_market_data {
                        "live+fallback".to_owned()
                    } else {
                        "fallback-only".to_owned()
                    },
                    summary: if config.llm.enabled && config.llm.enabled_strategies.iter().any(|name| name == &strategy.name) {
                        format!("DexScreener + GeckoTerminal live feeds across Uniswap, Aerodrome, PancakeSwap, SushiSwap, and Camelot with local Ollama intent generation via {}", config.llm.live_model)
                    } else if config.paper_trading.use_live_market_data {
                        "DexScreener primary, GeckoTerminal secondary, cached-live fallback, then paper mock; notable DEX coverage: Uniswap, Aerodrome, PancakeSwap, SushiSwap, Camelot".to_owned()
                    } else {
                        "Paper mock market feed only".to_owned()
                    },
                },
                AgentCapability {
                    agent: "actuary".to_owned(),
                    mode: if config.paper_trading.use_live_risk_checks {
                        "live+fallback".to_owned()
                    } else {
                        "fallback-only".to_owned()
                    },
                    summary: if config.paper_trading.use_live_risk_checks {
                        "GoPlus primary, Honeypot.is secondary, heuristic fallback".to_owned()
                    } else {
                        "Heuristic paper risk model only".to_owned()
                    },
                },
                AgentCapability {
                    agent: "safety".to_owned(),
                    mode: "local-guard".to_owned(),
                    summary: format!(
                        "Paper circuit breaker active; blocks >250bps slippage configs and poor liquidity ratio for {}",
                        strategy.name
                    ),
                },
                AgentCapability {
                    agent: "slinger".to_owned(),
                    mode: "paper-execution".to_owned(),
                    summary: format!(
                        "Paper execution via {} slippage model",
                        config.paper_trading.default_slippage_model
                    ),
                },
                AgentCapability {
                    agent: "reaper".to_owned(),
                    mode: "local-state".to_owned(),
                    summary: "Local file-backed position tracking with DexScreener/GeckoTerminal mark fallbacks".to_owned(),
                },
                AgentCapability {
                    agent: "critic".to_owned(),
                    mode: if config.llm.enabled && config.llm.enabled_strategies.iter().any(|name| name == &strategy.name) {
                        "local-qwen-critic".to_owned()
                    } else {
                        "standby".to_owned()
                    },
                    summary: if config.llm.enabled && config.llm.enabled_strategies.iter().any(|name| name == &strategy.name) {
                        format!("After-action reflection via {} with intent/outcome journaling", config.llm.critic_model)
                    } else {
                        "Critic disabled for this strategy".to_owned()
                    },
                },
            ],
        })
        .collect()
}

fn signal_from_position(position: &Position) -> Signal {
    Signal {
        id: position.signal_id.clone(),
        token: position.token.clone(),
        venue: position.venue.clone(),
        price_usd: position.current_price_usd.clone(),
        volume_24h_usd: position
            .metadata
            .get("last_mark_volume_24h_usd")
            .and_then(|value| value.parse().ok())
            .and_then(|value| ast_core::Usd::new(value).ok())
            .unwrap_or_else(|| position.entry_notional_usd.clone()),
        liquidity_usd: position
            .metadata
            .get("last_mark_liquidity_usd")
            .and_then(|value| value.parse().ok())
            .and_then(|value| ast_core::Usd::new(value).ok())
            .unwrap_or_else(|| position.entry_notional_usd.clone()),
        target_notional_usd: position.entry_notional_usd.clone(),
        timestamp_ms: position.updated_at_ms,
        metadata: position.metadata.clone(),
    }
}

async fn archive_paper_state(state_dir: &str) -> Result<()> {
    let state_root = Path::new(state_dir);
    let archive_root = state_root.join("archive").join(format!("fresh-paper-{}", timestamp_ms()));
    let mut moved_any = false;

    for name in ["positions", "ledger"] {
        let source = state_root.join(name);
        if !tokio::fs::try_exists(&source).await? {
            continue;
        }

        let mut entries = tokio::fs::read_dir(&source).await?;
        if entries.next_entry().await?.is_none() {
            continue;
        }

        tokio::fs::create_dir_all(&archive_root).await?;
        tokio::fs::rename(&source, archive_root.join(name)).await?;
        tokio::fs::create_dir_all(&source).await?;
        moved_any = true;
    }

    if moved_any {
        info!(archive = %archive_root.display(), "archived prior paper state for fresh run");
    } else {
        info!("fresh-paper requested but no prior paper state needed archiving");
    }

    Ok(())
}

fn build_operator_overview(cli: &Cli) -> OperatorOverview {
    let selected_mode = match cli.mode {
        LaunchMode::Paper => "paper",
        LaunchMode::Live => "live",
    }
    .to_owned();
    let live_execution_ready = false;
    let effective_mode = if cli.mode == LaunchMode::Live {
        "live_guarded"
    } else {
        "paper"
    }
    .to_owned();

    let mut warnings = Vec::new();
    if cli.mode == LaunchMode::Paper {
        warnings.push("Paper mode is active: fills are simulated, but market marks and risk checks can use live crypto data.".to_owned());
    } else {
        warnings.push("Live mode was requested, but on-chain execution is not wired yet. The runtime will not place real trades.".to_owned());
        warnings.push("A wallet/RPC/swap executor and kill-switch path must exist before live can be enabled for real capital.".to_owned());
    }

    let binary = "./target/debug/asymmetric-strike-team";
    let quick_actions = vec![
        OperatorQuickAction {
            label: "Resume paper session".to_owned(),
            command: format!("{binary} --mode paper"),
            summary: "Continue paper trading from existing state files.".to_owned(),
            availability: "ready".to_owned(),
        },
        OperatorQuickAction {
            label: "Fresh paper run".to_owned(),
            command: format!("{binary} --mode paper --fresh-paper"),
            summary: "Archive old paper state and start a clean paper session.".to_owned(),
            availability: "ready".to_owned(),
        },
        OperatorQuickAction {
            label: "Attempt live mode".to_owned(),
            command: format!("{binary} --mode live --allow-live"),
            summary: "Reserved for future real execution. Currently guarded and blocked.".to_owned(),
            availability: if live_execution_ready { "ready" } else { "blocked" }.to_owned(),
        },
    ];

    OperatorOverview {
        selected_mode,
        effective_mode,
        live_execution_ready,
        allow_live: cli.allow_live,
        state_dir: "data".to_owned(),
        dashboard_url: "http://127.0.0.1:8989".to_owned(),
        warnings,
        quick_actions,
    }
}

fn enforce_operator_mode(cli: &Cli, operator: &OperatorOverview) -> Result<()> {
    if cli.mode == LaunchMode::Live && !cli.allow_live {
        anyhow::bail!(
            "live mode requires --allow-live. This guard prevents accidental real-money launches."
        );
    }

    if cli.mode == LaunchMode::Live && !operator.live_execution_ready {
        anyhow::bail!(
            "live mode is not available yet: wallet/RPC/swap execution is still missing. Use --mode paper for now."
        );
    }

    Ok(())
}

fn print_startup_banner(config: &AppConfig, operator: &OperatorOverview) {
    info!(
        strategies = config.strategies.len(),
        paper_mode = config.paper_trading.enabled,
        selected_mode = %operator.selected_mode,
        effective_mode = %operator.effective_mode,
        llm_enabled = config.llm.enabled,
        llm_live_model = %config.llm.live_model,
        llm_critic_model = %config.llm.critic_model,
        "starting asymmetric strike team"
    );
    for strategy in &config.strategies {
        info!(
            strategy = %strategy.name,
            interval_seconds = strategy.scan_interval_seconds,
            max_position_usd = %strategy.max_position_size_usd.0,
            slippage_bps = strategy.max_slippage_bps,
            "strategy profile loaded"
        );
    }
}

fn timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}

async fn shutdown_signal() -> Result<()> {
    #[cfg(unix)]
    {
        let mut terminate = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())?;
        tokio::select! {
            result = tokio::signal::ctrl_c() => {
                result?;
            }
            _ = terminate.recv() => {}
        }
    }

    #[cfg(not(unix))]
    {
        tokio::signal::ctrl_c().await?;
    }

    Ok(())
}
