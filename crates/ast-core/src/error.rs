use thiserror::Error;

#[derive(Debug, Error)]
pub enum CoreError {
    #[error("configuration error: {0}")]
    Config(#[from] config::ConfigError),
    #[error("missing required environment variable: {0}")]
    MissingEnvVar(&'static str),
    #[error("validation error: {0}")]
    Validation(String),
}
