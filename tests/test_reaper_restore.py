import tempfile
from pathlib import Path

from agents.reaper import Reaper
from core.models import ExecutionOrder
from core.position_store import PositionStore


class _FakePosition:
    def __init__(self, token_address: str, chain: str, amount_usd: float, status: str = "ACTIVE"):
        self.token_address = token_address
        self.chain = chain
        self.amount_usd = amount_usd
        self.entry_value = amount_usd
        self.current_value = amount_usd
        self.peak_value = amount_usd
        self.entry_price_usd = 1.0
        self.last_price_usd = 1.0
        self.status = status
        self.pnl_pct = 0.0


def test_reaper_restores_active_positions():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "positions.json"
        store = PositionStore(store_path)

        positions = [
            _FakePosition("0x0000000000000000000000000000000000000001", "1", 100.0),
            _FakePosition("0x0000000000000000000000000000000000000002", "8453", 50.0, status="FREE_RIDE"),
            _FakePosition("0x0000000000000000000000000000000000000003", "56", 25.0),
        ]
        for pos in positions:
            store.save_position(pos)

        reaper = Reaper(paper_mode=True, store_path=store_path)

        assert len(reaper.positions) == 3
        assert set(reaper.positions.keys()) == {
            "0x0000000000000000000000000000000000000001",
            "0x0000000000000000000000000000000000000002",
            "0x0000000000000000000000000000000000000003",
        }
        assert reaper.positions["0x0000000000000000000000000000000000000002"].status == "FREE_RIDE"
