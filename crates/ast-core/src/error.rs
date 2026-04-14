use thiserror::Error;

#[derive(Debug, Error)]
pub enum AstError {
    #[error("configuration error: {0}")]
    Config(String),
    #[error("invalid transition from {from} to {to}")]
    InvalidTransition { from: &'static str, to: &'static str },
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("persistence corruption: {0}")]
    PersistenceCorruption(String),
    #[error("serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    #[error("validation error: {0}")]
    Validation(String),
}

pub type Result<T> = std::result::Result<T, AstError>;
