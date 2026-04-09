import requests
import logging

# Maps DexScreener chain names to GoPlus API chain IDs
SUPPORTED_CHAINS = {
    "ethereum": "1",
    "bsc": "56",
    "arbitrum": "42161",
    "base": "8453"
}

class Whisperer:
    def __init__(self):
        self.seen_tokens = set()

    def scan_latest_profiles(self):
        """Scans DexScreener for newly updated token profiles across supported EVM chains."""
        logging.info("🗣️  [Whisperer] Scanning DexScreener for newly updated EVM tokens...")
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            new_tokens = []
            for profile in data:
                chain = profile.get("chainId")
                address = profile.get("tokenAddress")
                
                if chain in SUPPORTED_CHAINS and address not in self.seen_tokens:
                    self.seen_tokens.add(address)
                    new_tokens.append({
                        "token_address": address,
                        "chain_name": chain,
                        "goplus_chain_id": SUPPORTED_CHAINS[chain],
                        "description": profile.get("description", "")
                    })
            
            if new_tokens:
                logging.info(f"🗣️  [Whisperer] Found {len(new_tokens)} new EVM targets!")
            return new_tokens
            
        except Exception as e:
            logging.error(f"🗣️  [Whisperer] API failure: {e}")
            return []
