use std::sync::Arc;

use anyhow::Result;
use ast_actuary::{Actuary, NullActuary};
use ast_core::StartupConfig;
use ast_observe::init_tracing;
use ast_reaper::{NullReaper, Reaper};
use ast_safety::{SafetyBreaker, SafetyContext};
use ast_slinger::{NullSlinger, Slinger};
use ast_whisperer::{NullWhisperer, Whisperer};
use tokio::{
    signal,
    time::{Duration, sleep},
};
use tracing::{error, info};

#[tokio::main]
async fn main() -> Result<()> {
    init_tracing();
    let startup = StartupConfig::load()?;
    let config = startup.app;

    let whisperer = Arc::new(NullWhisperer);
    let actuary = Arc::new(NullActuary);
    let slinger = Arc::new(NullSlinger);
    let safety = Arc::new(SafetyBreaker::default());
    let reaper = Arc::new(NullReaper);

    info!(
        paper_mode = config.paper_mode,
        "starting asymmetric strike team"
    );

    loop {
        tokio::select! {
            _ = signal::ctrl_c() => {
                info!("shutdown signal received");
                break;
            }
            result = run_cycle(&*whisperer, &*actuary, &*slinger, &*safety, &*reaper) => {
                if let Err(err) = result {
                    error!(error = %err, "trading cycle failed");
                }
                sleep(Duration::from_millis(config.scan_interval_ms)).await;
            }
        }
    }

    Ok(())
}

async fn run_cycle(
    whisperer: &dyn Whisperer,
    actuary: &dyn Actuary,
    slinger: &dyn Slinger,
    safety: &SafetyBreaker,
    reaper: &dyn Reaper,
) -> Result<()> {
    let signals = whisperer.scan().await?;
    for signal in signals {
        let risk = actuary.assess(&signal).await?;
        if risk.acceptable() {
            if let Ok(order) = slinger.route(&signal, &risk).await {
                let context = SafetyContext::default();
                if let Ok(authorized) = safety.authorize(order, &context) {
                    reaper.track(authorized).await?;
                }
            }
        }
    }
    reaper.monitor_positions().await?;
    Ok(())
}
