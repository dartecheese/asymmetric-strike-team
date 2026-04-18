use std::sync::Arc;

use anyhow::Result;
use ast_actuary::{ActuaryConfig, GoPlusActuary, GoPlusConfig};
use ast_core::StartupConfig;
use ast_observe::init_tracing;
use ast_reaper::{FileBackedReaper, Reaper};
use ast_safety::{SafetyBreaker, SafetyConfig, SafetyContext};
use ast_slinger::{NullSlinger, Slinger};
use ast_whisperer::{DexScreenerConfig, DexScreenerWhisperer, Whisperer};
use tokio::{
    signal,
    time::{Duration, sleep},
};
use tracing::{error, info, warn};

#[tokio::main]
async fn main() -> Result<()> {
    init_tracing();
    let startup = StartupConfig::load()?;
    let config = startup.app;

    info!(paper_mode = config.paper_mode, "starting asymmetric strike team");

    let whisperer = Arc::new(
        DexScreenerWhisperer::new(DexScreenerConfig::default())
            .expect("failed to build DexScreener client"),
    );
    let actuary = Arc::new(
        GoPlusActuary::new(GoPlusConfig::default(), ActuaryConfig::default())
            .expect("failed to build GoPlus actuary"),
    );
    let slinger = Arc::new(NullSlinger); // paper mode — no TX submission
    let safety = Arc::new(SafetyBreaker::default());
    let reaper = Arc::new(
        FileBackedReaper::new("data/positions.json")
            .expect("failed to initialize position store"),
    );

    if config.paper_mode {
        info!("paper mode: signals are assessed and tracked but no transactions are submitted");
    } else {
        warn!("LIVE MODE: real transactions will be submitted");
    }

    loop {
        tokio::select! {
            _ = signal::ctrl_c() => {
                info!("shutdown signal received — stopping");
                break;
            }
            result = run_cycle(&*whisperer, &*actuary, &*slinger, &*safety, &*reaper) => {
                if let Err(err) = result {
                    error!(error = %err, "trading cycle error");
                }
                sleep(Duration::from_millis(config.scan_interval_ms)).await;
            }
        }
    }

    Ok(())
}

async fn run_cycle(
    whisperer: &dyn Whisperer,
    actuary: &dyn ast_actuary::Actuary,
    slinger: &dyn Slinger,
    safety: &SafetyBreaker,
    reaper: &dyn Reaper,
) -> Result<()> {
    let signals = whisperer.scan().await?;
    info!(count = signals.len(), "scan complete");

    for signal in signals {
        info!(
            token = %signal.token.address,
            symbol = %signal.token.symbol,
            chain = %signal.token.chain,
            confidence_bps = signal.confidence_bps,
            "signal detected"
        );

        let risk = match actuary.assess(&signal).await {
            Ok(r) => r,
            Err(e) => {
                warn!(token = %signal.token.address, error = %e, "risk assessment failed — skipping");
                continue;
            }
        };

        info!(
            token = %signal.token.address,
            risk_level = ?risk.risk_level,
            max_allocation = %risk.max_allocation_usd,
            "risk assessed"
        );

        if !risk.acceptable() {
            info!(token = %signal.token.address, "rejected by risk filter");
            continue;
        }

        match slinger.route(&signal, &risk).await {
            Ok(order) => {
                let context = SafetyContext::default();
                match safety.authorize(order, &context) {
                    Ok(authorized) => {
                        if let Err(e) = reaper.track(authorized).await {
                            error!(error = %e, "failed to track position");
                        }
                    }
                    Err(e) => {
                        warn!(error = %e, "safety check failed — order blocked");
                    }
                }
            }
            Err(e) => {
                warn!(token = %signal.token.address, error = %e, "routing failed");
            }
        }
    }

    reaper.monitor_positions().await?;
    Ok(())
}
