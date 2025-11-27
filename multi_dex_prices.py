import asyncio
import aiohttp
import json
import ssl
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# SSL CONTEXT - Development only
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

# REALISTIC ARBITRAGE FILTERS
MIN_SPREAD_THRESHOLD = 0.005  # 0.5% minimum spread
MAX_SPREAD_THRESHOLD = 0.20   # 20% maximum spread (higher = likely fake)
MIN_LIQUIDITY_USD = 10000     # $10k minimum pool liquidity
MIN_SOURCES = 2               # Minimum number of DEXes reporting price
MAX_PRICE_DEVIATION = 0.30    # 30% max deviation from median (outlier filter)

# API Endpoints
JUPITER_PRICE_URL = "https://api.jup.ag/price/v2"
RAYDIUM_URL = "https://api-v3.raydium.io/pools/info/mint"
ORCA_WHIRLPOOL_URL = "https://api.mainnet.orca.so/v1/whirlpool/list"
BIRDEYE_URL = "https://public-api.birdeye.so/defi/price"
METEORA_URL = "https://dlmm-api.meteora.ag/pair/all"


@dataclass
class PoolData:
    """Structured pool data for GPU processing"""
    dex: str
    token_a: str
    token_b: str
    price: float
    liquidity_usd: float
    volume_24h: float
    fee_rate: float
    pool_address: str
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ArbitrageRoute:
    """Single arbitrage opportunity"""
    token: str
    buy_dex: str
    buy_price: float
    buy_liquidity: float
    sell_dex: str
    sell_price: float
    sell_liquidity: float
    spread_pct: float
    profit_per_token: float
    max_trade_size: float
    confidence_score: float
    
    def to_dict(self):
        return asdict(self)


class MultiDEXPriceTracker:
    def __init__(self):
        self.prices: Dict[str, Dict[str, float]] = {}
        self.pools: List[PoolData] = []  # For GPU multi-hop routing
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=20)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_jupiter_prices(self) -> Dict[str, Tuple[float, float, float]]:
        """Fetch prices from Jupiter - returns (price, liquidity, volume)"""
        try:
            token_ids = ','.join(TOKENS.values())
            url = f"{JUPITER_PRICE_URL}?ids={token_ids}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    
                    if 'data' in data:
                        for symbol, mint in TOKENS.items():
                            if mint in data['data']:
                                token_data = data['data'][mint]
                                price = float(token_data.get('price', 0))
                                liquidity = float(token_data.get('liquidity', 0))
                                volume = float(token_data.get('volume24h', 0))
                                
                                if price > 0:
                                    prices[symbol] = (price, liquidity, volume)
                    
                    return prices
        except Exception as e:
            print(f"✗ Jupiter: {e}")
        return {}
    
    async def fetch_raydium_prices(self) -> Dict[str, Tuple[float, float, float]]:
        """Fetch prices from Raydium with liquidity data"""
        try:
            prices = {}
            
            for symbol, mint in TOKENS.items():
                if symbol in ['USDC', 'USDT']:
                    prices[symbol] = (1.0, 0, 0)
                    continue
                
                url = f"{RAYDIUM_URL}?mint1={mint}&mint2={USDC_MINT}&poolType=all&poolSortField=liquidity&sortType=desc"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data') and len(data['data']) > 0:
                            # Get pool with highest liquidity
                            pool = data['data'][0]
                            price = float(pool.get('price', 0))
                            tvl = float(pool.get('tvl', 0))
                            volume = float(pool.get('volume24h', 0))
                            
                            if price > 0 and tvl >= MIN_LIQUIDITY_USD:
                                prices[symbol] = (price, tvl, volume)
                                
                                # Store pool data for GPU routing
                                self.pools.append(PoolData(
                                    dex='Raydium',
                                    token_a=symbol,
                                    token_b='USDC',
                                    price=price,
                                    liquidity_usd=tvl,
                                    volume_24h=volume,
                                    fee_rate=float(pool.get('feeRate', 0.0025)),
                                    pool_address=pool.get('id', '')
                                ))
            
            return prices
        except Exception as e:
            print(f"✗ Raydium: {e}")
        return {}
    
    async def fetch_orca_prices(self) -> Dict[str, Tuple[float, float, float]]:
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
                            tvl = float(pool.get('tvl', 0))
                            volume = float(pool.get('volume', {}).get('day', 0))
                            
                            # Only use pools with sufficient liquidity
                            if tvl < MIN_LIQUIDITY_USD:
                                continue
                            
                            for symbol, mint in TOKENS.items():
                                if mint == token_a and token_b == USDC_MINT:
                                    price = float(pool.get('price', 0))
                                    if price > 0:
                                        if symbol not in prices or tvl > prices[symbol][1]:
                                            prices[symbol] = (price, tvl, volume)
                                            
                                            self.pools.append(PoolData(
                                                dex='Orca',
                                                token_a=symbol,
                                                token_b='USDC',
                                                price=price,
                                                liquidity_usd=tvl,
                                                volume_24h=volume,
                                                fee_rate=0.003,
                                                pool_address=pool.get('address', '')
                                            ))
                                
                                elif mint == token_b and token_a == USDC_MINT:
                                    price = 1.0 / float(pool.get('price', 1))
                                    if price > 0:
                                        if symbol not in prices or tvl > prices[symbol][1]:
                                            prices[symbol] = (price, tvl, volume)
                                            
                                            self.pools.append(PoolData(
                                                dex='Orca',
                                                token_a=symbol,
                                                token_b='USDC',
                                                price=price,
                                                liquidity_usd=tvl,
                                                volume_24h=volume,
                                                fee_rate=0.003,
                                                pool_address=pool.get('address', '')
                                            ))
                    
                    return prices
        except Exception as e:
            print(f"✗ Orca: {e}")
        return {}
    
    async def fetch_birdeye_prices(self) -> Dict[str, Tuple[float, float, float]]:
        """Fetch prices from Birdeye"""
        try:
            prices = {}
            
            for symbol, mint in TOKENS.items():
                url = f"{BIRDEYE_URL}?address={mint}"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('data', {}).get('value'):
                            price = float(data['data']['value'])
                            liquidity = float(data['data'].get('liquidity', 0))
                            volume = float(data['data'].get('v24hUSD', 0))
                            
                            if price > 0 and liquidity >= MIN_LIQUIDITY_USD:
                                prices[symbol] = (price, liquidity, volume)
            
            return prices
        except Exception as e:
            print(f"✗ Birdeye: {e}")
        return {}
    
    async def fetch_meteora_prices(self) -> Dict[str, Tuple[float, float, float]]:
        """Fetch prices from Meteora DLMM"""
        try:
            async with self.session.get(METEORA_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    prices = {}
                    
                    for pair in data:
                        mint_x = pair.get('mint_x')
                        mint_y = pair.get('mint_y')
                        tvl = float(pair.get('liquidity', 0))
                        volume = float(pair.get('trade_volume_24h', 0))
                        
                        # Filter by liquidity
                        if tvl < MIN_LIQUIDITY_USD:
                            continue
                        
                        for symbol, mint in TOKENS.items():
                            if mint == mint_x and mint_y == USDC_MINT:
                                price = float(pair.get('current_price', 0))
                                if price > 0:
                                    if symbol not in prices or tvl > prices[symbol][1]:
                                        prices[symbol] = (price, tvl, volume)
                                        
                                        self.pools.append(PoolData(
                                            dex='Meteora',
                                            token_a=symbol,
                                            token_b='USDC',
                                            price=price,
                                            liquidity_usd=tvl,
                                            volume_24h=volume,
                                            fee_rate=float(pair.get('fee_rate', 0.003)),
                                            pool_address=pair.get('address', '')
                                        ))
                            
                            elif mint == mint_y and mint_x == USDC_MINT:
                                price = 1.0 / float(pair.get('current_price', 1))
                                if price > 0:
                                    if symbol not in prices or tvl > prices[symbol][1]:
                                        prices[symbol] = (price, tvl, volume)
                                        
                                        self.pools.append(PoolData(
                                            dex='Meteora',
                                            token_a=symbol,
                                            token_b='USDC',
                                            price=price,
                                            liquidity_usd=tvl,
                                            volume_24h=volume,
                                            fee_rate=float(pair.get('fee_rate', 0.003)),
                                            pool_address=pair.get('address', '')
                                        ))
                    
                    return prices
        except Exception as e:
            print(f"✗ Meteora: {e}")
        return {}
    
    async def fetch_all_prices(self) -> Dict[str, Dict[str, Tuple[float, float, float]]]:
        """Fetch prices from all DEXes concurrently"""
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Fetching prices from all DEXes...")
        
        # Clear pools for fresh data
        self.pools = []
        
        results = await asyncio.gather(
            self.fetch_jupiter_prices(),
            self.fetch_raydium_prices(),
            self.fetch_orca_prices(),
            self.fetch_birdeye_prices(),
            self.fetch_meteora_prices(),
            return_exceptions=True
        )
        
        dex_prices = {
            'Jupiter': results[0] if not isinstance(results[0], Exception) else {},
            'Raydium': results[1] if not isinstance(results[1], Exception) else {},
            'Orca': results[2] if not isinstance(results[2], Exception) else {},
            'Birdeye': results[3] if not isinstance(results[3], Exception) else {},
            'Meteora': results[4] if not isinstance(results[4], Exception) else {}
        }
        
        return dex_prices
    
    def calculate_confidence_score(self, prices: List[float], liquidities: List[float]) -> float:
        """Calculate confidence score for arbitrage opportunity"""
        if len(prices) < MIN_SOURCES:
            return 0.0
        
        # Factor 1: Number of sources (more = better)
        source_score = min(len(prices) / 5.0, 1.0)  # Max at 5 sources
        
        # Factor 2: Price consistency (lower std dev = better)
        import statistics
        if len(prices) > 1:
            mean_price = statistics.mean(prices)
            std_dev = statistics.stdev(prices)
            consistency_score = max(0, 1 - (std_dev / mean_price))
        else:
            consistency_score = 0.5
        
        # Factor 3: Total liquidity (higher = better)
        total_liquidity = sum(liquidities)
        liquidity_score = min(total_liquidity / 100000, 1.0)  # Max at $100k
        
        # Weighted average
        confidence = (source_score * 0.4 + consistency_score * 0.4 + liquidity_score * 0.2)
        return round(confidence, 3)
    
    def filter_outliers(self, price_data: List[Tuple[str, float, float, float]]) -> List[Tuple[str, float, float, float]]:
        """Remove price outliers using median absolute deviation"""
        if len(price_data) < 3:
            return price_data
        
        import statistics
        prices = [p[1] for p in price_data]
        median = statistics.median(prices)
        
        # Filter out prices that deviate too much from median
        filtered = []
        for data in price_data:
            deviation = abs(data[1] - median) / median
            if deviation <= MAX_PRICE_DEVIATION:
                filtered.append(data)
        
        return filtered if filtered else price_data  # Return original if all filtered
    
    def aggregate_prices(self, dex_prices: Dict[str, Dict[str, Tuple[float, float, float]]]) -> Dict[str, Dict]:
        """Aggregate prices with outlier filtering and confidence scoring"""
        aggregated = {}
        
        for symbol in TOKENS.keys():
            # Collect all price data: (dex, price, liquidity, volume)
            price_data = []
            
            for dex, prices in dex_prices.items():
                if symbol in prices:
                    price, liquidity, volume = prices[symbol]
                    price_data.append((dex, price, liquidity, volume))
            
            if not price_data:
                continue
            
            # Filter outliers
            filtered_data = self.filter_outliers(price_data)
            
            if len(filtered_data) >= MIN_SOURCES:
                prices = [p[1] for p in filtered_data]
                sources = [p[0] for p in filtered_data]
                liquidities = [p[2] for p in filtered_data]
                volumes = [p[3] for p in filtered_data]
                
                min_price = min(prices)
                max_price = max(prices)
                spread_pct = ((max_price - min_price) / min_price) * 100
                
                # Calculate confidence
                confidence = self.calculate_confidence_score(prices, liquidities)
                
                aggregated[symbol] = {
                    'prices': prices,
                    'sources': sources,
                    'liquidities': liquidities,
                    'volumes': volumes,
                    'min': min_price,
                    'max': max_price,
                    'avg': sum(prices) / len(prices),
                    'spread_pct': spread_pct,
                    'count': len(prices),
                    'confidence': confidence,
                    'total_liquidity': sum(liquidities),
                    'total_volume_24h': sum(volumes)
                }
        
        return aggregated
    
    def find_realistic_arbitrage(self, aggregated: Dict) -> List[ArbitrageRoute]:
        """Find realistic arbitrage opportunities with strict filtering"""
        opportunities = []
        
        for symbol, data in aggregated.items():
            spread_pct = data['spread_pct']
            
            # Apply realistic filters
            if (data['count'] < MIN_SOURCES or
                spread_pct < MIN_SPREAD_THRESHOLD * 100 or
                spread_pct > MAX_SPREAD_THRESHOLD * 100 or
                data['confidence'] < 0.5):
                continue
            
            # Find best buy and sell
            min_idx = data['prices'].index(data['min'])
            max_idx = data['prices'].index(data['max'])
            
            buy_liquidity = data['liquidities'][min_idx]
            sell_liquidity = data['liquidities'][max_idx]
            
            # Calculate max trade size (5% of pool liquidity)
            max_trade_size = min(buy_liquidity, sell_liquidity) * 0.05 / data['min']
            
            route = ArbitrageRoute(
                token=symbol,
                buy_dex=data['sources'][min_idx],
                buy_price=data['min'],
                buy_liquidity=buy_liquidity,
                sell_dex=data['sources'][max_idx],
                sell_price=data['max'],
                sell_liquidity=sell_liquidity,
                spread_pct=spread_pct,
                profit_per_token=data['max'] - data['min'],
                max_trade_size=max_trade_size,
                confidence_score=data['confidence']
            )
            
            opportunities.append(route)
        
        return sorted(opportunities, key=lambda x: x.confidence_score * x.spread_pct, reverse=True)
    
    def display_prices(self, aggregated: Dict, opportunities: List[ArbitrageRoute]):
        """Display current prices and realistic opportunities"""
        print("\n" + "="*80)
        print("💰 CURRENT PRICES (Filtered & Validated)\n")
        
        for symbol in sorted(aggregated.keys()):
            data = aggregated[symbol]
            print(f"{symbol}:")
            print(f"  Price: ${data['min']:.6f} - ${data['max']:.6f} (avg: ${data['avg']:.6f})")
            print(f"  Spread: {data['spread_pct']:.2f}% | Confidence: {data['confidence']:.1%}")
            print(f"  Liquidity: ${data['total_liquidity']:,.0f} | Volume 24h: ${data['total_volume_24h']:,.0f}")
            print(f"  Sources ({data['count']}): {', '.join(data['sources'])}\n")
        
        if opportunities:
            print("🎯 REALISTIC ARBITRAGE OPPORTUNITIES\n")
            for i, opp in enumerate(opportunities, 1):
                profit_usd = opp.profit_per_token * opp.max_trade_size
                print(f"{i}. {opp.token} | Confidence: {opp.confidence_score:.1%} | Spread: {opp.spread_pct:.2f}%")
                print(f"   Buy:  {opp.buy_dex:10} @ ${opp.buy_price:.6f}  (Liq: ${opp.buy_liquidity:,.0f})")
                print(f"   Sell: {opp.sell_dex:10} @ ${opp.sell_price:.6f}  (Liq: ${opp.sell_liquidity:,.0f})")
                print(f"   Max Trade: {opp.max_trade_size:,.2f} {opp.token} (~${profit_usd:,.2f} profit potential)")
                print()
        else:
            print("✓ No realistic arbitrage opportunities detected")
            print(f"  (Filters: {MIN_SPREAD_THRESHOLD*100}%-{MAX_SPREAD_THRESHOLD*100}% spread, " +
                  f"${MIN_LIQUIDITY_USD:,}+ liquidity, {MIN_SOURCES}+ sources)")
    
    def export_for_gpu_routing(self, filename: str = "pools_for_gpu.json"):
        """Export pool data for GPU multi-hop routing"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'pool_count': len(self.pools),
            'pools': [pool.to_dict() for pool in self.pools],
            'tokens': TOKENS
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Exported {len(self.pools)} pools to {filename} for GPU routing")
    
    def save_to_json(self, aggregated: Dict, opportunities: List[ArbitrageRoute], 
                     filename: str = "realistic_arbitrage.json"):
        """Save realistic opportunities to JSON"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'filters': {
                'min_spread': MIN_SPREAD_THRESHOLD,
                'max_spread': MAX_SPREAD_THRESHOLD,
                'min_liquidity': MIN_LIQUIDITY_USD,
                'min_sources': MIN_SOURCES
            },
            'prices': aggregated,
            'opportunities': [opp.to_dict() for opp in opportunities]
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)


async def main():
    print("SOLANA REALISTIC ARBITRAGE TRACKER")
    print(f"Tracking: {', '.join(TOKENS.keys())}")
    print(f"Update interval: {UPDATE_INTERVAL}s")
    print(f"Filters: {MIN_SPREAD_THRESHOLD*100}%-{MAX_SPREAD_THRESHOLD*100}% spread, " +
          f"${MIN_LIQUIDITY_USD:,}+ liquidity, {MIN_SOURCES}+ sources")
    print("="*80)
    
    async with MultiDEXPriceTracker() as tracker:
        iteration = 1
        
        try:
            while True:
                # Fetch all prices
                dex_prices = await tracker.fetch_all_prices()
                
                # Aggregate with filtering
                aggregated = tracker.aggregate_prices(dex_prices)
                
                # Find realistic opportunities
                opportunities = tracker.find_realistic_arbitrage(aggregated)
                
                # Display results
                tracker.display_prices(aggregated, opportunities)
                
                # Save data
                tracker.save_to_json(aggregated, opportunities)
                tracker.export_for_gpu_routing()
                
                print(f"\n[Iteration {iteration}] Waiting {UPDATE_INTERVAL}s before next update...")
                await asyncio.sleep(UPDATE_INTERVAL)
                iteration += 1
                
        except KeyboardInterrupt:
            print("\n\n✓ Shutting down gracefully...")


if __name__ == "__main__":
    asyncio.run(main())
