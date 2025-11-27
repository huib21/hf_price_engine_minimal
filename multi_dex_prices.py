import asyncio
import aiohttp
import json
import ssl
from datetime import datetime
from typing import Dict, List, Optional

# SSL CONTEXT - Tijdelijke oplossing voor certificaat problemen
# WAARSCHUWING: Alleen voor development! Voor productie: los certificaat probleem op
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Configuration
TOKENS = {
    'SOL': 'So11111111111111111111111111111111111111112',
    'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
    'BONK': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
    'JUP': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
    'RAY': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
    'ORCA': 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE'
}

USDC_MINT = TOKENS['USDC']
UPDATE_INTERVAL = 2  # seconds
MIN_SPREAD_THRESHOLD = 0.003  # 0.3%

# API Endpoints - GECORRIGEERDE URLs
JUPITER_PRICE_URL = "https://api.jup.ag/price/v2"  # Nieuwe price API
JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
RAYDIUM_URL = "https://api-v3.raydium.io/pools/info/mint"
ORCA_WHIRLPOOL_URL = "https://api.mainnet.orca.so/v1/whirlpool/list"
BIRDEYE_URL = "https://public-api.birdeye.so/defi/price"
METEORA_URL = "https://dlmm-api.meteora.ag/pair/all"


class MultiDEXPriceTracker:
    def __init__(self):
        self.prices: Dict[str, Dict[str, float]] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        # Maak session met SSL context en timeout
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=20)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_jupiter_prices(self) -> Dict[str, float]:
        """Fetch prices from Jupiter - Nieuwe API v2"""
        try:
            # Jupiter Price API v2 - bulk request
            token_ids = ','.join(TOKENS.values())
            url = f"{JUPITER_PRICE_URL}?ids={token_ids}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    
                    # Parse nieuwe response format
                    if 'data' in data:
                        for symbol, mint in TOKENS.items():
                            if mint in data['data'] and 'price' in data['data'][mint]:
                                prices[symbol] = float(data['data'][mint]['price'])
                    
                    return prices
        except Exception as e:
            print(f"✗ Jupiter: {e}")
        return {}
    
    async def fetch_raydium_prices(self) -> Dict[str, float]:
        """Fetch prices from Raydium"""
        try:
            prices = {}
            
            for symbol, mint in TOKENS.items():
                if symbol in ['USDC', 'USDT']:
                    prices[symbol] = 1.0
                    continue
                
                url = f"{RAYDIUM_URL}?mint1={mint}&mint2={USDC_MINT}&poolType=all"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data') and len(data['data']) > 0:
                            pool = data['data'][0]
                            if 'price' in pool:
                                prices[symbol] = float(pool['price'])
            
            return prices
        except Exception as e:
            print(f"✗ Raydium: {e}")
        return {}
    
    async def fetch_orca_prices(self) -> Dict[str, float]:
        """Fetch prices from Orca Whirlpools"""
        try:
            async with self.session.get(ORCA_WHIRLPOOL_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    
                    if 'whirlpools' in data:
                        for pool in data['whirlpools']:
                            token_a = pool.get('tokenA', {}).get('mint')
                            token_b = pool.get('tokenB', {}).get('mint')
                            
                            # Match tegen onze tokens
                            for symbol, mint in TOKENS.items():
                                if mint == token_a and token_b == USDC_MINT:
                                    if 'price' in pool:
                                        prices[symbol] = float(pool['price'])
                                elif mint == token_b and token_a == USDC_MINT:
                                    if 'price' in pool:
                                        prices[symbol] = 1.0 / float(pool['price'])
                    
                    return prices
        except Exception as e:
            print(f"✗ Orca: {e}")
        return {}
    
    async def fetch_birdeye_prices(self) -> Dict[str, float]:
        """Fetch prices from Birdeye"""
        try:
            prices = {}
            
            for symbol, mint in TOKENS.items():
                url = f"{BIRDEYE_URL}?address={mint}"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data', {}).get('value'):
                            prices[symbol] = float(data['data']['value'])
            
            return prices
        except Exception as e:
            print(f"✗ Birdeye: {e}")
        return {}
    
    async def fetch_meteora_prices(self) -> Dict[str, float]:
        """Fetch prices from Meteora DLMM"""
        try:
            async with self.session.get(METEORA_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    
                    for pair in data:
                        mint_x = pair.get('mint_x')
                        mint_y = pair.get('mint_y')
                        
                        for symbol, mint in TOKENS.items():
                            if mint == mint_x and mint_y == USDC_MINT:
                                if 'current_price' in pair:
                                    prices[symbol] = float(pair['current_price'])
                            elif mint == mint_y and mint_x == USDC_MINT:
                                if 'current_price' in pair:
                                    prices[symbol] = 1.0 / float(pair['current_price'])
                    
                    return prices
        except Exception as e:
            print(f"✗ Meteora: {e}")
        return {}
    
    async def fetch_all_prices(self) -> Dict[str, Dict[str, float]]:
        """Fetch prices from all DEXes concurrently"""
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Fetching prices from all DEXes...")
        
        # Voer alle fetches parallel uit
        results = await asyncio.gather(
            self.fetch_jupiter_prices(),
            self.fetch_raydium_prices(),
            self.fetch_orca_prices(),
            self.fetch_birdeye_prices(),
            self.fetch_meteora_prices(),
            return_exceptions=True
        )
        
        # Parse results
        dex_prices = {
            'Jupiter': results[0] if not isinstance(results[0], Exception) else {},
            'Raydium': results[1] if not isinstance(results[1], Exception) else {},
            'Orca': results[2] if not isinstance(results[2], Exception) else {},
            'Birdeye': results[3] if not isinstance(results[3], Exception) else {},
            'Meteora': results[4] if not isinstance(results[4], Exception) else {}
        }
        
        return dex_prices
    
    def aggregate_prices(self, dex_prices: Dict[str, Dict[str, float]]) -> Dict[str, Dict]:
        """Aggregate prices across DEXes per token"""
        aggregated = {}
        
        for symbol in TOKENS.keys():
            token_prices = []
            sources = []
            
            for dex, prices in dex_prices.items():
                if symbol in prices:
                    token_prices.append(prices[symbol])
                    sources.append(dex)
            
            if token_prices:
                aggregated[symbol] = {
                    'prices': token_prices,
                    'sources': sources,
                    'min': min(token_prices),
                    'max': max(token_prices),
                    'avg': sum(token_prices) / len(token_prices),
                    'spread_pct': ((max(token_prices) - min(token_prices)) / min(token_prices)) * 100 if token_prices else 0,
                    'count': len(token_prices)
                }
        
        return aggregated
    
    def find_arbitrage_opportunities(self, aggregated: Dict) -> List[Dict]:
        """Find arbitrage opportunities across DEXes"""
        opportunities = []
        
        for symbol, data in aggregated.items():
            if data['count'] >= 2 and data['spread_pct'] > MIN_SPREAD_THRESHOLD * 100:
                # Find best buy and sell DEX
                min_idx = data['prices'].index(data['min'])
                max_idx = data['prices'].index(data['max'])
                
                opportunities.append({
                    'token': symbol,
                    'buy_dex': data['sources'][min_idx],
                    'buy_price': data['min'],
                    'sell_dex': data['sources'][max_idx],
                    'sell_price': data['max'],
                    'spread_pct': data['spread_pct'],
                    'profit_per_token': data['max'] - data['min']
                })
        
        return sorted(opportunities, key=lambda x: x['spread_pct'], reverse=True)
    
    def display_prices(self, aggregated: Dict, opportunities: List[Dict]):
        """Display current prices and opportunities"""
        print("\n" + "="*80)
        print("💰 CURRENT PRICES ACROSS ALL DEXes\n")
        
        for symbol in sorted(aggregated.keys()):
            data = aggregated[symbol]
            print(f"{symbol}:")
            print(f"  Min: ${data['min']:.6f} | Max: ${data['max']:.6f} | Avg: ${data['avg']:.6f}")
            print(f"  Spread: {data['spread_pct']:.3f}% | Sources: {', '.join(data['sources'])}\n")
        
        # Display tokens without prices
        for symbol in TOKENS.keys():
            if symbol not in aggregated:
                print(f"{symbol}: ⚠️ No prices available\n")
        
        if opportunities:
            print("🎯 ARBITRAGE OPPORTUNITIES (>" + f"{MIN_SPREAD_THRESHOLD*100}%)\n")
            for opp in opportunities:
                print(f"  {opp['token']}: Buy on {opp['buy_dex']} @ ${opp['buy_price']:.6f}")
                print(f"         Sell on {opp['sell_dex']} @ ${opp['sell_price']:.6f}")
                print(f"         Spread: {opp['spread_pct']:.3f}% | Profit: ${opp['profit_per_token']:.6f}\n")
        else:
            print("✓ No significant arbitrage opportunities detected")
    
    def save_to_json(self, aggregated: Dict, opportunities: List[Dict], filename: str = "multi_dex_prices.json"):
        """Save data to JSON file"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'prices': aggregated,
            'arbitrage_opportunities': opportunities
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"✓ Saved to {filename}")


async def main():
    print("SOLANA MULTI-DEX PRICE ENGINE FOR HF ARBITRAGE")
    print(f"Tracking: {', '.join(TOKENS.keys())}")
    print(f"Update interval: {UPDATE_INTERVAL}s")
    print(f"Min spread threshold: {MIN_SPREAD_THRESHOLD*100}%")
    print("DEX Sources: Jupiter, Raydium, Orca, Birdeye, Meteora")
    print("="*80)
    
    async with MultiDEXPriceTracker() as tracker:
        iteration = 1
        
        try:
            while True:
                # Fetch all prices
                dex_prices = await tracker.fetch_all_prices()
                
                # Aggregate and analyze
                aggregated = tracker.aggregate_prices(dex_prices)
                opportunities = tracker.find_arbitrage_opportunities(aggregated)
                
                # Display results
                tracker.display_prices(aggregated, opportunities)
                
                # Save to file
                tracker.save_to_json(aggregated, opportunities)
                
                print(f"\n[Iteration {iteration}] Waiting {UPDATE_INTERVAL}s before next update...")
                await asyncio.sleep(UPDATE_INTERVAL)
                iteration += 1
                
        except KeyboardInterrupt:
            print("\n\n✓ Shutting down gracefully...")


if __name__ == "__main__":
    asyncio.run(main())
