import requests
import time

# Tokens die jij wilt tracken
TOKENS = [
    "SOL",
    "USDC",
    "ETH",
    "USDT",
    "BONK",
    "JUP",
    "RAY",
    "ORCA",
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

BASE_INTERVAL = 3      # normale interval (sec)
BACKOFF_INTERVAL = 10  # extra wachtijd na 429


class HFPriceService:
    def get_prices(self):
        r = requests.get(API_URL, timeout=3)

        # Eenvoudige handling voor rate limiting
        if r.status_code == 429:
            print("Rate limited (429) door CoinGecko → backoff...")
            time.sleep(BACKOFF_INTERVAL)
            return {}

        r.raise_for_status()
        data = r.json()

        prices = {}

        for sym in TOKENS:
            cid = COINGECKO_IDS[sym]
            if cid in data and "usd" in data[cid]:
                prices[sym] = float(data[cid]["usd"])

        # Stablecoins forceren op 1.0 (altijd)
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

            time.sleep(BASE_INTERVAL)


if __name__ == "__main__":
    HFPriceService().run()

