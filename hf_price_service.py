import requests
import time

TOKENS = ["SOL", "USDC", "ETH", "USDT", "BONK", "JUP", "RAY", "ORCA"]

def get_prices(tokens):
    try:
        ids = ",".join(tokens)
        url = f"https://api.jup.ag/price/v2?ids={ids}"
        r = requests.get(url, timeout=2)
        r.raise_for_status()
        data = r.json()["data"]

        result = {}
        for t in tokens:
            if t in data and "price" in data[t]:
                result[t] = data[t]["price"]

        return result

    except Exception as e:
        print("Error:", e)
        return {}

print("HF Jupiter Engine Running...\n")

while True:
    prices = get_prices(TOKENS)
    print(prices)
    time.sleep(1)
