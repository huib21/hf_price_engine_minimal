import requests
import time

# Symbols die jij wilt tracken
TOKENS = [
    "SOL", "USDC", "ETH", "USDT",
    "BONK", "JUP", "RAY", "ORCA",
    "BTC",
]

# Mapping van symbol -> CoinGecko ID
COINGECKO_IDS = {
    "SOL":  "solana",
    "USDC": "usd-coin",
    "ETH":  "ethereum",
    "USDT": "tether",
    "BONK": "bonk",
    "JUP":  "jupiter-exchange",
    "RAY":  "raydium",
    "ORCA": "orca",
    "BTC":  "bitcoin",
}

ID_LIST = ",".join(COINGECKO_IDS[s] for s in TOKENS)
API_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    f"?ids={ID_LIST}&vs_currencies=usd"
)

class HFPriceService:
    def get_prices(self):
        r = requests.get(API_URL, timeout=3)
        r.raise_for_status()
        data = r.json()

        prices = {}

        for sym in TOKENS:
            cid = COINGECKO_IDS[sym]
            if cid in data and "usd" in data[cid]:
                prices[sym] = float(data[cid]["usd"])

        # Stablecoins forceren op 1.0 als je dat wilt
        for stable in ["USDC", "USDT"]:
            if stable in prices:
                prices[stable] = 1.0

        return prices

    def run(self):
        print("HF CoinGecko Engine Running...\n")

        while True:
            try:
                prices = self.get_prices()
                print(prices)
            except Exception as e:
                print("Error fetching prices:", e)
                print("{}")
            time.sleep(1)  # 1 Hz; voor HF kun je dit later verlagen

if __name__ == "__main__":
    HFPriceService().run()
