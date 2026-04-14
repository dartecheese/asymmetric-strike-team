pub mod persistence;
pub mod state_machine;

use std::collections::HashMap;
use std::path::Path;
use std::sync::Mutex;

use ast_core::{AstError, Result};
use ast_safety::AuthorizedOrder;
use async_trait::async_trait;

pub use persistence::PositionStore;
pub use state_machine::{ManagedPosition, ReaperAction, ReaperThresholds};

#[async_trait]
pub trait Reaper: Send + Sync {
    async fn track(&self, order: AuthorizedOrder) -> Result<()>;
    async fn monitor_positions(&self) -> Result<()>;
}

#[derive(Debug)]
pub struct FileBackedReaper {
    positions: Mutex<HashMap<String, ManagedPosition>>,
    store: PositionStore,
}

impl FileBackedReaper {
    pub fn new(path: impl AsRef<Path>) -> Result<Self> {
        let store = PositionStore::new(path.as_ref().to_path_buf());
        let restored = store
            .load_positions()?
            .into_iter()
            .map(|position| (position.id(), position))
            .collect::<HashMap<_, _>>();

        Ok(Self {
            positions: Mutex::new(restored),
            store,
        })
    }

    pub fn positions(&self) -> Result<Vec<ManagedPosition>> {
        Ok(self
            .positions
            .lock()
            .map_err(|_| AstError::Validation("reaper positions mutex poisoned".into()))?
            .values()
            .cloned()
            .collect())
    }

    fn persist_locked(&self, positions: &HashMap<String, ManagedPosition>) -> Result<()> {
        self.store.persist_positions(positions.values())
    }
}

#[async_trait]
impl Reaper for FileBackedReaper {
    async fn track(&self, order: AuthorizedOrder) -> Result<()> {
        let position = ManagedPosition::from_order(order.0)?;
        let mut positions = self
            .positions
            .lock()
            .map_err(|_| AstError::Validation("reaper positions mutex poisoned".into()))?;
        positions.insert(position.id(), position);
        self.persist_locked(&positions)
    }

    async fn monitor_positions(&self) -> Result<()> {
        let positions = self
            .positions
            .lock()
            .map_err(|_| AstError::Validation("reaper positions mutex poisoned".into()))?;
        self.persist_locked(&positions)
    }
}

pub struct NullReaper;

#[async_trait]
impl Reaper for NullReaper {
    async fn track(&self, _order: AuthorizedOrder) -> Result<()> {
        Ok(())
    }

    async fn monitor_positions(&self) -> Result<()> {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use ast_core::{ExecutionOrder, PositionState, Token, Usd, Venue};
    use ast_safety::AuthorizedOrder;
    use rust_decimal::Decimal;

    use super::{FileBackedReaper, Reaper};

    fn usd(value: i64) -> Usd {
        Usd::new(Decimal::new(value, 0)).expect("valid usd")
    }

    fn order(address: &str, amount: i64) -> AuthorizedOrder {
        AuthorizedOrder(ExecutionOrder {
            token: Token {
                address: address.into(),
                chain: "base".into(),
                symbol: "AST".into(),
                decimals: 18,
            },
            venue: Venue::Dex {
                chain: "base".into(),
                router: "router".into(),
            },
            amount_usd: usd(amount),
        })
    }

    fn temp_path(name: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("ast-reaper-lib-{name}-{nanos}"));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir.join("positions.json")
    }

    #[tokio::test]
    async fn restores_three_positions_after_restart() {
        let path = temp_path("restart");

        let reaper = FileBackedReaper::new(&path).expect("create reaper");
        reaper.track(order("0x1", 100)).await.expect("track 1");
        reaper.track(order("0x2", 50)).await.expect("track 2");
        reaper.track(order("0x3", 25)).await.expect("track 3");

        let restored = FileBackedReaper::new(&path).expect("restart reaper");
        let positions = restored.positions().expect("positions");

        assert_eq!(positions.len(), 3);
        assert!(
            positions
                .iter()
                .all(|position| position.state == PositionState::Open)
        );
    }
}
