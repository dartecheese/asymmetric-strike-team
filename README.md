# Asymmetric Strike Team

A high-risk, high-reward ("degen") DeFi trading system powered by an autonomous 4-agent assembly. Designed to capitalize on fast-moving social narratives while enforcing ruthless capital preservation rules.

## The Assembly

1. **The Whisperer**: Scans social firehoses (Twitter, Telegram, DexScreener) for narrative spikes and smart money velocity.
2. **The Actuary**: Rapid heuristic security auditor. Uses GoPlus API to check for honeypots and excessive taxes.
3. **The Slinger**: Direct Web3 execution. Bypasses UIs, constructing raw router calldata (Uniswap V2, etc.) with high slippage tolerances to guarantee block inclusion.
4. **The Reaper**: Portfolio defense monitor. Executes a strict "Free Ride" protocol (extract principal at +100%) and a kill-switch stop loss (liquidate at -30%).

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set up your `.env`:
```
RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
PRIVATE_KEY=your_private_key_here  # Optional for live execution
```

## Running the Assembly

```bash
python main.py
```

## Architecture Notes
- Uses `web3.py` for direct calldata generation to eliminate UI frontend latency.
- Uses `pydantic` for rigid inter-agent communication data models.

*Disclaimer: This is experimental software for high-risk DeFi environments. Use at your own risk.*