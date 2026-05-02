use rust_decimal::Decimal;

use crate::SlingerError;

type Result<T> = std::result::Result<T, SlingerError>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlippageCheck {
    pub expected_out: Decimal,
    pub minimum_out: Decimal,
    pub actual_out: Decimal,
    pub observed_bps: u32,
}

pub struct SlippageGuard;

impl SlippageGuard {
    pub fn minimum_output(expected_out: Decimal, max_slippage_bps: u32) -> Result<Decimal> {
        if expected_out.is_sign_negative() || expected_out.is_zero() {
            return Err(SlingerError::OrderValidation(
                "expected output must be greater than zero".into(),
            ));
        }

        let max_bps = Decimal::from(10_000u32);
        let slippage = Decimal::from(max_slippage_bps);
        Ok(expected_out * (max_bps - slippage) / max_bps)
    }

    pub fn evaluate(
        expected_out: Decimal,
        actual_out: Decimal,
        max_slippage_bps: u32,
    ) -> Result<SlippageCheck> {
        if actual_out.is_sign_negative() {
            return Err(SlingerError::OrderValidation(
                "actual output must be non-negative".into(),
            ));
        }

        let minimum_out = Self::minimum_output(expected_out, max_slippage_bps)?;
        let observed_bps = ((expected_out - actual_out) / expected_out * Decimal::from(10_000u32))
            .round_dp(0)
            .to_u32()
            .ok_or_else(|| SlingerError::OrderValidation("failed to compute slippage in bps".into()))?;

        if actual_out < minimum_out {
            return Err(SlingerError::SlippageExceeded {
                observed_bps,
                max_bps: max_slippage_bps,
            });
        }

        Ok(SlippageCheck {
            expected_out,
            minimum_out,
            actual_out,
            observed_bps,
        })
    }
}

trait DecimalExt {
    fn to_u32(&self) -> Option<u32>;
}

impl DecimalExt for Decimal {
    fn to_u32(&self) -> Option<u32> {
        rust_decimal::prelude::ToPrimitive::to_u32(self)
    }
}

#[cfg(test)]
mod tests {
    use rust_decimal::Decimal;

    use super::SlippageGuard;

    #[test]
    fn computes_amount_out_minimum_from_bps_budget() {
        let min_out = SlippageGuard::minimum_output(Decimal::new(1_000, 0), 300)
            .expect("minimum output should compute");

        assert_eq!(min_out, Decimal::new(970, 0));
    }

    #[test]
    fn rejects_swap_when_slippage_exceeds_budget() {
        let result = SlippageGuard::evaluate(Decimal::new(1_000, 0), Decimal::new(950, 0), 300);

        assert!(result.is_err());
    }
}
