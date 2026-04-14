use ast_core::{Result, RiskAssessment, Signal, Venue};
use async_trait::async_trait;

#[async_trait]
pub trait VenueResolver: Send + Sync {
    async fn resolve_venue(&self, signal: &Signal, risk: &RiskAssessment) -> Result<Venue>;
}

#[derive(Debug, Clone)]
pub struct StaticVenueResolver {
    venue: Venue,
}

impl StaticVenueResolver {
    pub fn new(venue: Venue) -> Self {
        Self { venue }
    }
}

#[async_trait]
impl VenueResolver for StaticVenueResolver {
    async fn resolve_venue(&self, _signal: &Signal, _risk: &RiskAssessment) -> Result<Venue> {
        Ok(self.venue.clone())
    }
}
