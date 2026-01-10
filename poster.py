#!/usr/bin/env python3
"""
Poster script: find biggest hourly gainer, create chart image, and post via real_bot.post_tweet.

Reads Twitter credentials from environment variables (no hard-coded keys).
Writes bot.log and crypto_chart.png in the repo root during run.
"""
import logging
import os
import time
import json
from datetime import datetime
from typing import Dict, Any, Tuple, List

import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

# Logging
logger = logging.getLogger("poster")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("bot.log")
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(fh)
logger.addHandler(logging.StreamHandler())

BRANDING_TEXT = "@tokennotifs"

# Binance helpers
def get_binance_chart_url(symbol: str) -> str:
    base = symbol.replace("USDT", "")
    return f"https://www.binance.com/en/trade/{base}_USDT"

def get_top_100_symbols() -> List[Dict[str, Any]]:
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        tickers = r.json()
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        usdt_pairs.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        return usdt_pairs[:100]
    except Exception as e:
        logger.exception("Error fetching tickers: %s", e)
        return []

def get_last_hourly_candles(symbol: str, limit: int = 24):
    url = "https://api.binance.com/api/v3/klines"
    params = {'symbol': symbol, 'interval': '1h', 'limit': limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def calculate_hourly_change(candles):
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
        'close_time': datetime.fromtimestamp(close_time / 1000),
        'candles': candles
    }

# Chart generation (kept similar to your design)
def create_candlestick_chart(candles, symbol, winner_candle_index=-2) -> str:
    try:
        times = [datetime.fromtimestamp(c[0] / 1000) for c in candles]
        opens = [float(c[1]) for c in candles]
        highs = [float(c[2]) for c in candles]
        lows = [float(c[3]) for c in candles]
        closes = [float(c[4]) for c in candles]
        volumes = [float(c[5]) for c in candles]

        fig = plt.figure(figsize=(14, 8), facecolor='#0e1217')
        ax_price = plt.subplot2grid((4, 1), (0, 0), rowspan=3, fig=fig)
        ax_price.set_facecolor('#0e1217')
        ax_volume = plt.subplot2grid((4, 1), (3, 0), fig=fig, sharex=ax_price)
        ax_volume.set_facecolor('#0e1217')

        winner_change = ((closes[winner_candle_index] - opens[winner_candle_index]) /
                         opens[winner_candle_index] * 100)

        width_in_hours = 0.6
        candle_width = width_in_hours / 24.0

        for i in range(len(candles)):
            open_price = opens[i]
            close_price = closes[i]
            high_price = highs[i]
            low_price = lows[i]
            t = mdates.date2num(times[i])
            is_green = close_price >= open_price

            if i == winner_candle_index:
                body_color = '#FFD700'
                wick_color = '#FFD700'
                edge_color = '#000000'
                edge_width = 3
                wick_width = 3
            elif is_green:
                body_color = '#00E676'
                wick_color = '#00E676'
                edge_color = '#00C853'
                edge_width = 1.5
                wick_width = 2
            else:
                body_color = '#FF5252'
                wick_color = '#FF5252'
                edge_color = '#D32F2F'
                edge_width = 1.5
                wick_width = 2

            ax_price.plot([t, t], [low_price, high_price], color=wick_color, linewidth=wick_width, alpha=1.0, zorder=1)
            height = abs(close_price - open_price)
            bottom = min(open_price, close_price)
            if height < (high_price - low_price) * 0.05:
                height = (high_price - low_price) * 0.05

            rect = Rectangle((t - candle_width / 2, bottom), candle_width, height,
                             facecolor=body_color, edgecolor=edge_color, linewidth=edge_width, zorder=2)
            ax_price.add_patch(rect)
            vol_color = body_color if i != winner_candle_index else '#FFD700'
            ax_volume.bar(t, volumes[i], width=candle_width * 0.9, color=vol_color, alpha=0.7, edgecolor='none')

        winner_time = mdates.date2num(times[winner_candle_index])
        winner_price = max(highs[winner_candle_index], closes[winner_candle_index])
        ax_price.annotate(f'🚀 +{winner_change:.2f}%',
                         xy=(winner_time, winner_price),
                         xytext=(10, 15), textcoords='offset points',
                         bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFD700', edgecolor='#FFA500', linewidth=2, alpha=0.95),
                         fontsize=11, fontweight='bold', color='#0e1217',
                         arrowprops=dict(arrowstyle='->', color='#FFD700', lw=2))

        ax_price.grid(True, alpha=0.25, linestyle='-', linewidth=0.8, color='#2d3748')
        ax_price.set_ylabel('Price (USDT)', fontsize=13, color='#e2e8f0', fontweight='bold')
        ax_price.tick_params(colors='#e2e8f0', labelsize=11, width=1.5, length=6)

        ax_volume.grid(True, alpha=0.25, linestyle='-', linewidth=0.8, color='#2d3748')
        ax_volume.set_ylabel('Volume', fontsize=12, color='#e2e8f0', fontweight='bold')
        ax_volume.set_xlabel('Time (UTC)', fontsize=13, color='#e2e8f0', fontweight='bold')

        ax_price.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax_price.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.setp(ax_price.xaxis.get_majorticklabels(), rotation=0, fontsize=11, fontweight='bold')

        fig.text(0.125, 0.96, f'{symbol}/USDT', fontsize=22, fontweight='bold', color='#ffffff', ha='left')
        fig.text(0.99, 0.02, f'{BRANDING_TEXT}  •  Data: Binance', fontsize=8, color='#4a5568', ha='right', style='italic')

        plt.tight_layout(rect=[0, 0.03, 1, 0.91])
        script_dir = os.path.dirname(os.path.abspath(__file__))
        chart_path = os.path.join(script_dir, 'crypto_chart.png')
        plt.savefig(chart_path, dpi=200, facecolor='#0e1217', edgecolor='none', bbox_inches='tight', pad_inches=0.3)
        plt.close()
        logger.info("Chart created: %s", chart_path)
        return chart_path
    except Exception as e:
        logger.exception("Error creating chart: %s", e)
        plt.close()
        return None

def find_biggest_green_candle() -> Tuple[Dict[str, Any], str]:
    logger.info("Starting analysis at %s", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    symbols = get_top_100_symbols()
    if not symbols:
        logger.error("No symbols fetched")
        return None, None

    results = []
    for i, ticker in enumerate(symbols):
        symbol = ticker['symbol']
        if i > 0 and i % 25 == 0:
            logger.info("Processed %s/%s symbols", i, len(symbols))
        candles = get_last_hourly_candles(symbol)
        if candles:
            info = calculate_hourly_change(candles)
            if info and info['change_percent'] > 0:
                coin_name = symbol.replace('USDT', '')
                results.append({'symbol': coin_name, 'full_symbol': symbol, **info})
        time.sleep(0.05)

    if not results:
        logger.info("No green candles found")
        return None, None

    results.sort(key=lambda x: x['change_percent'], reverse=True)
    winner = results[0]
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
    logger.info("Winner: %s +%0.2f%%", winner['symbol'], winner['change_percent'])
    return winner, tweet

def main():
    try:
        winner, tweet_text = find_biggest_green_candle()
        if not winner or not tweet_text:
            logger.info("Nothing to post")
            return

        # Create chart image
        chart_path = create_candlestick_chart(winner['candles'], winner['symbol'])
        # Post using real_bot if available
        dry = os.getenv("DRY_RUN", "false").lower() not in ("false", "0", "no", "off")
        if dry:
            logger.info("DRY_RUN enabled — not posting. Preview:\n%s", tweet_text)
            if chart_path:
                logger.info("Chart would be: %s", chart_path)
            return

        try:
            import real_bot
        except Exception:
            real_bot = None

        if real_bot and hasattr(real_bot, "post_tweet"):
            logger.info("Posting tweet via real_bot")
            res = real_bot.post_tweet(tweet_text, image_path=chart_path)
            logger.info("Post result: %s", res)
        else:
            logger.error("real_bot.post_tweet not available (create real_bot.py)")
    except Exception as e:
        logger.exception("Unhandled exception in main: %s", e)

if __name__ == "__main__":
    main()
