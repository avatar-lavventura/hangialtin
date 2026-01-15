from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import gold_etf
from app.services import fetcher  # Use global fetcher instance
from datetime import datetime
import os
import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for background tasks.
    """
    # Startup: Start background task to fetch data every 5 minutes
    background_task = asyncio.create_task(fetch_data_periodically())
    
    yield
    
    # Shutdown: Cancel background task
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass


async def fetch_data_periodically():
    """
    Background task that fetches all ETF data and gram gold price every 5 minutes.
    This keeps the cache fresh so users get instant responses.
    """
    print("Background task started: Fetching ETF data every 5 minutes...")
    
    # Fetch immediately on startup
    await fetch_all_data()
    
    # Then fetch every 5 minutes (300 seconds)
    while True:
        try:
            await asyncio.sleep(300)  # Wait 5 minutes
            await fetch_all_data()
        except asyncio.CancelledError:
            print("Background task cancelled")
            break
        except Exception as e:
            print(f"Error in background task: {type(e).__name__}: {str(e)[:100]}")
            # Continue even if there's an error - don't stop the background task
            await asyncio.sleep(60)  # Wait 1 minute before retrying on error


async def fetch_all_data():
    """
    Fetch all ETF data and gram gold price to populate cache.
    """
    try:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch: Starting data update...")
        
        # Fetch gram gold price first (needed for NAV calculations)
        gram_price = fetcher._fetch_gram_gold_price()
        if gram_price:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch: Gram gold price = {gram_price:.2f} TL/gram")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch: Warning - Could not fetch gram gold price")
        
        # Fetch all ETFs
        etfs = await fetcher.fetch_all_etfs()
        if etfs:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch: Successfully cached {len(etfs)} ETFs")
            for etf in etfs:
                nav_str = f"{etf.nav_price:.4f} TL" if etf.nav_price else "N/A"
                print(f"  - {etf.symbol}: {etf.current_price:.4f} TL (NAV: {nav_str})")
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch: Warning - No ETFs fetched")
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Background fetch error: {type(e).__name__}: {str(e)[:100]}")


app = FastAPI(
    title="HangiAltin - BIST Gold ETF Comparison",
    description="Find the cheapest BIST gold ETF to buy",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(gold_etf.router, prefix="/api", tags=["gold-etf"])


@app.get("/")
async def root():
    """Serve the front-end HTML file."""
    static_file = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {
        "message": "HangiAltin API - BIST Gold ETF Comparison Service",
        "endpoints": {
            "compare": "/api/gold-etf/compare",
            "list": "/api/gold-etf/list",
            "details": "/api/gold-etf/{symbol}"
        },
        "frontend": "/static/index.html"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify background task and cache status.
    """
    # Check if cache has any data
    cache_size = len(fetcher._cache)
    gram_cache_size = len(fetcher._gram_gold_cache)
    
    # Try to get a sample ETF from cache
    sample_etf = None
    for symbol in fetcher.GOLD_ETFS.keys():
        cache_key = f"etf_{symbol.upper()}"
        cached = fetcher._cache.get(cache_key)
        if cached:
            sample_etf = cached
            break
    
    gram_price = fetcher._gram_gold_cache.get("gram_gold_price")
    
    return {
        "status": "healthy",
        "background_task": "running",
        "cache_status": {
            "etf_cache_size": cache_size,
            "gram_gold_cache_size": gram_cache_size,
            "sample_etf": {
                "symbol": sample_etf.symbol if sample_etf else None,
                "price": sample_etf.current_price if sample_etf else None,
                "last_updated": sample_etf.last_updated.isoformat() if sample_etf and sample_etf.last_updated else None
            } if sample_etf else None,
            "gram_gold_price": gram_price
        },
        "message": "Background task fetches data every 5 minutes. Data is served from cache for instant responses."
    }

