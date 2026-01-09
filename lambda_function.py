import requests
import time
from datetime import datetime
import os
import json

# Twitter API credentials from environment variables
API_KEY = os.environ.get('TWITTER_API_KEY')
API_SECRET = os.environ.get('TWITTER_API_SECRET')
ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

BRANDING_TEXT = "@tokennotifs"

def get_binance_chart_url(symbol):
    """Generate Binance trading chart URL"""
    base = symbol.replace("USDT", "")
    return f"https://www.binance.com/en/trade/{base}_USDT"

def get_top_100_symbols():
    """Get top 100 USDT trading pairs from Binance by volume"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            tickers = response.json()
            usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
            usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
            return usdt_pairs[:100]
        else:
            print(f"Error fetching tickers: {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception fetching tickers: {e}")
        return []

def get_last_hourly_candles(symbol):
    """Get hourly candles for a symbol"""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': '1h',
        'limit': 3
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

def calculate_hourly_change(candles):
    """Calculate percentage change from last completed hourly candle"""
    if not candles or len(candles) < 2:
        return None
    
    last_candle = candles[-2]
    
    open_price = float(last_candle[1])
    close_price = float(last_candle[4])
    high_price = float(last_candle[2])
    low_price = float(last_candle[3])
    close_time = last_candle[6]
    
    if open_price == 0:
        return None
    
    change_percent = ((close_price - open_price) / open_price) * 100
    
    return {
        'open': open_price,
        'close': close_price,
        'high': high_price,
        'low': low_price,
        'change_percent': change_percent,
        'close_time': datetime.fromtimestamp(close_time / 1000)
    }

def find_biggest_green_candle():
    """Find the coin with the biggest green candle"""
    print(f"🔍 Starting analysis at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    symbols = get_top_100_symbols()
    
    if not symbols:
        print("❌ Failed to fetch symbols")
        return None, None
    
    print(f"✅ Analyzing {len(symbols)} symbols...")
    
    results = []
    
    for i, ticker in enumerate(symbols):
        symbol = ticker['symbol']
        
        if i > 0 and i % 25 == 0:
            print(f"⏳ Processed {i}/{len(symbols)}...")
        
        candles = get_last_hourly_candles(symbol)
        
        if candles:
            candle_info = calculate_hourly_change(candles)
            
            if candle_info and candle_info['change_percent'] > 0:
                coin_name = symbol.replace('USDT', '')
                
                results.append({
                    'symbol': coin_name,
                    'full_symbol': symbol,
                    **candle_info
                })
        
        time.sleep(0.05)
    
    if not results:
        print("❌ No green candles found")
        return None, None
    
    results.sort(key=lambda x: x['change_percent'], reverse=True)
    
    # Show top 5
    print("🏆 TOP 5:")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. {result['symbol']}: +{result['change_percent']:.2f}%")
    
    winner = results[0]
    
    print(f"🥇 WINNER: {winner['symbol']} +{winner['change_percent']:.2f}%")
    
    chart_url = get_binance_chart_url(winner['full_symbol'])
    
    tweet = (
        f"🚀 Biggest Hourly Gainer\n\n"
        f"{winner['symbol']} ⬆️ +{winner['change_percent']:.2f}%\n"
        f"📊 Chart: {chart_url}\n\n"
        f"💰 ${winner['open']:.4f} → ${winner['close']:.4f}\n"
        f"📈 High: ${winner['high']:.4f}\n"
        f"⏰ {winner['close_time'].strftime('%H:%M UTC')}\n\n"
        f"${winner['symbol']} #Crypto #Binance"
    )
    
    print(f"\n📱 TWEET:\n{tweet}")
    
    return winner, tweet

def post_tweet(tweet_text):
    """Post a tweet"""
    from requests_oauthlib import OAuth1
    
    url = "https://api.twitter.com/2/tweets"
    payload = {"text": tweet_text}
    
    auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    try:
        response = requests.post(url, json=payload, auth=auth, timeout=15)
        
        if response.status_code == 201:
            tweet_data = response.json()
            tweet_id = tweet_data['data']['id']
            print(f"✅ Tweet posted!")
            print(f"🔗 https://twitter.com/i/web/status/{tweet_id}")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def lambda_handler(event, context):
    """AWS Lambda entry point"""
    
    try:
        print("🚀 Lambda function started")
        
        winner, tweet_text = find_biggest_green_candle()
        
        if not winner or not tweet_text:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No data to post'})
            }
        
        print("📤 Posting to Twitter...")
        success = post_tweet(tweet_text)
        
        if success:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Tweet posted successfully'})
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Failed to post tweet'})
            }
            
    except Exception as e:
        print(f"❌ Lambda error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Error: {str(e)}'})
        }