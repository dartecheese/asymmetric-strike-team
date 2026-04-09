import requests
import json

def test_dexscreener_latest():
    url = "https://api.dexscreener.com/token-profiles/latest/v1"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data)} latest profiles.")
        if len(data) > 0:
            print(json.dumps(data[0], indent=2))
    else:
        print("Failed:", response.status_code)

if __name__ == "__main__":
    test_dexscreener_latest()
