"""
Multi-DEX Price Engine for Solana Arbitrage Bot
Fetches prices from multiple DEXes simultaneously and detects arbitrage opportunities
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Token mint addresses on Solana
TOKEN_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
}

@dataclass
class PriceQuote:
    """Single price quote from a DEX"""
    dex: str
    token: str
    price: float
    timestamp: float
    confidence: str = "high"  # high, medium, low

@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity"""
    token: str
    buy_dex: str
    buy_price: float
    sell_dex: str
    sell_price: float
    spread_pct: float
    timestamp: float


class MultiDexPriceEngine:
    """
    Fetches prices from multiple Solana DEXes in parallel
    Designed for high-frequency arbitrage detection
    """

    def __init__(self, birdeye_api_key: Optional[str] = None, timeout: int = 3):
        self.birdeye_api_key = birdeye_api_key or "public"
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.all_prices: Dict[str, List[PriceQuote]] = {}  # token -> [quotes from different DEXes]

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # ========================================================================
    # JUPITER AGGREGATED PRICES (Best overall price aggregation)
    # ========================================================================
    async def fetch_jupiter_prices(self) -> List[PriceQuote]:
        """
        Jupiter Price API v4 - Aggregated prices from all major DEXes
        This is often the best source as Jupiter aggregates multiple DEXes
        """
        quotes = []
        try:
            token_ids = ",".join(TOKEN_MINTS.values())
            url = f"https://price.jup.ag/v4/price?ids={token_ids}"

            async with self.session.get(url, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    for token_symbol, mint in TOKEN_MINTS.items():
                        if mint in data.get("data", {}):
                            price_data = data["data"][mint]
                            quotes.append(PriceQuote(
                                dex="Jupiter",
                                token=token_symbol,
                                price=float(price_data["price"]),
                                timestamp=time.time(),
                                confidence="high"
                            ))

                    print(f"✓ Jupiter: {len(quotes)} prices")
                else:
                    print(f"✗ Jupiter: HTTP {resp.status}")

        except asyncio.TimeoutError:
            print("✗ Jupiter: Timeout")
        except Exception as e:
            print(f"✗ Jupiter: {e}")

        return quotes

    # ========================================================================
    # RAYDIUM PRICES (Major AMM DEX)
    # ========================================================================
    async def fetch_raydium_prices(self) -> List[PriceQuote]:
        """Raydium API - Direct AMM prices"""
        quotes = []
        try:
            url = "https://api.raydium.io/v2/main/price"

            async with self.session.get(url, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    for token_symbol, mint in TOKEN_MINTS.items():
                        if mint in data:
                            quotes.append(PriceQuote(
                                dex="Raydium",
                                token=token_symbol,
                                price=float(data[mint]),
                                timestamp=time.time(),
                                confidence="high"
                            ))

                    print(f"✓ Raydium: {len(quotes)} prices")
                else:
                    print(f"✗ Raydium: HTTP {resp.status}")

        except asyncio.TimeoutError:
            print("✗ Raydium: Timeout")
        except Exception as e:
            print(f"✗ Raydium: {e}")

        return quotes

    # ========================================================================
    # ORCA PRICES (Major AMM DEX with Whirlpools)
    # ========================================================================
    async def fetch_orca_prices(self) -> List[PriceQuote]:
        """Orca API - Whirlpool prices"""
        quotes = []
        try:
            # Orca token price API
            url = "https://api.mainnet.orca.so/v1/token/list"

            async with self.session.get(url, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Create mint to price mapping
                    price_map = {}
                    for token_data in data.get("tokens", []):
                        if "mint" in token_data and "usdPrice" in token_data:
                            price_map[token_data["mint"]] = token_data["usdPrice"]

                    for token_symbol, mint in TOKEN_MINTS.items():
                        if mint in price_map and price_map[mint]:
                            quotes.append(PriceQuote(
                                dex="Orca",
                                token=token_symbol,
                                price=float(price_map[mint]),
                                timestamp=time.time(),
                                confidence="high"
                            ))

                    print(f"✓ Orca: {len(quotes)} prices")
                else:
                    print(f"✗ Orca: HTTP {resp.status}")

        except asyncio.TimeoutError:
            print("✗ Orca: Timeout")
        except Exception as e:
            print(f"✗ Orca: {e}")

        return quotes

    # ========================================================================
    # BIRDEYE PRICES (Aggregator with good coverage)
    # ========================================================================
    async def fetch_birdeye_prices(self) -> List[PriceQuote]:
        """Birdeye API - Multi-chain price aggregator"""
        quotes = []
        try:
            token_list = ",".join(TOKEN_MINTS.values())
            url = f"https://public-api.birdeye.so/public/multi_price?list_address={token_list}"

            headers = {"X-API-KEY": self.birdeye_api_key}

            async with self.session.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if data.get("success") and "data" in data:
                        price_data = data["data"]

                        for token_symbol, mint in TOKEN_MINTS.items():
                            if mint in price_data:
                                price = price_data[mint].get("value", 0)
                                if price > 0:
                                    quotes.append(PriceQuote(
                                        dex="Birdeye",
                                        token=token_symbol,
                                        price=float(price),
                                        timestamp=time.time(),
                                        confidence="high"
                                    ))

                    print(f"✓ Birdeye: {len(quotes)} prices")
                else:
                    print(f"✗ Birdeye: HTTP {resp.status}")

        except asyncio.TimeoutError:
            print("✗ Birdeye: Timeout")
        except Exception as e:
            print(f"✗ Birdeye: {e}")

        return quotes

    # ========================================================================
    # METEORA DLMM PRICES (Dynamic Liquidity Market Maker)
    # ========================================================================
    async def fetch_meteora_prices(self) -> List[PriceQuote]:
        """Meteora DLMM - Advanced AMM with concentrated liquidity"""
        quotes = []
        try:
            # Meteora pairs API
            url = "https://dlmm-api.meteora.ag/pair/all_by_groups"

            async with self.session.get(url, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Parse pairs and extract prices
                    # This is a simplified version - in production you'd need more sophisticated parsing
                    for group in data.get("groups", []):
                        for pair in group.get("pairs", []):
                            mint_x = pair.get("mint_x")
                            mint_y = pair.get("mint_y")

                            # Check if we have these tokens and if there's price data
                            # Note: Meteora provides pool data, you'd need to calculate price from reserves
                            pass

                    print(f"✓ Meteora: {len(quotes)} prices")
                else:
                    print(f"✗ Meteora: HTTP {resp.status}")

        except asyncio.TimeoutError:
            print("✗ Meteora: Timeout")
        except Exception as e:
            print(f"✗ Meteora: {e}")

        return quotes

    # ========================================================================
    # FETCH ALL SOURCES IN PARALLEL
    # ========================================================================
    async def fetch_all_prices(self) -> Dict[str, List[PriceQuote]]:
        """
        Fetch prices from all DEX sources in parallel
        Returns: {token_symbol: [PriceQuote, PriceQuote, ...]}
        """
        print(f"\n{'='*80}")
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Fetching prices from all DEXes...")
        print('-'*80)

        # Fetch from all sources in parallel for minimum latency
        tasks = [
            self.fetch_jupiter_prices(),
            self.fetch_raydium_prices(),
            self.fetch_orca_prices(),
            self.fetch_birdeye_prices(),
            self.fetch_meteora_prices(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate all quotes by token
        all_quotes: Dict[str, List[PriceQuote]] = {token: [] for token in TOKEN_MINTS.keys()}

        for result in results:
            if isinstance(result, list):
                for quote in result:
                    all_quotes[quote.token].append(quote)

        # Override stablecoins to 1.0
        for stable in ["USDC", "USDT"]:
            if stable in all_quotes:
                for quote in all_quotes[stable]:
                    quote.price = 1.0

        self.all_prices = all_quotes
        return all_quotes

    # ========================================================================
    # ARBITRAGE DETECTION
    # ========================================================================
    def detect_arbitrage(self, min_spread_pct: float = 0.5) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities across DEXes
        min_spread_pct: Minimum spread percentage to report (e.g., 0.5 = 0.5%)
        """
        opportunities = []

        for token, quotes in self.all_prices.items():
            if len(quotes) < 2:
                continue

            # Find min and max prices
            quotes_sorted = sorted(quotes, key=lambda q: q.price)
            min_quote = quotes_sorted[0]
            max_quote = quotes_sorted[-1]

            # Calculate spread
            spread_pct = ((max_quote.price - min_quote.price) / min_quote.price) * 100

            if spread_pct >= min_spread_pct:
                opportunities.append(ArbitrageOpportunity(
                    token=token,
                    buy_dex=min_quote.dex,
                    buy_price=min_quote.price,
                    sell_dex=max_quote.dex,
                    sell_price=max_quote.price,
                    spread_pct=spread_pct,
                    timestamp=time.time()
                ))

        return opportunities

    # ========================================================================
    # DISPLAY FUNCTIONS
    # ========================================================================
    def display_prices(self):
        """Display all prices in a formatted table"""
        print(f"\n{'='*80}")
        print("💰 CURRENT PRICES ACROSS ALL DEXes")
        print('='*80)

        for token in sorted(TOKEN_MINTS.keys()):
            quotes = self.all_prices.get(token, [])

            if not quotes:
                print(f"\n{token}:")
                print(f"  ⚠️  No prices available")
                continue

            # Calculate statistics
            prices = [q.price for q in quotes]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            spread_pct = ((max_price - min_price) / min_price * 100) if min_price > 0 else 0

            print(f"\n{token}:")
            print(f"  Avg: ${avg_price:>12.6f}  |  Min: ${min_price:>12.6f}  |  Max: ${max_price:>12.6f}  |  Spread: {spread_pct:>6.3f}%")

            # Show all DEX prices
            for quote in sorted(quotes, key=lambda q: q.price):
                deviation = ((quote.price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                print(f"    {quote.dex:12s}: ${quote.price:>12.6f}  ({deviation:+6.3f}%)")

    def display_arbitrage(self, opportunities: List[ArbitrageOpportunity]):
        """Display detected arbitrage opportunities"""
        if not opportunities:
            print("\n✓ No significant arbitrage opportunities detected")
            return

        print(f"\n{'='*80}")
        print("🎯 ARBITRAGE OPPORTUNITIES DETECTED")
        print('='*80)

        for opp in sorted(opportunities, key=lambda o: o.spread_pct, reverse=True):
            print(f"\n{opp.token}:")
            print(f"  Buy  @ {opp.buy_dex:12s}: ${opp.buy_price:>12.6f}")
            print(f"  Sell @ {opp.sell_dex:12s}: ${opp.sell_price:>12.6f}")
            print(f"  💰 Potential profit: {opp.spread_pct:>6.3f}% (before fees)")

    # ========================================================================
    # SAVE TO FILE
    # ========================================================================
    async def save_to_file(self, opportunities: List[ArbitrageOpportunity]):
        """Save prices and opportunities to JSON file"""
        data = {
            "timestamp": time.time(),
            "formatted_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "prices": {
                token: [
                    {
                        "dex": q.dex,
                        "price": q.price,
                        "timestamp": q.timestamp,
                        "confidence": q.confidence
                    }
                    for q in quotes
                ]
                for token, quotes in self.all_prices.items()
            },
            "arbitrage_opportunities": [
                {
                    "token": opp.token,
                    "buy_dex": opp.buy_dex,
                    "buy_price": opp.buy_price,
                    "sell_dex": opp.sell_dex,
                    "sell_price": opp.sell_price,
                    "spread_pct": opp.spread_pct,
                    "timestamp": opp.timestamp
                }
                for opp in opportunities
            ]
        }

        try:
            with open("multi_dex_prices.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n✓ Saved to multi_dex_prices.json")
        except Exception as e:
            print(f"\n✗ Error saving to file: {e}")

    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    async def run(self, interval: int = 2, min_spread_pct: float = 0.3):
        """
        Main execution loop
        interval: Seconds between updates (2s recommended for HF arbitrage)
        min_spread_pct: Minimum spread to report (0.3% = 30 basis points)
        """
        print("=" * 80)
        print("SOLANA MULTI-DEX PRICE ENGINE FOR HF ARBITRAGE")
        print("=" * 80)
        print(f"Tracking: {', '.join(TOKEN_MINTS.keys())}")
        print(f"Update interval: {interval}s")
        print(f"Min spread threshold: {min_spread_pct}%")
        print(f"DEX Sources: Jupiter, Raydium, Orca, Birdeye, Meteora")
        print("=" * 80)

        iteration = 0

        while True:
            try:
                iteration += 1

                # Fetch all prices in parallel
                await self.fetch_all_prices()

                # Display prices
                self.display_prices()

                # Detect arbitrage
                opportunities = self.detect_arbitrage(min_spread_pct)
                self.display_arbitrage(opportunities)

                # Save to file
                await self.save_to_file(opportunities)

                print(f"\n[Iteration {iteration}] Waiting {interval}s before next update...")
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                print("\n\n🛑 Stopping price engine...")
                break
            except Exception as e:
                print(f"\n❌ Error in main loop: {e}")
                await asyncio.sleep(interval)


# ============================================================================
# MAIN EXECUTION
# ============================================================================
async def main():
    """Main entry point"""

    # Optional: Set your Birdeye API key for better rate limits
    # Get free key at: https://birdeye.so
    birdeye_key = None  # or "your-api-key-here"

    async with MultiDexPriceEngine(birdeye_api_key=birdeye_key, timeout=3) as engine:
        # Run with 2 second interval and 0.3% minimum spread
        await engine.run(interval=2, min_spread_pct=0.3)


if __name__ == "__main__":
    """
    Installation:
    pip install aiohttp

    Usage:
    python multi_dex_prices.py
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
