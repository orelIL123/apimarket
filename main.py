import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Configuration ---
# IMPORTANT: Replace 'YOUR_ALPHA_VANTAGE_API_KEY' with your actual free API key.
# Get your free key here: https://www.alphavantage.co/support/#api-key
# For permanent deployment, set this as an Environment Variable on your hosting platform!
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "demo" ) # 'demo' is for testing only
BASE_URL = "https://www.alphavantage.co/query"

app = FastAPI(
    title="Real-Time Market Data API Wrapper",
    description="A simple, secure wrapper for Alpha Vantage to fetch real-time stock and crypto prices.",
    version="1.0.0"
 )

class PriceResponse(BaseModel):
    """Schema for the API response."""
    symbol: str
    price: float
    currency: str
    last_refreshed: str
    source: str = "Alpha Vantage via Custom API"

def fetch_stock_price(symbol: str) -> dict:
    """Fetches real-time stock price using Alpha Vantage Global Quote."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()

    if "Error Message" in data:
        raise HTTPException(status_code=404, detail=f"Symbol not found or API error: {data['Error Message']}")
    
    quote = data.get("Global Quote", {})
    if not quote or not quote.get("05. price"):
        raise HTTPException(status_code=404, detail=f"Could not retrieve price for stock symbol: {symbol}")

    return {
        "symbol": quote.get("01. symbol"),
        "price": float(quote.get("05. price")),
        "currency": "USD", # Alpha Vantage Global Quote is typically in USD
        "last_refreshed": quote.get("07. latest trading day"),
    }

def fetch_crypto_price(symbol: str) -> dict:
    """Fetches real-time crypto price using Alpha Vantage Currency Exchange Rate."""
    from_symbol = symbol.upper()
    to_symbol = "USD"
    
    params = {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_symbol,
        "to_currency": to_symbol,
        "apikey": ALPHA_VANTAGE_API_KEY
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()

    if "Error Message" in data:
        raise HTTPException(status_code=404, detail=f"Symbol not found or API error: {data['Error Message']}")

    rate_info = data.get("Realtime Currency Exchange Rate", {})
    if not rate_info or not rate_info.get("5. Exchange Rate"):
        raise HTTPException(status_code=404, detail=f"Could not retrieve price for crypto symbol: {symbol}")

    return {
        "symbol": from_symbol,
        "price": float(rate_info.get("5. Exchange Rate")),
        "currency": to_symbol,
        "last_refreshed": rate_info.get("6. Last Refreshed"),
    }

@app.get("/price/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str):
    """
    Fetches the real-time price for a given stock, index, or cryptocurrency symbol.
    """
    upper_symbol = symbol.upper()
    
    # Map common index names to their Alpha Vantage symbols
    INDEX_MAP = {
        "NASDAQ": "^IXIC",
        "SP500": "^GSPC",
        "TA35": "TA35.TA" # Assuming TA35.TA is the correct symbol for Tel Aviv 35 on Alpha Vantage
    }
    
    if upper_symbol in INDEX_MAP:
        upper_symbol = INDEX_MAP[upper_symbol]
        is_crypto = False
    else:
        # Simple heuristic to distinguish between common crypto and stock symbols
        is_crypto = upper_symbol in ["BTC", "ETH", "XRP", "LTC", "ADA", "SOL", "DOGE"] or len(upper_symbol) <= 4

    try:
        # Try fetching as stock first (this covers mapped indices too)
        return fetch_stock_price(upper_symbol)
    except HTTPException as e:
        # If stock/index fails, try fetching as crypto
        try:
            return fetch_crypto_price(upper_symbol)
        except HTTPException:
            raise e # Re-raise the original stock/index error if crypto also fails
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Market Data API is running."}
