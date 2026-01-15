from fastapi import APIRouter, HTTPException
from typing import List
from app.models import GoldETF, ComparisonResult
from app.services.comparison_service import ComparisonService
from app.services import fetcher  # Use global fetcher instance

router = APIRouter()


# IMPORTANT: Specific routes must come before parameterized routes
# Order matters in FastAPI - more specific routes first!

@router.get("/gold-etf/compare", response_model=ComparisonResult)
async def compare_etfs():
    """
    Compare all gold ETFs and find the cheapest option.
    Similar to hangikredi's comparison approach.
    
    Data is automatically refreshed every 5 minutes in the background.
    Responses are served from cache for instant results.
    """
    try:
        etfs = await fetcher.fetch_all_etfs()
        if not etfs:
            raise HTTPException(
                status_code=503, 
                detail="No ETFs found. This may be due to rate limiting. Please wait a few minutes and try again, or check if Yahoo Finance is accessible."
            )
        
        # Get gram gold price for response
        gram_gold_price = fetcher._fetch_gram_gold_price()
        
        comparison = ComparisonService.compare_etfs(etfs)
        # Add spot gram gold price to comparison result
        comparison.spot_gram_gold_price = gram_gold_price
        
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Yahoo Finance has strict rate limits. Please wait 5-10 minutes before trying again. The API uses caching (5 min TTL) to reduce requests."
            )
        raise HTTPException(status_code=500, detail=f"Error comparing ETFs: {str(e)}")


@router.get("/gold-etf/list", response_model=List[GoldETF])
async def list_all_etfs():
    """
    Get list of all tracked gold ETFs with current prices.
    Data is automatically refreshed every 5 minutes in the background.
    """
    try:
        etfs = await fetcher.fetch_all_etfs()
        return etfs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ETFs: {str(e)}")


@router.get("/gold-etf/{symbol}", response_model=GoldETF)
async def get_etf_details(symbol: str):
    """
    Get details for a specific gold ETF.
    Data is automatically refreshed every 5 minutes in the background.
    """
    try:
        etf = await fetcher.fetch_etf_price(symbol.upper())
        if not etf:
            raise HTTPException(status_code=404, detail=f"ETF {symbol} not found")
        return etf
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ETF: {str(e)}")


@router.get("/gold-etf/compare/{symbol1}/{symbol2}")
async def compare_two_etfs(symbol1: str, symbol2: str):
    """
    Compare two specific gold ETFs by unit price.
    Example: /gold-etf/compare/GLDTR/ZGOLD
    Data is automatically refreshed every 5 minutes in the background.
    """
    try:
        etf1 = await fetcher.fetch_etf_price(symbol1.upper())
        if not etf1:
            raise HTTPException(status_code=404, detail=f"ETF {symbol1} not found")
        
        etf2 = await fetcher.fetch_etf_price(symbol2.upper())
        if not etf2:
            raise HTTPException(status_code=404, detail=f"ETF {symbol2} not found")
        
        comparison = ComparisonService.compare_two_etfs(etf1, etf2)
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing ETFs: {str(e)}")


@router.post("/gold-etf/clear-cache")
async def clear_cache():
    """
    Clear all caches to force fresh data fetch.
    Useful for testing or when data seems stale.
    """
    fetcher.clear_cache()
    return {"message": "Cache cleared successfully", "status": "ok"}


@router.get("/gold-etf/debug/{symbol}")
async def debug_etf_gold_backing(symbol: str):
    """
    Debug endpoint to see if gold_backing_grams is dynamically updated from NAV.
    Shows both static (default) and dynamic (calculated from NAV) values.
    """
    symbol_upper = symbol.upper()
    
    if symbol_upper not in fetcher.GOLD_ETFS:
        raise HTTPException(status_code=404, detail=f"ETF {symbol} not found")
    
    # Get static/default value
    etf_info = fetcher.GOLD_ETFS[symbol_upper]
    static_gold_backing = etf_info.get("gold_backing_grams")
    
    # Get current ETF data (may have dynamically updated gold_backing_grams)
    etf = await fetcher.fetch_etf_price(symbol_upper)
    if not etf:
        raise HTTPException(status_code=404, detail=f"ETF {symbol} data not available")
    
    # Get gram gold price
    gram_price = fetcher._fetch_gram_gold_price()
    
    # Calculate what gold_backing should be if NAV is available
    calculated_gold_backing = None
    if etf.nav_price and etf.nav_price > 0 and gram_price and gram_price > 0:
        calculated_gold_backing = etf.nav_price / gram_price
    
    return {
        "symbol": symbol_upper,
        "static_gold_backing_grams": static_gold_backing,
        "current_gold_backing_grams": etf.gold_backing_grams,
        "nav_price": etf.nav_price,
        "gram_gold_price": gram_price,
        "calculated_gold_backing": calculated_gold_backing,
        "is_dynamically_updated": etf.gold_backing_grams != static_gold_backing if static_gold_backing else None,
        "difference": etf.gold_backing_grams - static_gold_backing if (static_gold_backing and etf.gold_backing_grams) else None,
        "difference_percent": ((etf.gold_backing_grams - static_gold_backing) / static_gold_backing * 100) if (static_gold_backing and etf.gold_backing_grams and static_gold_backing > 0) else None,
        "explanation": {
            "static": f"Default value from configuration: {static_gold_backing} gram",
            "dynamic": f"Calculated from NAV: {calculated_gold_backing:.6f} gram" if calculated_gold_backing else "Could not calculate (NAV or gram price missing)",
            "current": f"Currently using: {etf.gold_backing_grams:.6f} gram" if etf.gold_backing_grams else "Not available",
            "formula": "gold_backing_grams = NAV / gram_gold_price" if calculated_gold_backing else None
        }
    }

