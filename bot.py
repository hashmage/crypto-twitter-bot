#!/usr/bin/env python3
import os

def main():
    print('Starting test bot')
    print('Environment variables:')
    keys = [
        'TWITTER_API_KEY',
        'TWITTER_API_SECRET',
        'TWITTER_ACCESS_TOKEN',
        'TWITTER_ACCESS_TOKEN_SECRET'
    ]
    for k in keys:
        print(f'{k} present: {bool(os.getenv(k))}')

if __name__ == '__main__':
    main()
