import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from datetime import datetime

# --- Configuration ---
# IMPORTANT: Replace 'YOUR_FINNHUB_API_KEY' with your actual free API key.
# Get your free key here: https://finnhub.io/register
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "d4cbh0hr01qudf6hhukgd4cbh0hr01qudf6hhul0" )
BASE_URL = "https://finnhub.io/api/v1"

# Cache configuration
CACHE_TTL = 15 # Time to Live in seconds (15 seconds minimum for 13 symbols on Finnhub free tier )
CACHE_KEY_PREFIX = "finnhub_price"

app = FastAPI(
    title="Real-Time Market Data API Wrapper (Finnhub)",
    description="A simple, secure wrapper for Finnhub to fetch real-time stock and crypto prices.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup():
    FastAPICache.init(InMemoryBackend(), prefix=CACHE_KEY_PREFIX)

class PriceResponse(BaseModel):
    """Schema for the API response."""
    symbol: str
    price: float
    currency: str
    last_refreshed: str
    source: str = "Finnhub via Custom API"

def fetch_finnhub_price(symbol: str) -> dict:
    """Fetches real-time price using Finnhub Quote endpoint."""
    params = {
        "symbol": symbol,
        "token": FINNHUB_API_KEY
    }
    url = f"{BASE_URL}/quote"
    response = requests.get(url, params=params)
    data = response.json()

    # Finnhub returns an empty object or a specific error message for invalid symbols/keys
    if not data or data.get("s") == "no_data":
        raise HTTPException(status_code=404, detail=f"Could not retrieve price for symbol: {symbol}. Check if symbol is correct or if API key is valid.")
    
    # 'c' is the current price
    price = data.get("c")
    timestamp = data.get("t")

    if not price or price == 0:
        raise HTTPException(status_code=404, detail=f"Could not retrieve price for symbol: {symbol}. Price data is missing or zero.")

    # Convert Unix timestamp to ISO format string
    last_refreshed = datetime.fromtimestamp(timestamp).isoformat() if timestamp else datetime.now().isoformat()

    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD", # Finnhub quotes are typically in USD
        "last_refreshed": last_refreshed,
    }

@app.get("/price/{symbol}", response_model=PriceResponse)
@cache(expire=CACHE_TTL)
async def get_price(symbol: str):
    """
    Fetches the real-time price for a given stock, index, or cryptocurrency symbol.
    """
    upper_symbol = symbol.upper()
    
    # Finnhub requires specific prefixes for indices and crypto
    INDEX_MAP = {
        "NASDAQ": "^IXIC",
        "SP500": "^GSPC",
        "TA35": "TA35.TA" # Finnhub might not support this, but we keep the mapping for consistency
    }
    
    # Finnhub Crypto symbols are typically in the format 'BINANCE:BTCUSDT'
    # We will try to map common crypto symbols to a common exchange (e.g., BINANCE)
    CRYPTO_MAP = {
        "BTC": "BINANCE:BTCUSDT",
        "ETH": "BINANCE:ETHUSDT",
        "XRP": "BINANCE:XRPUSDT",
        "LTC": "BINANCE:LTCUSDT",
        "ADA": "BINANCE:ADAUSDT",
        "SOL": "BINANCE:SOLUSDT",
        "DOGE": "BINANCE:DOGEUSDT",
    }

    # 1. Check for Index mapping
    if upper_symbol in INDEX_MAP:
        finnhub_symbol = INDEX_MAP[upper_symbol]
    # 2. Check for Crypto mapping
    elif upper_symbol in CRYPTO_MAP:
        finnhub_symbol = CRYPTO_MAP[upper_symbol]
    # 3. Assume it's a standard stock ticker
    else:
        finnhub_symbol = upper_symbol

    try:
        # Try fetching the price with the determined Finnhub symbol
        return fetch_finnhub_price(finnhub_symbol)
    except HTTPException as e:
        # If the first attempt fails, try a fallback for common symbols
        if upper_symbol not in INDEX_MAP and upper_symbol not in CRYPTO_MAP:
            # Fallback: If it was a stock, try a common crypto format (e.g., for short symbols)
            if len(upper_symbol) <= 4:
                try:
                    finnhub_symbol_fallback = CRYPTO_MAP.get(upper_symbol, f"BINANCE:{upper_symbol}USDT")
                    return fetch_finnhub_price(finnhub_symbol_fallback)
                except HTTPException:
                    raise e # Re-raise the original error
            else:
                raise e # Re-raise the original error
        else:
            raise e # Re-raise the original error
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Market Data API is running."}
