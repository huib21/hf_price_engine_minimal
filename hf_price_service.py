import requests
import time

TOKENS = ["SOL", "USDC", "ETH", "USDT", "BONK", "JUP", "RAY", "ORCA"]

API_URL = "https://quote-api.jup.ag/v6/price?ids=" + ",".join(TOKENS)

class HFPriceService:
    def run(self):
        print("HF Jupiter Engine Running...\n")

        while True:
            try:
                r = requests.get(API_URL, timeout=5)
                r.raise_for_status()
                data = r.json()

                # Jupiter returns structure:
                # { "data": { "SOL": {...}, "USDC": {...}, ... } }
                out = {}

                for t in TOKENS:
                    if t in data.get("data", {}):
                        out[t] = data["data"][t]["price"]

                print(out)

            except Exception as e:
                print("Error:", e)
                print("{}")

            time.sleep(1)

if __name__ == "__main__":
    HFPriceService().run()
