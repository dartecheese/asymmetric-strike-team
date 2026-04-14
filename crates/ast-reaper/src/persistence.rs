use std::collections::hash_map::DefaultHasher;
use std::fs::{self, File, OpenOptions};
use std::hash::{Hash, Hasher};
use std::io::Write;
use std::path::{Path, PathBuf};

use ast_core::{AstError, PositionState, Result};
use serde::{Deserialize, Serialize};

use crate::state_machine::ManagedPosition;

const MAGIC: &str = "AST_REAPER_V1";
const VERSION: u32 = 1;

#[derive(Debug, Clone)]
pub struct PositionStore {
    path: PathBuf,
}

#[derive(Debug, Serialize, Deserialize)]
struct PersistedEnvelope {
    magic: String,
    version: u32,
    checksum: String,
    positions: Vec<PersistedPosition>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
struct PersistedPosition {
    token: ast_core::Token,
    venue: ast_core::Venue,
    state: PositionState,
    amount_usd: ast_core::Usd,
    entry_value_usd: ast_core::Usd,
    current_value_usd: ast_core::Usd,
    peak_value_usd: ast_core::Usd,
}

impl PositionStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn load_positions(&self) -> Result<Vec<ManagedPosition>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }

        let bytes = fs::read(&self.path)?;
        let envelope: PersistedEnvelope = serde_json::from_slice(&bytes).map_err(|error| {
            AstError::PersistenceCorruption(format!(
                "invalid persistence payload in {}: {error}",
                self.path.display()
            ))
        })?;
        self.validate_envelope(&envelope)?;

        envelope
            .positions
            .into_iter()
            .map(|persisted| {
                ManagedPosition::restore(
                    persisted.token,
                    persisted.venue,
                    persisted.state,
                    persisted.amount_usd,
                    persisted.entry_value_usd,
                    persisted.current_value_usd,
                    persisted.peak_value_usd,
                )
            })
            .collect()
    }

    pub fn persist_positions<'a>(
        &self,
        positions: impl IntoIterator<Item = &'a ManagedPosition>,
    ) -> Result<()> {
        let positions = positions
            .into_iter()
            .map(PersistedPosition::from)
            .collect::<Vec<_>>();
        let checksum = checksum_positions(&positions)?;
        let envelope = PersistedEnvelope {
            magic: MAGIC.into(),
            version: VERSION,
            checksum,
            positions,
        };
        let payload = serde_json::to_vec_pretty(&envelope)?;
        self.atomic_write(&payload)
    }

    fn validate_envelope(&self, envelope: &PersistedEnvelope) -> Result<()> {
        if envelope.magic != MAGIC {
            return Err(AstError::PersistenceCorruption(format!(
                "unexpected magic bytes in {}",
                self.path.display()
            )));
        }
        if envelope.version != VERSION {
            return Err(AstError::PersistenceCorruption(format!(
                "unsupported reaper persistence version {}",
                envelope.version
            )));
        }

        let actual = checksum_positions(&envelope.positions)?;
        if actual != envelope.checksum {
            return Err(AstError::PersistenceCorruption(format!(
                "checksum mismatch for {}",
                self.path.display()
            )));
        }
        Ok(())
    }

    fn atomic_write(&self, payload: &[u8]) -> Result<()> {
        let parent = self.path.parent().ok_or_else(|| {
            AstError::Validation(format!(
                "position store path {} has no parent",
                self.path.display()
            ))
        })?;
        fs::create_dir_all(parent)?;

        let file_name = self.path.file_name().ok_or_else(|| {
            AstError::Validation(format!(
                "position store path {} has no filename",
                self.path.display()
            ))
        })?;
        let temp_path = parent.join(format!("{}.tmp", file_name.to_string_lossy()));

        {
            let mut temp_file = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .open(&temp_path)?;
            temp_file.write_all(payload)?;
            temp_file.sync_all()?;
        }

        fs::rename(&temp_path, &self.path)?;
        sync_dir(parent)?;
        Ok(())
    }
}

impl From<&ManagedPosition> for PersistedPosition {
    fn from(position: &ManagedPosition) -> Self {
        Self {
            token: position.token.clone(),
            venue: position.venue.clone(),
            state: position.state.clone(),
            amount_usd: position.amount_usd,
            entry_value_usd: position.entry_value_usd,
            current_value_usd: position.current_value_usd,
            peak_value_usd: position.peak_value_usd,
        }
    }
}

fn checksum_positions(positions: &[PersistedPosition]) -> Result<String> {
    let bytes = serde_json::to_vec(positions)?;
    let mut hasher = DefaultHasher::new();
    bytes.hash(&mut hasher);
    Ok(format!("{:016x}", hasher.finish()))
}

fn sync_dir(path: &Path) -> Result<()> {
    let dir = File::open(path)?;
    dir.sync_all()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    use ast_core::{ExecutionOrder, PositionState, Token, Usd, Venue};
    use rust_decimal::Decimal;

    use super::PositionStore;
    use crate::state_machine::ManagedPosition;

    fn usd(value: i64) -> Usd {
        Usd::new(Decimal::new(value, 0)).expect("valid usd")
    }

    fn temp_path(name: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("ast-reaper-{name}-{nanos}"));
        fs::create_dir_all(&dir).expect("create temp dir");
        dir.join("positions.json")
    }

    fn sample_position(address: &str, state: PositionState, value: i64) -> ManagedPosition {
        ManagedPosition::restore(
            Token::new(address, "base", "AST", 18).expect("valid token"),
            Venue::dex("base", "router").expect("valid venue"),
            state,
            usd(value),
            usd(value),
            usd(value),
            usd(value),
        )
        .expect("restorable position")
    }

    #[test]
    fn round_trips_positions_across_restart() {
        let path = temp_path("roundtrip");
        let store = PositionStore::new(&path);
        let positions = vec![
            sample_position("0x1", PositionState::Open, 100),
            sample_position("0x2", PositionState::FreeRide, 50),
            sample_position("0x3", PositionState::Closing, 25),
        ];

        store.persist_positions(positions.iter()).expect("persist");

        let reloaded = PositionStore::new(&path).load_positions().expect("reload");
        assert_eq!(reloaded.len(), 3);
        assert_eq!(reloaded[1].state, PositionState::FreeRide);
    }

    #[test]
    fn rejects_corrupted_payloads() {
        let path = temp_path("corrupt");
        fs::write(
            &path,
            br#"{"magic":"AST_REAPER_V1","version":1,"checksum":"bad","positions":[]}"#,
        )
        .expect("write corrupt payload");

        let error = PositionStore::new(&path)
            .load_positions()
            .expect_err("corruption should fail");
        assert!(matches!(
            error,
            ast_core::AstError::PersistenceCorruption(_)
        ));
    }

    #[test]
    fn persists_from_execution_order_shape() {
        let path = temp_path("order-shape");
        let store = PositionStore::new(&path);
        let position = ManagedPosition::from_order(
            ExecutionOrder::builder()
                .token(Token::new("0x4", "base", "AST", 18).expect("valid token"))
                .venue(Venue::dex("base", "router").expect("valid venue"))
                .amount_usd(usd(42))
                .build()
                .expect("valid execution order"),
        )
        .expect("from order");

        store.persist_positions([&position]).expect("persist");
        let restored = store.load_positions().expect("load");

        assert_eq!(restored.len(), 1);
        assert_eq!(restored[0].state, PositionState::Open);
    }
}
