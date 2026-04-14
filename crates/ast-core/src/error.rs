use thiserror::Error;

#[derive(Debug, Error)]
pub enum AstError {
    #[error("configuration error: {0}")]
    Config(String),
    #[error("invalid transition from {from} to {to}")]
    InvalidTransition { from: &'static str, to: &'static str },
    #[error("validation error: {0}")]
    Validation(String),
}

pub type Result<T> = std::result::Result<T, AstError>;
