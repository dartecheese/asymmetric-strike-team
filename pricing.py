import logging
import requests


def get_token_info(token_address):
    """
    Fetch token market metadata via DexScreener.

    Returns the highest-liquidity pair with useful fields for charting/UI.
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        pairs = data.get("pairs") or []
        if not pairs:
            return None

        def liquidity_usd(pair):
            try:
                return float((pair.get("liquidity") or {}).get("usd") or 0)
            except Exception:
                return 0.0

        best_pair = max(pairs, key=liquidity_usd)
        liquidity = best_pair.get("liquidity") or {}
        volume = best_pair.get("volume") or {}
        price_change = best_pair.get("priceChange") or {}
        base = best_pair.get("baseToken") or {}
        quote = best_pair.get("quoteToken") or {}

        return {
            "price": float(best_pair.get("priceUsd") or 0),
            "symbol": base.get("symbol") or token_address[:8],
            "name": base.get("name") or base.get("symbol") or token_address[:8],
            "chain_id": best_pair.get("chainId") or "ethereum",
            "dex_id": best_pair.get("dexId") or "unknown",
            "pair_address": best_pair.get("pairAddress"),
            "pair_url": best_pair.get("url"),
            "image_url": ((best_pair.get("info") or {}).get("imageUrl")),
            "website": (((best_pair.get("info") or {}).get("websites") or [{}])[0].get("url") if (best_pair.get("info") or {}).get("websites") else None),
            "labels": best_pair.get("labels") or [],
            "liquidity_usd": float(liquidity.get("usd") or 0),
            "fdv": float(best_pair.get("fdv") or 0),
            "market_cap": float(best_pair.get("marketCap") or 0),
            "volume_h24": float(volume.get("h24") or 0),
            "volume_h6": float(volume.get("h6") or 0),
            "volume_h1": float(volume.get("h1") or 0),
            "buys_h24": int(((best_pair.get("txns") or {}).get("h24") or {}).get("buys") or 0),
            "sells_h24": int(((best_pair.get("txns") or {}).get("h24") or {}).get("sells") or 0),
            "price_change_m5": float(price_change.get("m5") or 0),
            "price_change_h1": float(price_change.get("h1") or 0),
            "price_change_h6": float(price_change.get("h6") or 0),
            "price_change_h24": float(price_change.get("h24") or 0),
            "base_symbol": base.get("symbol"),
            "quote_symbol": quote.get("symbol"),
            "raw_pair": best_pair,
        }

    except Exception as e:
        logging.error(f"DexScreener API failure: {e}")
        return None


if __name__ == "__main__":
    pepe_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    info = get_token_info(pepe_address)
    print(f"PEPE Info: {info}")
