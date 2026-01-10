#!/usr/bin/env python3
"""
real_bot.py — safe poster.

Reads Twitter credentials from the environment, uploads media via v1.1 upload,
creates tweet via v2 endpoint, returns structured result (dict).
Handles 429 (Retry-After / x-rate-limit-reset) with backoff and returns errors for logging.
"""
import os
import time
from typing import Dict, Any
import requests

API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def _rate_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in headers.items() if "rate" in k.lower() or k.lower() in ("retry-after", "x-rate-limit-reset")}

def post_tweet(tweet_text: str, image_path: str = None, max_retries: int = 5, timeout: int = 30) -> Dict[str, Any]:
    from requests_oauthlib import OAuth1

    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        return {"ok": False, "error": "Missing Twitter credentials in environment"}

    auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    media_id = None
    if image_path and os.path.exists(image_path):
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        try:
            with open(image_path, "rb") as f:
                files = {"media": f}
                r = requests.post(upload_url, auth=auth, files=files, timeout=timeout)
            headers = dict(r.headers)
            rate = _rate_headers(headers)
            if r.status_code == 200:
                media_id = r.json().get("media_id_string")
            else:
                return {"ok": False, "status_code": r.status_code, "text": r.text, "rate": rate}
        except requests.RequestException as e:
            return {"ok": False, "error": f"Image upload exception: {e}"}

    url = "https://api.twitter.com/2/tweets"
    payload = {"text": tweet_text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}

    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.post(url, json=payload, auth=auth, timeout=timeout)
            headers = dict(r.headers)
            rate = _rate_headers(headers)
            if r.status_code in (200, 201):
                try:
                    body = r.json()
                except ValueError:
                    body = {"text": r.text}
                return {"ok": True, "status_code": r.status_code, "body": body, "rate": rate}
            if r.status_code == 429:
                retry_after = headers.get("Retry-After")
                reset_ts = headers.get("x-rate-limit-reset")
                sleep = None
                if retry_after:
                    try:
                        sleep = int(retry_after)
                    except Exception:
                        sleep = None
                if sleep is None and reset_ts:
                    try:
                        sleep = max(0, int(reset_ts) - int(time.time()))
                    except Exception:
                        sleep = None
                if sleep is None:
                    sleep = min(60 * (2 ** (attempt - 1)), 3600)
                if attempt >= max_retries:
                    return {"ok": False, "status_code": 429, "text": r.text, "rate": rate}
                time.sleep(sleep)
                continue
            return {"ok": False, "status_code": r.status_code, "text": r.text, "rate": rate}
        except requests.RequestException as e:
            if attempt >= max_retries:
                return {"ok": False, "error": f"RequestException: {e}"}
            backoff = min(2 ** attempt, 60)
            time.sleep(backoff)
            continue
