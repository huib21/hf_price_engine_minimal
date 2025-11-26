import requests
import time

TOKENS = ["SOL", "USDC", "ETH", "USDT", "BONK", "JUP", "RAY", "ORCA"]

API_URL = "https://api.jup.ag/price/v2?ids=" + ",".join(TOKENS)

class HFPriceService:
    def run(self):
        print("HF Jupiter Engine Running...\n")

        while True:
            try:
                r = requests.get(API_URL, timeout=5)
                r.raise_for_status()
                data = r.json()

                prices = {t: data[t]["price"] for t in TOKENS if t in data}

                print(prices)

            except Exception as e:
                print("Error:", e)
                print("{}")

            time.sleep(1)

if __name__ == "__main__":
    HFPriceService().run()
