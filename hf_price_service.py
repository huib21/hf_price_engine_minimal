root@55bebced5e91:~/hf_price_engine_minimal# python3.13 hf_price_service.py
HF CoinGecko Engine Running...

{'SOL': 137.01, 'USDC': 1.0, 'ETH': 2931.07, 'USDT': 1.0, 'BONK': 9.49e-06, 'RAY': 1.1, 'ORCA': 1.065, 'BTC': 87110.0}
{'SOL': 137.01, 'USDC': 1.0, 'ETH': 2931.07, 'USDT': 1.0, 'BONK': 9.49e-06, 'RAY': 1.1, 'ORCA': 1.065, 'BTC': 87110.0}
{'SOL': 137.01, 'USDC': 1.0, 'ETH': 2931.07, 'USDT': 1.0, 'BONK': 9.49e-06, 'RAY': 1.1, 'ORCA': 1.065, 'BTC': 87110.0}
{'SOL': 137.01, 'USDC': 1.0, 'ETH': 2931.07, 'USDT': 1.0, 'BONK': 9.49e-06, 'RAY': 1.1, 'ORCA': 1.065, 'BTC': 87110.0}
{'SOL': 137.01, 'USDC': 1.0, 'ETH': 2931.07, 'USDT': 1.0, 'BONK': 9.49e-06, 'RAY': 1.1, 'ORCA': 1.065, 'BTC': 87110.0}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
Error fetching prices: 429 Client Error: Too Many Requests for url: https://api.coingecko.com/api/v3/simple/price?ids=solana,usd-coin,ethereum,tether,bonk,jupiter-exchange,raydium,orca,bitcoin&vs_currencies=usd
{}
^CTraceback (most recent call last):
  File "/root/hf_price_engine_minimal/hf_price_service.py", line 63, in <module>
    HFPriceService().run()
    ~~~~~~~~~~~~~~~~~~~~^^
  File "/root/hf_price_engine_minimal/hf_price_service.py", line 60, in run
    time.sleep(1)  # 1 Hz; voor HF kun je dit later verlagen
    ~~~~~~~~~~^^^
KeyboardInterrupt
