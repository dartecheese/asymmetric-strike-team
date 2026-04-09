import requests
import logging

def get_token_info(token_address):
    """
    Fetches the current price and symbol of a token in USD via DexScreener API.
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("pairs"):
            return None
            
        # Get the highest liquidity pair's info
        best_pair = max(data["pairs"], key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))
        price_usd = float(best_pair["priceUsd"])
        symbol = best_pair["baseToken"]["symbol"]
        
        return {"price": price_usd, "symbol": symbol}

    except Exception as e:
        logging.error(f"DexScreener API failure: {e}")
        return None

if __name__ == "__main__":
    pepe_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    info = get_token_info(pepe_address)
    print(f"PEPE Info: {info}")
