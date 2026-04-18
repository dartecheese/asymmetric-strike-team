#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
import time

def test_goplus_api():
    chain_id = "1"
    token_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    
    url = (
        f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
        f"?contract_addresses={token_address}"
    )
    print(f"URL: {url}")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AsymmetricStrikeTeam/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        
        print(f"Response code: {data.get('code')}")
        print(f"Message: {data.get('message')}")
        
        result = data.get("result", {})
        print(f"Result keys: {list(result.keys())}")
        
        # Try both lowercased and original
        token_data = result.get(token_address.lower()) or result.get(token_address)
        print(f"Token data found: {token_data is not None}")
        
        if token_data:
            print(f"Sample fields:")
            print(f"  is_honeypot: {token_data.get('is_honeypot')}")
            print(f"  buy_tax: {token_data.get('buy_tax')}")
            print(f"  sell_tax: {token_data.get('sell_tax')}")
            print(f"  is_open_source: {token_data.get('is_open_source')}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_goplus_api()