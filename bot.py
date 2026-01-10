#!/usr/bin/env python3
"""
Safe bot wrapper for CI.

Behavior:
- Honors DRY_RUN environment variable (defaults to true).
- Writes logs to bot.log and prints to stdout.
- If you provide a module `real_bot.py` with a function `post_tweet(message)`,
  this wrapper will call it when DRY_RUN is disabled.
- Otherwise it shows how to implement a posting helper using `requests`.
"""

import logging
import os
import sys
import time
from typing import Dict, Any

# Configure logging to file and stdout
logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# file handler
fh = logging.FileHandler("bot.log")
fh.setFormatter(formatter)
logger.addHandler(fh)

# stdout handler
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(formatter)
logger.addHandler(sh)


def is_dry_run() -> bool:
    v = os.getenv("DRY_RUN", "true").lower()
    return v not in ("false", "0", "no", "off")


def log_rate_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {k: headers.get(k) for k in headers.keys() if "rate" in k.lower() or k.lower() in ("retry-after", "x-rate-limit-reset")}


def main():
    logger.info("Starting bot wrapper. DRY_RUN=%s", is_dry_run())
    # example message to post; adapt as needed
    message = "Automated update from crypto-twitter-bot"

    # Attempt to import a project-provided posting implementation
    try:
        import real_bot  # you can create this module with a post_tweet(message) function
        has_real_bot = hasattr(real_bot, "post_tweet") and callable(real_bot.post_tweet)
    except Exception:
        real_bot = None
        has_real_bot = False

    if is_dry_run():
        logger.info("DRY_RUN active: will NOT post to Twitter/X. Would post message: %s", message)
        print("DRY_RUN active - skipping post")
        return

    # Not a dry run: attempt to post
    if has_real_bot:
        try:
            logger.info("Using real_bot.post_tweet to post message")
            resp = real_bot.post_tweet(message)
            logger.info("real_bot.post_tweet returned: %s", resp)
        except Exception as e:
            logger.exception("Exception while calling real_bot.post_tweet: %s", e)
            raise
    else:
        # No real_bot provided; show example of posting using requests and backoff.
        logger.warning("No real_bot.py with post_tweet found. Using example post_with_backoff (adapt to your API client).")
        try:
            resp = post_with_backoff_example(message)
            logger.info("Example post returned: %s", resp)
        except Exception as e:
            logger.exception("Error calling example post helper: %s", e)
            raise


def post_with_backoff_example(message: str, max_retries: int = 5) -> Dict[str, Any]:
    """
    Example of how to post with backoff using `requests`.
    Replace endpoint/headers with the appropriate Twitter/X API client you use, or
    implement equivalent logic using your library (tweepy, twitter-api-v2, etc).
    """
    import json
    import requests

    # Example: replace with the real endpoint and auth for your client
    url = "https://api.twitter.com/2/tweets"  # v2 API endpoint for creating a tweet
    # For OAuth2 / Bearer token you may need a different approach; this is illustrative only.
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    headers = {
        "Authorization": f"Bearer {bearer_token}" if bearer_token else "",
        "Content-Type": "application/json",
    }
    payload = {"text": message}

    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            logger.info("POST %s -> status=%s", url, r.status_code)
            logger.info("Rate headers: %s", log_rate_headers(r.headers))
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                reset_ts = r.headers.get("x-rate-limit-reset")
                logger.error("429 Too Many Requests. Retry-After=%s reset=%s body=%s", retry_after, reset_ts, r.text)
                if retry_after:
                    sleep = int(retry_after)
                elif reset_ts:
                    sleep = max(0, int(reset_ts) - int(time.time()))
                else:
                    sleep = min(60 * (2 ** (attempt - 1)), 3600)
                logger.info("Sleeping %s seconds before retry (attempt %s)", sleep, attempt)
                time.sleep(sleep)
                if attempt >= max_retries:
                    logger.error("Max retries reached, raising")
                    r.raise_for_status()
                continue
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return {"status_code": r.status_code, "text": r.text}
        except requests.RequestException as e:
            logger.exception("Request error on attempt %s: %s", attempt, e)
            if attempt >= max_retries:
                raise
            backoff = min(2 ** attempt, 60)
            logger.info("Sleeping %s seconds (backoff) before retry", backoff)
            time.sleep(backoff)


if __name__ == "__main__":
    main()
