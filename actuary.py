import requests
import logging

def check_token_security(chain_id, token_address):
    """
    Queries GoPlus Security API to check if a token is a honeypot or has crazy taxes.
    Chain IDs: 1 (Ethereum), 56 (BSC), 42161 (Arbitrum), 8453 (Base)
    """
    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 1 or not data.get("result"):
            logging.error(f"GoPlus API Error or Token not found: {data.get('message')}")
            return None
            
        token_data = data["result"][token_address.lower()]
        
        # Actuary Risk Heuristics
        is_honeypot = token_data.get("is_honeypot") == "1"
        is_open_source = token_data.get("is_open_source") == "1"
        
        # Taxes are often returned as strings like "0.01" for 1% or sometimes empty
        buy_tax_str = token_data.get("buy_tax", "1.0")
        sell_tax_str = token_data.get("sell_tax", "1.0")
        buy_tax = float(buy_tax_str) * 100 if buy_tax_str else 100.0
        sell_tax = float(sell_tax_str) * 100 if sell_tax_str else 100.0
        
        risk_report = {
            "is_honeypot": is_honeypot,
            "buy_tax": buy_tax,
            "sell_tax": sell_tax,
            "is_open_source": is_open_source,
            "safe": not is_honeypot and is_open_source and buy_tax <= 10.0 and sell_tax <= 10.0
        }
        
        return risk_report

    except Exception as e:
        logging.error(f"Actuary GoPlus API failure: {e}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Testing with PEPE token on Ethereum
    pepe_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    print(f"Checking PEPE: {pepe_address}")
    report = check_token_security("1", pepe_address)
    print(report)
