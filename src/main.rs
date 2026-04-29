use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use ast_actuary::{GoPlusActuary, RiskAssessor};
use ast_core::{AppConfig, CliOverrides, ExecutionOrder, Position, StrategyProfile};
use ast_observe::{
    init_tracing, serve_http, AgentEvent, EventBus, ObserveHttpState, StrategyStatusRegistry,
};
use ast_reaper::{FileReaper, PositionTracker};
use ast_slinger::{DefaultVenueResolver, ExecutionRouter, PaperSlinger};
use ast_whisperer::{DexScreenerWhisperer, SignalScanner};
use clap::Parser;
use dotenvy::dotenv;
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
}

#[tokio::main]
async fn main() -> Result<()> {
    let _ = dotenv();
    let cli = Cli::parse();
    let config = AppConfig::load(
        &cli.config,
        CliOverrides {
            log_filter: cli.log_filter,
        },
    )?;
    init_tracing(&config.observe.log_filter)?;

    print_startup_banner(&config);

    let event_bus = EventBus::new(config.runtime.recent_event_capacity);
    let statuses = StrategyStatusRegistry::default();
    statuses.initialize(&config.strategies).await;

    let (shutdown_tx, _) = broadcast::channel::<()>(1);
    let http_state = ObserveHttpState {
        event_bus: event_bus.clone(),
        strategies: config.strategies.clone(),
        statuses: statuses.clone(),
        started_at: std::time::Instant::now(),
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

        pipeline_handles.push(tokio::spawn(async move {
            if let Err(error) = run_strategy_pipeline(
                strategy,
                runtime.state_dir,
                paper_trading.enabled,
                paper_trading.default_slippage_model,
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
    paper_mode: bool,
    slippage_model: String,
    event_bus: EventBus,
    statuses: StrategyStatusRegistry,
    shutdown_rx: &mut broadcast::Receiver<()>,
) -> Result<()> {
    let whisperer: Arc<dyn SignalScanner> =
        Arc::new(DexScreenerWhisperer::new(strategy.clone(), paper_mode));
    let actuary: Arc<dyn RiskAssessor> = Arc::new(GoPlusActuary::new(strategy.clone(), paper_mode));
    let slinger: Arc<dyn ExecutionRouter> =
        Arc::new(PaperSlinger::new(strategy.clone(), DefaultVenueResolver, slippage_model));
    let reaper: Arc<dyn PositionTracker> =
        Arc::new(FileReaper::new(state_dir, &strategy.name).await?);

    statuses.mark_running(&strategy.name).await;
    let mut interval = tokio::time::interval(Duration::from_secs(strategy.scan_interval_seconds));
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

    loop {
        tokio::select! {
            _ = shutdown_rx.recv() => {
                statuses.mark_stopped(&strategy.name).await;
                break;
            }
            _ = interval.tick() => {
                if let Err(error) = process_strategy_iteration(
                    &strategy,
                    whisperer.as_ref(),
                    actuary.as_ref(),
                    slinger.as_ref(),
                    reaper.as_ref(),
                    &event_bus,
                    &statuses,
                ).await {
                    statuses.mark_error(&strategy.name).await;
                    event_bus.publish(AgentEvent::Error {
                        strategy: strategy.name.clone(),
                        agent: "pipeline".to_owned(),
                        message: error.to_string(),
                        timestamp: timestamp_ms(),
                    }).await;
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
    slinger: &dyn ExecutionRouter,
    reaper: &dyn PositionTracker,
    event_bus: &EventBus,
    statuses: &StrategyStatusRegistry,
) -> Result<()> {
    let signals = whisperer.scan().await.map_err(anyhow::Error::from)?;
    for signal in signals {
        event_bus
            .publish(AgentEvent::SignalDiscovered {
                strategy: strategy.name.clone(),
                signal: signal.clone(),
                timestamp: timestamp_ms(),
            })
            .await;

        let assessment = match actuary.assess(&signal).await {
            Ok(assessment) => assessment,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::Error {
                        strategy: strategy.name.clone(),
                        agent: "actuary".to_owned(),
                        message: error.to_string(),
                        timestamp: timestamp_ms(),
                    })
                    .await;
                continue;
            }
        };

        event_bus
            .publish(AgentEvent::RiskAssessed {
                strategy: strategy.name.clone(),
                signal_id: signal.id.clone(),
                assessment: assessment.clone(),
                timestamp: timestamp_ms(),
            })
            .await;

        if !assessment.acceptable() {
            continue;
        }

        let order = match slinger.route(&signal, &assessment).await {
            Ok(order) => order,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::Error {
                        strategy: strategy.name.clone(),
                        agent: "slinger".to_owned(),
                        message: error.to_string(),
                        timestamp: timestamp_ms(),
                    })
                    .await;
                continue;
            }
        };

        emit_order_constructed(strategy, &order, event_bus).await;

        let result = match slinger.execute(&order).await {
            Ok(result) => result,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::Error {
                        strategy: strategy.name.clone(),
                        agent: "slinger".to_owned(),
                        message: error.to_string(),
                        timestamp: timestamp_ms(),
                    })
                    .await;
                continue;
            }
        };

        event_bus
            .publish(AgentEvent::OrderFilled {
                strategy: strategy.name.clone(),
                order_id: order.id.clone(),
                result: result.clone(),
                timestamp: timestamp_ms(),
            })
            .await;

        match reaper.track_fill(&order, &signal, &result).await {
            Ok(position) => emit_position(strategy, position, event_bus).await,
            Err(error) => {
                statuses.mark_error(&strategy.name).await;
                event_bus
                    .publish(AgentEvent::Error {
                        strategy: strategy.name.clone(),
                        agent: "reaper".to_owned(),
                        message: error.to_string(),
                        timestamp: timestamp_ms(),
                    })
                    .await;
            }
        }
    }

    let positions = reaper.monitor_positions().await.map_err(anyhow::Error::from)?;
    for position in positions {
        emit_position(strategy, position, event_bus).await;
    }
    statuses.mark_running(&strategy.name).await;
    Ok(())
}

async fn emit_order_constructed(strategy: &StrategyProfile, order: &ExecutionOrder, event_bus: &EventBus) {
    event_bus
        .publish(AgentEvent::OrderConstructed {
            strategy: strategy.name.clone(),
            order: order.clone(),
            timestamp: timestamp_ms(),
        })
        .await;
}

async fn emit_position(strategy: &StrategyProfile, position: Position, event_bus: &EventBus) {
    event_bus
        .publish(AgentEvent::PositionUpdated {
            strategy: strategy.name.clone(),
            position,
            timestamp: timestamp_ms(),
        })
        .await;
}

fn print_startup_banner(config: &AppConfig) {
    info!(
        strategies = config.strategies.len(),
        paper_mode = config.paper_trading.enabled,
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

fn timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or_default()
}
