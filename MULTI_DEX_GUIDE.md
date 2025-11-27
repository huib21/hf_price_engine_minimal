# Multi-DEX Price Engine for Solana Arbitrage

## Overview

This enhanced price engine fetches prices from **multiple Solana DEXes simultaneously** and detects arbitrage opportunities in real-time. Perfect for high-frequency trading bots.

## DEX Sources

The engine fetches from these sources **in parallel** for minimal latency:

1. **Jupiter** - Aggregated prices from all major DEXes (best overall coverage)
2. **Raydium** - Major AMM DEX with deep liquidity
3. **Orca** - Whirlpool AMM with concentrated liquidity
4. **Birdeye** - Multi-source aggregator (optional API key)
5. **Meteora** - DLMM (Dynamic Liquidity Market Maker)

## Key Features

### 1. Parallel Fetching
All DEX APIs are queried simultaneously using `asyncio.gather()` for sub-second latency.

### 2. Arbitrage Detection
Automatically detects price spreads across DEXes:
```
SOL:
  Buy  @ Raydium    : $102.345000
  Sell @ Jupiter    : $102.567000
  💰 Potential profit: 0.217% (before fees)
```

### 3. Price Statistics
Shows min/max/average prices and spreads for each token:
```
SOL:
  Avg: $102.450000  |  Min: $102.345000  |  Max: $102.567000  |  Spread: 0.217%
    Raydium     : $102.345000  (-0.102%)
    Orca        : $102.456000  (+0.006%)
    Jupiter     : $102.567000  (+0.114%)
```

### 4. JSON Export
All prices and opportunities are saved to `multi_dex_prices.json` for downstream processing:
```json
{
  "timestamp": 1735123456.789,
  "prices": {
    "SOL": [
      {"dex": "Jupiter", "price": 102.567, "confidence": "high"},
      {"dex": "Raydium", "price": 102.345, "confidence": "high"}
    ]
  },
  "arbitrage_opportunities": [...]
}
```

## Installation

```bash
pip install aiohttp
```

## Usage

### Basic Usage
```bash
python multi_dex_prices.py
```

### With Birdeye API Key (Recommended)
Edit `multi_dex_prices.py` and set your API key:
```python
birdeye_key = "your-api-key-here"  # Get free key at birdeye.so
```

### Configuration Options

In the `main()` function:

```python
await engine.run(
    interval=2,           # Update every 2 seconds
    min_spread_pct=0.3    # Only report spreads > 0.3%
)
```

**For HF arbitrage:**
- Use `interval=1` or `interval=2` for fast updates
- Set `min_spread_pct=0.2` to catch smaller opportunities
- Lower timeout to `timeout=2` for faster failures

## Architecture

### Class Structure

```
MultiDexPriceEngine
├── fetch_jupiter_prices()    → List[PriceQuote]
├── fetch_raydium_prices()    → List[PriceQuote]
├── fetch_orca_prices()       → List[PriceQuote]
├── fetch_birdeye_prices()    → List[PriceQuote]
├── fetch_meteora_prices()    → List[PriceQuote]
├── fetch_all_prices()        → Dict[token, List[PriceQuote]]
├── detect_arbitrage()        → List[ArbitrageOpportunity]
└── run()                     → Main loop
```

### Data Flow

```
┌─────────────────────────────────────────┐
│  Parallel Fetch (asyncio.gather)       │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │ Jupiter │  │ Raydium  │  │  Orca  │ │
│  └────┬────┘  └─────┬────┘  └────┬───┘ │
└───────┼─────────────┼────────────┼─────┘
        │             │            │
        ▼             ▼            ▼
    ┌───────────────────────────────────┐
    │  Aggregate by Token               │
    │  {"SOL": [quote1, quote2, ...]}   │
    └──────────────┬────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌────────────────┐    ┌──────────────────┐
│ Calculate      │    │ Detect Arbitrage │
│ Statistics     │    │ Opportunities    │
└───────┬────────┘    └────────┬─────────┘
        │                      │
        ▼                      ▼
    ┌────────────────────────────┐
    │  Display & Save to JSON    │
    └────────────────────────────┘
```

## Adding More DEX Sources

To add a new DEX source:

1. **Create a fetch function:**
```python
async def fetch_newdex_prices(self) -> List[PriceQuote]:
    quotes = []
    try:
        url = "https://api.newdex.com/prices"
        async with self.session.get(url, timeout=self.timeout) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Parse and create PriceQuote objects
                for token_symbol, mint in TOKEN_MINTS.items():
                    if mint in data:
                        quotes.append(PriceQuote(
                            dex="NewDex",
                            token=token_symbol,
                            price=float(data[mint]),
                            timestamp=time.time()
                        ))
        print(f"✓ NewDex: {len(quotes)} prices")
    except Exception as e:
        print(f"✗ NewDex: {e}")
    return quotes
```

2. **Add to parallel fetch:**
```python
tasks = [
    self.fetch_jupiter_prices(),
    self.fetch_raydium_prices(),
    self.fetch_newdex_prices(),  # Add here
    # ...
]
```

## Performance Tips

### For High-Frequency Arbitrage:

1. **Use faster intervals:**
   ```python
   await engine.run(interval=1, min_spread_pct=0.2)
   ```

2. **Reduce timeout:**
   ```python
   engine = MultiDexPriceEngine(timeout=2)
   ```

3. **Filter DEX sources:**
   Only fetch from DEXes with good liquidity for your tokens

4. **Combine with WebSocket:**
   Use this for polling + WebSocket subscriptions for critical pairs (see `hf_price_service.py`)

5. **Process in separate thread:**
   Run arbitrage calculations in separate process while this fetches prices

## Integration with Trading Bot

### Option 1: Direct Integration
```python
async with MultiDexPriceEngine() as engine:
    await engine.fetch_all_prices()
    opportunities = engine.detect_arbitrage(min_spread_pct=0.5)

    for opp in opportunities:
        await execute_arbitrage_trade(opp)
```

### Option 2: File-based Communication
```python
# Price engine writes to multi_dex_prices.json
# Trading bot reads from file and executes

while True:
    with open("multi_dex_prices.json") as f:
        data = json.load(f)

    for opp in data["arbitrage_opportunities"]:
        if opp["spread_pct"] > THRESHOLD:
            execute_trade(opp)
```

### Option 3: Shared Memory/Queue
Use `multiprocessing.Queue` or shared memory for fastest IPC:
```python
from multiprocessing import Queue

price_queue = Queue()

# Price engine
await engine.fetch_all_prices()
price_queue.put(engine.all_prices)

# Trading bot
prices = price_queue.get()
```

## Troubleshooting

### No prices from certain DEXes
- Check if API is down: `curl https://api.raydium.io/v2/main/price`
- Increase timeout: `MultiDexPriceEngine(timeout=5)`
- Some DEXes may require API keys

### High latency
- Reduce number of DEX sources
- Use faster RPC endpoint
- Consider WebSocket subscriptions for critical pairs

### Rate limiting
- Add delays between requests
- Use API keys where available (Birdeye, Jupiter Premium)
- Implement exponential backoff

## Next Steps

1. **WebSocket Integration**: Combine with `hf_price_service.py` for real-time updates
2. **On-chain Verification**: Add Solana RPC calls to verify pool reserves
3. **Fee Calculation**: Factor in DEX fees, slippage, and transaction costs
4. **Execution Engine**: Add automated trade execution
5. **Risk Management**: Add position sizing and stop-loss logic

## Resources

- Jupiter API: https://station.jup.ag/docs/apis/price-api
- Raydium API: https://docs.raydium.io/raydium/
- Orca API: https://docs.orca.so/
- Birdeye API: https://docs.birdeye.so/
