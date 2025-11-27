"""
Quick test of multi-DEX price engine
Runs one iteration and exits
"""

import asyncio
from multi_dex_prices import MultiDexPriceEngine


async def test_run():
    """Run one iteration to test"""
    print("Testing Multi-DEX Price Engine...\n")

    async with MultiDexPriceEngine(timeout=5) as engine:
        # Fetch prices once
        await engine.fetch_all_prices()

        # Display prices
        engine.display_prices()

        # Detect arbitrage
        opportunities = engine.detect_arbitrage(min_spread_pct=0.1)
        engine.display_arbitrage(opportunities)

        # Save to file
        await engine.save_to_file(opportunities)

    print("\n✓ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_run())
