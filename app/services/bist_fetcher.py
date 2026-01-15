import yfinance as yf
import asyncio
import time
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from cachetools import TTLCache
from app.models import GoldETF


class BISTFetcher:
    """
    Fetches BIST gold ETF prices from various sources.
    Supports multiple ETFs: ZGOLD, GLDTR, and others.
    Uses yfinance for BIST data (symbols with .IS suffix).
    Includes caching and rate limiting to avoid API throttling.
    """
    
    # Common BIST gold ETFs with their full names
    # For yfinance, BIST stocks use .IS suffix
    # Try without .IS first, then with .IS, as yfinance may handle them differently
    GOLD_ETFS = {
        "ZGOLD": {
            "name": "ZGOLD Gold ETF",
            "ticker": "ZGOLD.IS",  # Primary ticker format for yfinance
            "alternatives": ["ZGOLD"],  # Try without suffix too
            "gold_backing_grams": 0.0981,  # ZGOLD 1 pay ≈ 0.0981 gram altın karşılığı
            "nav_price": 626.702,  # Fixed NAV value (will be updated in future)
            "stopaj_rate": 0.0,  # Stopaj oranı (%)
            "expense_ratio": 0.0  # Yönetim ücreti/harcama oranı (%) - güncellenecek
        },
        "GLDTR": {
            "name": "GLDTR Gold ETF",
            "ticker": "GLDTR.IS",
            "alternatives": ["GLDTR"],
            "gold_backing_grams": 0.085,  # GLDTR 1 pay ≈ 0.085 gram altın karşılığı
            "nav_price": 538.2205,  # Fixed NAV value (will be updated in future)
            "stopaj_rate": 0.0,  # Stopaj oranı (%)
            "expense_ratio": 0.0  # Yönetim ücreti/harcama oranı (%) - güncellenecek
        },
        "ISGLK": {
            "name": "ISGLK Altın ETF",
            "ticker": "ISGLK.IS",
            "alternatives": ["ISGLK"],
            "gold_backing_grams": 0.102,  # ISGLK bir birim = 1 gram altın karşılığı (varsayım, güncellenebilir)
            "nav_price": 626.702,  # Fixed NAV value (will be updated in future)
            "stopaj_rate": 0.0,  # Stopaj oranı (%)
            "expense_ratio": 0.0  # Yönetim ücreti/harcama oranı (%) - güncellenecek
        },
        "GLD": {
            "name": "GLD Gold ETF",
            "ticker": "GLD.IS",
            "alternatives": ["GLD"],
            "active": False  # Possibly delisted based on 404 errors
        },
        "GLDTR2": {
            "name": "GLDTR2 Gold ETF",
            "ticker": "GLDTR2.IS",
            "alternatives": ["GLDTR2"],
            "active": False  # Possibly delisted based on 404 errors
        },
    }
    
    # Cache with 5 minute TTL to reduce API calls significantly
    _cache = TTLCache(maxsize=100, ttl=300)
    _gram_gold_cache = TTLCache(maxsize=10, ttl=300)  # Cache for gram gold price
    
    def clear_cache(self):
        """Clear all caches - useful for testing or forcing fresh data."""
        self._cache.clear()
        self._gram_gold_cache.clear()
        print("Cache cleared")
    
    def __init__(self):
        self.last_request_time = 0
        self.min_request_interval = 3.0  # Minimum 3 seconds between requests to avoid rate limits and blocking
    
    def _fetch_gram_gold_price(self) -> Optional[float]:
        """
        Fetches gram gold price using GC=F (Gold futures) and USDTRY=X (USD/TRY exchange rate).
        Calculation method:
        1. Get gold futures price (USD per troy ounce) from GC=F
        2. Get USD/TRY exchange rate from USDTRY=X
        3. Calculate XAU/TRY = gold_usd * usd_try
        4. Convert to gram: gram_try = xau_try / GRAMS_PER_OUNCE (31.1034768)
        """
        cache_key = "gram_gold_price"
        cached_price = self._gram_gold_cache.get(cache_key)
        if cached_price:
            # Check if cached price is valid (not 0 or None)
            if cached_price > 0:
                print(f"Gram gold price (cached): {cached_price:.2f} TL/gram")
                return cached_price
            else:
                # Invalid cached price, clear it and fetch fresh
                print(f"Warning: Invalid cached gram gold price ({cached_price}), clearing cache and fetching fresh...")
                self._gram_gold_cache.pop(cache_key, None)
        
        try:
            # Gold futures (USD per troy ounce)
            print("Fetching gold futures (GC=F)...")
            self._rate_limit()
            gold = yf.Ticker("GC=F")
            gold_hist = gold.history(period="1d", interval="1m")
            
            if gold_hist.empty:
                raise RuntimeError("Yahoo veri dönmedi: GC=F boş")
            
            # USD/TRY exchange rate
            print("Fetching USD/TRY exchange rate (USDTRY=X)...")
            self._rate_limit()
            usdtry = yf.Ticker("USDTRY=X")
            usdtry_hist = usdtry.history(period="1d", interval="1m")
            
            if usdtry_hist.empty:
                raise RuntimeError("Yahoo veri dönmedi: USDTRY=X boş")
            
            # Get latest prices
            gold_usd = gold_hist["Close"].iloc[-1]
            usd_try = usdtry_hist["Close"].iloc[-1]
            
            # Validate prices
            if pd.isna(gold_usd) or gold_usd <= 0:
                raise RuntimeError(f"Geçersiz altın fiyatı: {gold_usd}")
            if pd.isna(usd_try) or usd_try <= 0:
                raise RuntimeError(f"Geçersiz USD/TRY kuru: {usd_try}")
            
            # XAU/TRY ons
            xau_try = gold_usd * usd_try
            
            # Gram altın
            GRAMS_PER_OUNCE = 31.1034768
            gram_try = xau_try / GRAMS_PER_OUNCE
            
            # Validate result
            if gram_try <= 0 or not (1000 <= gram_try <= 20000):
                raise RuntimeError(f"Hesaplanan gram fiyatı makul değil: {gram_try:.2f} TL/gram")
            
            print(f"Gold (USD/oz): {gold_usd:.2f}")
            print(f"USD/TRY: {usd_try:.4f}")
            print(f"XAU/TRY: {xau_try:.2f}")
            print(f"Gram TL: {gram_try:.2f}")
            
            # Cache the result
            self._gram_gold_cache[cache_key] = gram_try
            return gram_try
            
        except Exception as e:
            error_msg = f"Error fetching gram gold price: {type(e).__name__}: {str(e)[:100]}"
            print(f"Warning: {error_msg}")
            return None
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    
    def _try_ticker_formats(self, symbol: str, etf_info: Dict) -> List[str]:
        """
        Returns a list of ticker formats to try for a given symbol.
        For yfinance, BIST stocks typically use .IS suffix.
        """
        ticker_formats = []
        
        # Add primary ticker first (most likely to work)
        if etf_info and "ticker" in etf_info:
            primary_ticker = etf_info["ticker"]
            ticker_formats.append(primary_ticker)
        
        # Add alternative formats
        if etf_info and "alternatives" in etf_info:
            ticker_formats.extend(etf_info["alternatives"])
        
        # If no alternatives, add common variations
        if len(ticker_formats) <= 1:
            base_symbol = symbol.upper()
            # Try without .IS suffix if primary has it
            if ticker_formats and ticker_formats[0].endswith(".IS"):
                ticker_formats.append(base_symbol)
            # Try with .IS if primary doesn't have it
            elif ticker_formats and not ticker_formats[0].endswith(".IS"):
                ticker_formats.append(f"{base_symbol}.IS")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_formats = []
        for fmt in ticker_formats:
            if fmt not in seen:
                seen.add(fmt)
                unique_formats.append(fmt)
        
        return unique_formats
    
    def fetch_etf_price_sync(self, symbol: str, retry_count: int = 3, use_stale_cache: bool = True) -> Optional[GoldETF]:
        """
        Synchronously fetches current price for a specific gold ETF using yfinance.
        Note: yfinance is synchronous, so we use this in an async context.
        Includes retry logic with exponential backoff for rate limiting.
        If rate limited, can return stale cached data if available.
        """
        # Check cache first - return immediately if available
        cache_key = f"etf_{symbol.upper()}"
        cached_etf = self._cache.get(cache_key)
        if cached_etf:
            return cached_etf
        
        # Validate symbol is in our list
        if symbol.upper() not in self.GOLD_ETFS:
            # Silently ignore invalid symbols (likely from error parsing)
            # Only log if it's a reasonable-looking symbol (not error messages)
            if len(symbol) <= 10 and symbol.isalnum():
                print(f"Warning: {symbol} is not in the list of tracked ETFs")
            return None
        
        etf_info = self.GOLD_ETFS.get(symbol.upper())
        
        # Check if symbol is marked as inactive (delisted)
        if etf_info and etf_info.get("active") is False:
            print(f"Info: {symbol} is marked as inactive (possibly delisted), skipping")
            return None
        
        if not etf_info:
            # Try with .IS suffix if not found
            etf_name = f"{symbol.upper()} Gold ETF"
            base_symbol = symbol.upper()
            ticker_formats = [
                f"{base_symbol}.IS",
                base_symbol
            ]
        else:
            etf_name = etf_info["name"]
            ticker_formats = self._try_ticker_formats(symbol, etf_info)
        
        # Try each ticker format until one succeeds
        for ticker_symbol in ticker_formats:
            for attempt in range(retry_count):
                try:
                    # Rate limiting
                    self._rate_limit()
                    
                    # Try yf.download first as it's more reliable for some tickers
                    # This method sometimes works better than Ticker() for international symbols
                    try:
                        self._rate_limit()
                        download_data = yf.download(
                            ticker_symbol,
                            period="1d",
                            progress=False,
                            timeout=15,
                            auto_adjust=True,
                            prepost=False
                        )
                        if download_data is not None and isinstance(download_data, pd.DataFrame) and not download_data.empty and len(download_data) > 0:
                            # Handle MultiIndex columns if present
                            if isinstance(download_data.columns, pd.MultiIndex):
                                if ticker_symbol in download_data.columns.levels[0]:
                                    download_data = download_data[ticker_symbol]
                            
                            # Try to get Close price
                            if 'Close' in download_data.columns:
                                price_val = download_data['Close'].iloc[-1]
                                if pd.notna(price_val) and price_val > 0:
                                    current_price = float(price_val)
                                    previous_close = float(download_data['Close'].iloc[-2]) if len(download_data) > 1 else current_price
                                    if current_price > 0:
                                        print(f"Successfully fetched {ticker_symbol} using download method: {current_price}")
                                        # Create ETF object directly
                                        # Get gold backing from ETF info (ZGOLD uses fixed value: 0.1014 gram)
                                        gold_backing = etf_info.get("gold_backing_grams") if etf_info else None
                                        gram_gold_price_for_nav_calc = None
                                        
                                        # GLDTR uses fixed gold backing: 1 pay ≈ 0.085 gram altın
                                        # Use the value from GOLD_ETFS dictionary
                                        
                                        # Use fixed NAV value from GOLD_ETFS dictionary (will be updated in future)
                                        nav_price = etf_info.get("nav_price") if etf_info else None
                                        if nav_price:
                                            print(f"{symbol}: NAV (sabit değer) = {nav_price:.4f} TL (GOLD_ETFS'den alındı)")
                                        
                                        # Calculate NAV using ETF-specific formulas (only if fixed NAV not available):
                                        # 
                                        # 1) GLDTR (QNB Portföy Altın Katılım BYF):
                                        #    NAV_GLDTR = ((fiziki altın gramı × spot) + nakit) / pay sayısı
                                        #    Portföyü ağırlıkla fiziki altın + az miktar nakit içerir.
                                        #    Bu yüzden GLDTR'de 1 pay = sabit bir gram + küçük TL nakit gibi davranır.
                                        #
                                        # 2) ZGOLD (Ziraat Portföy Altın Katılım BYF):
                                        #    NAV_ZGOLD = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                                        #    Portföyü altın bazlı kira sertifikaları, altın hesapları ve fiziki altın içerir.
                                        #    "Altın eşdeğeri gram", sertifikaların ve hesapların spot altına çevrilmiş karşılığıdır.
                                        #
                                        # 3) ISGLK (İş Portföy Altın Katılım BYF):
                                        #    NAV_ISGLK = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                                        #    ZGOLD ile aynı mantık. Varlık türleri farklı olabilir ama hesap aynıdır.
                                        #
                                        # Basitleştirilmiş hesaplama (nakit kalemi küçük olduğu için yaklaşık):
                                        # NAV ≈ (1 payın gramı) × (spot gram fiyatı)
                                        # NAV değeri her zaman bu formüle göre hesaplanır (değişken)
                                        # Note: If fixed NAV is not set, calculate it
                                        if not nav_price:
                                            if gold_backing and gold_backing > 0:
                                                try:
                                                    if not gram_gold_price_for_nav_calc:
                                                        print(f"{symbol}: Fetching gram gold price for NAV calculation...")
                                                        gram_gold_price_for_nav_calc = self._fetch_gram_gold_price()
                                                        if gram_gold_price_for_nav_calc is None:
                                                            print(f"{symbol}: ERROR - gram_gold_price_for_nav_calc is None!")
                                                        elif gram_gold_price_for_nav_calc == 0:
                                                            print(f"{symbol}: ERROR - gram_gold_price_for_nav_calc is 0.00!")
                                                    if gram_gold_price_for_nav_calc and gram_gold_price_for_nav_calc > 0:
                                                        calculated_nav = gold_backing * gram_gold_price_for_nav_calc
                                                        print(f"{symbol}: NAV Debug - gold_backing={gold_backing:.6f}, gram_gold_price={gram_gold_price_for_nav_calc:.2f}, calculated_nav={calculated_nav:.2f}")
                                                        # Use calculated NAV if it's reasonable (between 0.1 and 10000 TL)
                                                        if 0.1 <= calculated_nav <= 10000:
                                                            nav_price = calculated_nav
                                                            print(f"{symbol}: NAV (güncellenmiş) ≈ {gold_backing:.6f} gram × {gram_gold_price_for_nav_calc:.2f} TL/gram = {nav_price:.2f} TL (formüle göre hesaplandı)")
                                                        else:
                                                            print(f"Warning: {symbol} calculated NAV seems incorrect: {calculated_nav:.2f} TL (Gold backing: {gold_backing:.6f} gram, Gram price: {gram_gold_price_for_nav_calc:.2f} TL/gram)")
                                                    else:
                                                        print(f"Warning: {symbol} gram gold price is invalid: {gram_gold_price_for_nav_calc}")
                                                except Exception as nav_err:
                                                    print(f"Warning: Could not calculate NAV for {symbol}: {type(nav_err).__name__}: {str(nav_err)[:100]}")
                                            else:
                                                print(f"Warning: {symbol} gold_backing is invalid: {gold_backing}")
                                        
                                        # Try to get NAV from ticker info only as fallback if fixed NAV and calculation both failed
                                        nav_from_ticker = False
                                        if not nav_price:
                                            try:
                                                ticker = yf.Ticker(ticker_symbol)
                                                info = ticker.info
                                                nav_keys = ['navPrice', 'netAssetValue', 'nav', 'NAV', 'netAssetValuePerShare']
                                                for key in nav_keys:
                                                    if key in info and info[key]:
                                                        try:
                                                            nav_price = float(info[key])
                                                            if nav_price > 0:
                                                                nav_from_ticker = True
                                                                print(f"{symbol}: NAV (fallback) = {nav_price:.2f} TL (ticker info'dan alındı)")
                                                                break
                                                        except (ValueError, TypeError):
                                                            continue
                                            except Exception:
                                                pass
                                        
                                        # Print final NAV value
                                        if nav_price:
                                            print(f"{symbol}: Final NAV = {nav_price:.2f} TL")
                                        else:
                                            print(f"{symbol}: NAV hesaplanamadı")
                                        
                                        # Update gold_backing_grams from NAV if available (using fixed NAV values)
                                        # Formula: gold_backing_grams = NAV / gram_gold_price
                                        # This gives us the actual gold backing per share based on NAV
                                        if nav_price and nav_price > 0:
                                            # Ensure we have gram gold price
                                            if not gram_gold_price_for_nav_calc:
                                                gram_gold_price_for_nav_calc = self._fetch_gram_gold_price()
                                            
                                            if gram_gold_price_for_nav_calc and gram_gold_price_for_nav_calc > 0:
                                                calculated_gold_backing = nav_price / gram_gold_price_for_nav_calc
                                                # Validate calculated gold_backing (should be reasonable, e.g., 0.01 to 1.0 grams per share)
                                                if 0.01 <= calculated_gold_backing <= 1.0:
                                                    gold_backing = calculated_gold_backing
                                                    print(f"{symbol}: gold_backing_grams NAV'dan güncellendi: {gold_backing:.6f} gram (NAV={nav_price:.2f} TL / gram_fiyat={gram_gold_price_for_nav_calc:.2f} TL/gram)")
                                                else:
                                                    print(f"{symbol}: Warning - NAV'dan hesaplanan gold_backing makul değil: {calculated_gold_backing:.6f} gram, sabit değer kullanılıyor: {gold_backing}")
                                            else:
                                                print(f"{symbol}: Warning - Gram gold price alınamadı, gold_backing_grams güncellenemedi")
                                        # If NAV not available or not from ticker, use static value from GOLD_ETFS dictionary
                                        
                                        # Get stopaj and expense ratio from ETF info
                                        stopaj_rate = etf_info.get("stopaj_rate") if etf_info else None
                                        expense_ratio = etf_info.get("expense_ratio") if etf_info else None
                                        
                                        etf = GoldETF(
                                            symbol=symbol.upper(),
                                            name=etf_name,
                                            current_price=round(current_price, 4),
                                            change_percent=round(((current_price - previous_close) / previous_close) * 100, 2) if previous_close > 0 else 0.0,
                                            volume=None,
                                            last_updated=datetime.now(),
                                            gold_backing_grams=gold_backing,
                                            nav_price=round(nav_price, 4) if nav_price else None,
                                            stopaj_rate=stopaj_rate,
                                            expense_ratio=expense_ratio
                                        )
                                        self._cache[cache_key] = etf
                                        return etf
                    except Exception as download_first_error:
                        # Download method failed, continue to Ticker method
                        pass
                    
                    # Fallback to Ticker method
                    ticker = yf.Ticker(ticker_symbol)
                    
                    # Skip info call if it causes JSON parsing errors - we can get price from history
                    info = {}
                    try:
                        info = ticker.info
                        # Check if info is actually valid (not empty dict or error response)
                        if not info or not isinstance(info, dict):
                            info = {}
                    except Exception as info_error:
                        error_str = str(info_error)
                        # If info fails, try history only
                        if "429" in error_str or "Too Many Requests" in error_str:
                            wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                            print(f"Rate limited for {symbol}, waiting {wait_time}s before retry {attempt + 1}/{retry_count}")
                            time.sleep(wait_time)
                            continue
                        # JSON parsing errors or empty responses - skip info, use history only
                        if "Expecting value" in error_str or "JSON" in error_str or "empty" in error_str.lower():
                            # This is okay - we'll get data from history instead
                            info = {}
                        else:
                            # Other errors - log but continue
                            info = {}
                    
                    # Get current price - try multiple periods if needed
                    current_price = 0.0
                    previous_close = 0.0
                    hist = None
                    rate_limited = False
                    json_error_occurred = False
                    
                    # Try different periods in order of preference
                    periods_to_try = ["1d", "5d", "1mo"]
                    for period in periods_to_try:
                        try:
                            # Try with interval parameter for better data retrieval
                            hist = ticker.history(period=period, interval="1d", auto_adjust=True, prepost=False)
                            # Better validation of the data
                            if hist is not None and isinstance(hist, pd.DataFrame) and not hist.empty and len(hist) > 0:
                                # Check if Close column exists
                                if 'Close' in hist.columns:
                                    price_val = hist['Close'].iloc[-1]
                                    # Check for NaN and valid price
                                    if pd.notna(price_val) and price_val > 0:
                                        current_price = float(price_val)
                                        if len(hist) > 1:
                                            prev_val = hist['Close'].iloc[-2]
                                            previous_close = float(prev_val) if pd.notna(prev_val) and prev_val > 0 else current_price
                                        else:
                                            previous_close = current_price
                                        if current_price > 0:  # Valid price found
                                            print(f"Successfully fetched price for {ticker_symbol} using period={period}: {current_price}")
                                            break  # Success, exit loop
                                # Try alternative column names if Close doesn't exist
                                elif 'Adj Close' in hist.columns:
                                    price_val = hist['Adj Close'].iloc[-1]
                                    if pd.notna(price_val) and price_val > 0:
                                        current_price = float(price_val)
                                        previous_close = float(hist['Adj Close'].iloc[-2]) if len(hist) > 1 else current_price
                                        if current_price > 0:
                                            print(f"Successfully fetched price for {ticker_symbol} using Adj Close: {current_price}")
                                            break
                                else:
                                    # Log what columns we got for debugging
                                    print(f"Warning: {ticker_symbol} history returned data but no Close/Adj Close column. Columns: {list(hist.columns)}")
                        except Exception as hist_error:
                            error_str = str(hist_error)
                            # Check for rate limiting
                            if "429" in error_str or "Too Many Requests" in error_str:
                                rate_limited = True
                                wait_time = (2 ** attempt) * 2
                                print(f"Rate limited for {symbol} history, waiting {wait_time}s before retry {attempt + 1}/{retry_count}")
                                time.sleep(wait_time)
                                break  # Break to retry outer loop
                            # Check for JSON parsing errors (empty/invalid response)
                            if "Expecting value" in error_str or "JSON" in error_str:
                                json_error_occurred = True
                                # Yahoo Finance returned invalid response - try next period or retry
                                if attempt < retry_count - 1:
                                    # Wait longer for JSON errors (might be temporary blocking)
                                    wait_time = 5
                                    print(f"Invalid response for {symbol} ({period}), waiting {wait_time}s before retry")
                                    time.sleep(wait_time)
                                    break  # Break to retry outer loop
                                continue  # Try next period
                            # Check for "no data" errors or 404 - symbol may be delisted
                            if "No price data found" in error_str or "delisted" in error_str.lower() or "404" in error_str or "Not Found" in error_str:
                                # If 404 or delisted, don't try other periods - move to next ticker format
                                if "404" in error_str or "Not Found" in error_str or "delisted" in error_str.lower():
                                    print(f"  {ticker_symbol}: Symbol not found or delisted (404/delisted error)")
                                    break  # Break period loop, try next ticker format
                                continue  # Try next period
                            # Other errors - try next period
                            continue
                    
                    # If we were rate limited, retry the whole operation
                    if rate_limited:
                        continue  # Retry outer loop
                    
                    # If we got JSON errors on all periods and have retries left, retry the whole operation
                    if json_error_occurred and current_price == 0.0 and attempt < retry_count - 1:
                        wait_time = 5
                        print(f"JSON errors for all periods for {symbol}, waiting {wait_time}s before retry {attempt + 1}/{retry_count}")
                        time.sleep(wait_time)
                        continue  # Retry outer loop
                    
                    # If history didn't work, try fallback using yf.download for this single symbol
                    if current_price == 0.0:
                        try:
                            self._rate_limit()
                            download_data = yf.download(
                                ticker_symbol, 
                                period="1d", 
                                progress=False, 
                                timeout=15,
                                auto_adjust=True,
                                prepost=False
                            )
                            if download_data is not None and isinstance(download_data, pd.DataFrame) and not download_data.empty and len(download_data) > 0:
                                # Handle MultiIndex columns if present
                                if isinstance(download_data.columns, pd.MultiIndex):
                                    if ticker_symbol in download_data.columns.levels[0]:
                                        download_data = download_data[ticker_symbol]
                                
                                # Try to get Close price
                                if 'Close' in download_data.columns:
                                    price_val = download_data['Close'].iloc[-1]
                                    if pd.notna(price_val) and price_val > 0:
                                        current_price = float(price_val)
                                        previous_close = float(download_data['Close'].iloc[-2]) if len(download_data) > 1 else current_price
                                elif 'Adj Close' in download_data.columns:
                                    price_val = download_data['Adj Close'].iloc[-1]
                                    if pd.notna(price_val) and price_val > 0:
                                        current_price = float(price_val)
                                        previous_close = float(download_data['Adj Close'].iloc[-2]) if len(download_data) > 1 else current_price
                        except Exception as download_error:
                            # Download fallback failed, try info
                            error_str = str(download_error)
                            if "No price data found" not in error_str and "delisted" not in error_str.lower():
                                print(f"Download fallback failed for {ticker_symbol}: {type(download_error).__name__}")
                            pass
                    
                    # If still no price, try fallback to info
                    if current_price == 0.0:
                        current_price = info.get('regularMarketPrice') or info.get('previousClose') or info.get('currentPrice', 0.0)
                        previous_close = info.get('previousClose', current_price)
                    
                    if current_price == 0.0:
                        # No price found with this ticker format, try next format
                        break  # Break inner retry loop, try next ticker format
                    
                    # Get change percent
                    if previous_close and previous_close > 0:
                        change_percent = ((current_price - previous_close) / previous_close) * 100
                    else:
                        change_percent = 0.0
                    
                    # Get volume
                    volume = info.get('regularMarketVolume') or info.get('volume', 0)
                    
                    # Get gold backing (altın karşılığı) from ETF info or default
                    gold_backing = None
                    if etf_info and "gold_backing_grams" in etf_info:
                        gold_backing = etf_info["gold_backing_grams"]
                    
                    # Get gold backing from ETF info (ZGOLD uses fixed value: 0.1014 gram)
                    gram_gold_price_for_nav = None
                    
                    # GLDTR uses fixed gold backing: 1 pay ≈ 0.085 gram altın
                    # Use the value from GOLD_ETFS dictionary (already set above)
                    
                    # Use fixed NAV value from GOLD_ETFS dictionary (will be updated in future)
                    nav_price = etf_info.get("nav_price") if etf_info else None
                    if nav_price:
                        print(f"{symbol}: NAV (sabit değer) = {nav_price:.4f} TL (GOLD_ETFS'den alındı)")
                    
                    # Calculate NAV using ETF-specific formulas (only if fixed NAV not available):
                    # 
                    # 1) GLDTR (QNB Portföy Altın Katılım BYF):
                    #    NAV_GLDTR = ((fiziki altın gramı × spot) + nakit) / pay sayısı
                    #    Portföyü ağırlıkla fiziki altın + az miktar nakit içerir.
                    #    Bu yüzden GLDTR'de 1 pay = sabit bir gram + küçük TL nakit gibi davranır.
                    #
                    # 2) ZGOLD (Ziraat Portföy Altın Katılım BYF):
                    #    NAV_ZGOLD = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                    #    Portföyü altın bazlı kira sertifikaları, altın hesapları ve fiziki altın içerir.
                    #    "Altın eşdeğeri gram", sertifikaların ve hesapların spot altına çevrilmiş karşılığıdır.
                    #
                    # 3) ISGLK (İş Portföy Altın Katılım BYF):
                    #    NAV_ISGLK = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                    #    ZGOLD ile aynı mantık. Varlık türleri farklı olabilir ama hesap aynıdır.
                    #
                    # Basitleştirilmiş hesaplama (nakit kalemi küçük olduğu için yaklaşık):
                    # NAV ≈ (1 payın gramı) × (spot gram fiyatı)
                    # NAV değeri her zaman bu formüle göre hesaplanır (değişken)
                    # Note: If fixed NAV is not set, calculate it
                    if not nav_price:
                        if gold_backing and gold_backing > 0:
                            try:
                                if not gram_gold_price_for_nav:
                                    print(f"{symbol}: Fetching gram gold price for NAV calculation...")
                                    gram_gold_price_for_nav = self._fetch_gram_gold_price()
                                    if gram_gold_price_for_nav is None:
                                        print(f"{symbol}: ERROR - gram_gold_price_for_nav is None!")
                                    elif gram_gold_price_for_nav == 0:
                                        print(f"{symbol}: ERROR - gram_gold_price_for_nav is 0.00!")
                                if gram_gold_price_for_nav and gram_gold_price_for_nav > 0:
                                    calculated_nav = gold_backing * gram_gold_price_for_nav
                                    print(f"{symbol}: NAV Debug - gold_backing={gold_backing:.6f}, gram_gold_price={gram_gold_price_for_nav:.2f}, calculated_nav={calculated_nav:.2f}")
                                    # Use calculated NAV if it's reasonable (between 0.1 and 10000 TL)
                                    if 0.1 <= calculated_nav <= 10000:
                                        nav_price = calculated_nav
                                        print(f"{symbol}: NAV (güncellenmiş) ≈ {gold_backing:.6f} gram × {gram_gold_price_for_nav:.2f} TL/gram = {nav_price:.2f} TL (formüle göre hesaplandı)")
                                    else:
                                        print(f"Warning: {symbol} calculated NAV seems incorrect: {calculated_nav:.2f} TL (Gold backing: {gold_backing:.6f} gram, Gram price: {gram_gold_price_for_nav:.2f} TL/gram)")
                                else:
                                    print(f"Warning: {symbol} gram gold price is invalid: {gram_gold_price_for_nav}")
                            except Exception as nav_calc_error:
                                print(f"Warning: Could not calculate NAV for {symbol}: {type(nav_calc_error).__name__}: {str(nav_calc_error)[:100]}")
                        else:
                            print(f"Warning: {symbol} gold_backing is invalid: {gold_backing}")
                    
                    # Try to get NAV from ticker info only as fallback if calculation failed
                    nav_from_ticker = False
                    if not nav_price:
                        nav_keys = ['navPrice', 'netAssetValue', 'nav', 'NAV', 'netAssetValuePerShare']
                        for key in nav_keys:
                            if key in info and info[key]:
                                try:
                                    nav_price = float(info[key])
                                    if nav_price > 0:
                                        nav_from_ticker = True
                                        print(f"{symbol}: NAV (fallback) = {nav_price:.2f} TL (ticker info'dan alındı)")
                                        break
                                except (ValueError, TypeError):
                                    continue
                    
                    # Print final NAV value
                    if nav_price:
                        print(f"{symbol}: Final NAV = {nav_price:.2f} TL")
                    else:
                        print(f"{symbol}: NAV hesaplanamadı")
                    
                    # Update gold_backing_grams from NAV if available (using fixed NAV values)
                    # Formula: gold_backing_grams = NAV / gram_gold_price
                    # This gives us the actual gold backing per share based on NAV
                    if nav_price and nav_price > 0:
                        if not gram_gold_price_for_nav:
                            # Try to fetch gram gold price if not already fetched
                            gram_gold_price_for_nav = self._fetch_gram_gold_price()
                        if gram_gold_price_for_nav and gram_gold_price_for_nav > 0:
                            calculated_gold_backing = nav_price / gram_gold_price_for_nav
                            # Validate calculated gold_backing (should be reasonable, e.g., 0.01 to 1.0 grams per share)
                            if 0.01 <= calculated_gold_backing <= 1.0:
                                gold_backing = calculated_gold_backing
                                print(f"{symbol}: gold_backing_grams NAV'dan güncellendi: {gold_backing:.6f} gram (NAV={nav_price:.2f} TL / gram_fiyat={gram_gold_price_for_nav:.2f} TL/gram)")
                            else:
                                print(f"{symbol}: Warning - NAV'dan hesaplanan gold_backing makul değil: {calculated_gold_backing:.6f} gram, sabit değer kullanılıyor: {gold_backing}")
                    # If NAV not available or not from ticker, use static value from GOLD_ETFS dictionary
                    
                    # Get stopaj and expense ratio from ETF info
                    stopaj_rate = etf_info.get("stopaj_rate") if etf_info else None
                    expense_ratio = etf_info.get("expense_ratio") if etf_info else None
                    
                    etf = GoldETF(
                        symbol=symbol.upper(),
                        name=etf_name,
                        current_price=round(current_price, 4),
                        change_percent=round(change_percent, 2),
                        volume=int(volume) if volume else None,
                        last_updated=datetime.now(),
                        gold_backing_grams=gold_backing,
                        nav_price=round(nav_price, 4) if nav_price else None,
                        stopaj_rate=stopaj_rate,
                        expense_ratio=expense_ratio
                    )
                    
                    # Cache the result
                    self._cache[cache_key] = etf
                    return etf
                    
                except Exception as e:
                    error_str = str(e)
                    error_type = type(e).__name__
                    # Log detailed error for debugging on last attempt
                    if attempt == retry_count - 1:
                        print(f"Debug: {ticker_symbol} error details: {error_type}: {error_str[:200]}")
                    # Check for rate limiting
                    if "429" in error_str or "Too Many Requests" in error_str:
                        if attempt < retry_count - 1:
                            wait_time = (2 ** attempt) * 3  # Longer waits: 3s, 6s
                            print(f"Rate limited for {symbol}, waiting {wait_time}s before retry {attempt + 1}/{retry_count}")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"Error fetching {symbol} after {retry_count} attempts: Rate limit exceeded")
                            print(f"Note: Yahoo Finance has strict rate limits. Consider using cached data or waiting longer.")
                            break  # Try next ticker format
                    # Check for JSON parsing errors (empty/invalid response from Yahoo Finance)
                    elif "Expecting value" in error_str or ("JSON" in error_str and "parse" in error_str.lower()):
                        # This means Yahoo Finance returned empty/invalid response - try next ticker format immediately
                        print(f"Warning: {ticker_symbol}: Yahoo Finance returned empty/invalid response (JSON parse error), trying next ticker format")
                        break  # Try next ticker format immediately - don't retry same format
                    # Check for "no data" errors or 404 - symbol may be delisted
                    elif "No price data found" in error_str or "delisted" in error_str.lower() or "no data" in error_str.lower() or "404" in error_str or "Not Found" in error_str:
                        # If 404 or delisted, don't retry - move to next ticker format immediately
                        if "404" in error_str or "Not Found" in error_str or "delisted" in error_str.lower():
                            print(f"Warning: {ticker_symbol}: Symbol not found or delisted (404/delisted), trying next ticker format")
                            break  # Break inner retry loop, try next ticker format immediately
                        # Otherwise, if last attempt, try next format
                        if attempt == retry_count - 1:
                            print(f"Warning: {ticker_symbol}: No price data available, trying next ticker format")
                            break  # Break inner retry loop, try next ticker format
                        continue  # Otherwise retry same format
                    else:
                        # Other errors - if last attempt, try next format
                        if attempt == retry_count - 1:
                            error_msg = f"{type(e).__name__}: {str(e)[:100]}"  # Limit error message length
                            print(f"Warning: {ticker_symbol}: Error '{error_msg}', trying next ticker format")
                            break  # Break inner retry loop, try next ticker format
                        continue  # Otherwise retry same format
        
        # If we've tried all ticker formats and still no price, return None
        print(f"Warning: Could not fetch price for {symbol} with yfinance")
        return None
    
    async def fetch_etf_price(self, symbol: str) -> Optional[GoldETF]:
        """
        Async wrapper for fetching ETF price using yfinance.
        """
        # Validate symbol before processing
        if not symbol or symbol.upper() not in self.GOLD_ETFS:
            return None
        
        # Use yfinance
        import asyncio
        loop = asyncio.get_event_loop()
        etf = await loop.run_in_executor(None, self.fetch_etf_price_sync, symbol)
        
        return etf
    
    async def fetch_all_etfs(self) -> List[GoldETF]:
        """
        Fetches prices for all tracked gold ETFs.
        Uses batch download when possible to reduce API calls.
        """
        # Try batch download first (more efficient)
        try:
            tickers = [info["ticker"] for info in self.GOLD_ETFS.values()]
            ticker_string = " ".join(tickers)
            
            # Rate limit before batch request
            self._rate_limit()
            
            # Use yfinance download for batch requests
            # Try different periods if needed
            data = None
            periods_to_try = ["1d", "5d", "1mo"]
            
            for period in periods_to_try:
                try:
                    data = yf.download(
                        ticker_string, 
                        period=period, 
                        progress=False, 
                        group_by='ticker',
                        timeout=15  # Increased timeout
                    )
                    if data is not None and not data.empty:
                        break  # Success, exit loop
                    else:
                        # Empty data - try next period
                        continue
                except Exception as download_error:
                    error_str = str(download_error)
                    if "429" in error_str or "Too Many Requests" in error_str:
                        # Rate limited - break to fall back to individual requests
                        raise
                    # JSON parsing errors - Yahoo Finance returned invalid response
                    if "Expecting value" in error_str or ("JSON" in error_str and "parse" in error_str.lower()):
                        # Try next period - might work with different period
                        continue
                    # No data for this period or 404 - try next one
                    if "No price data found" in error_str or "delisted" in error_str.lower() or "404" in error_str or "Not Found" in error_str:
                        # If 404, don't try other periods
                        if "404" in error_str or "Not Found" in error_str:
                            print(f"  {ticker_symbol}: 404 Not Found, symbol may be delisted")
                            break  # Break period loop
                        continue
                    # Other error - try next period
                    continue
            
            if data is None or data.empty:
                raise ValueError("No data available for any period")
            
            # Process the downloaded data
            if not data.empty:
                etfs = []
                for symbol, info in self.GOLD_ETFS.items():
                    # Skip inactive (delisted) symbols
                    if info.get("active") is False:
                        continue
                    
                    ticker_symbol = info["ticker"]
                    ticker_name = info["name"]
                    
                    # Extract data for this ticker
                    ticker_data = None
                    if isinstance(data.columns, pd.MultiIndex):
                        # MultiIndex columns (multiple tickers)
                        if ticker_symbol in data.columns.levels[0]:
                            ticker_data = data[ticker_symbol]
                    else:
                        # Single ticker or flat structure
                        # Check if this is a single ticker download
                        if len(self.GOLD_ETFS) == 1 or 'Close' in data.columns:
                            ticker_data = data
                    
                    if ticker_data is not None and not ticker_data.empty:
                        try:
                            current_price = float(ticker_data['Close'].iloc[-1])
                            previous_close = float(ticker_data['Close'].iloc[-2]) if len(ticker_data) > 1 else current_price
                            
                            change_percent = ((current_price - previous_close) / previous_close) * 100 if previous_close > 0 else 0.0
                            
                            # Get gold backing for this symbol (if available)
                            gold_backing = None
                            if symbol.upper() in self.GOLD_ETFS:
                                etf_info = self.GOLD_ETFS[symbol.upper()]
                                if "gold_backing_grams" in etf_info:
                                    gold_backing = etf_info["gold_backing_grams"]
                            
                            # Use fixed NAV value from GOLD_ETFS dictionary (will be updated in future)
                            nav_price = etf_info.get("nav_price") if etf_info else None
                            if nav_price:
                                print(f"{symbol}: NAV (sabit değer) = {nav_price:.4f} TL (GOLD_ETFS'den alındı)")
                            
                            # Calculate NAV using ETF-specific formulas (only if fixed NAV not available):
                            # 
                            # 1) GLDTR (QNB Portföy Altın Katılım BYF):
                            #    NAV_GLDTR = ((fiziki altın gramı × spot) + nakit) / pay sayısı
                            #    Portföyü ağırlıkla fiziki altın + az miktar nakit içerir.
                            #    Bu yüzden GLDTR'de 1 pay = sabit bir gram + küçük TL nakit gibi davranır.
                            #
                            # 2) ZGOLD (Ziraat Portföy Altın Katılım BYF):
                            #    NAV_ZGOLD = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                            #    Portföyü altın bazlı kira sertifikaları, altın hesapları ve fiziki altın içerir.
                            #    "Altın eşdeğeri gram", sertifikaların ve hesapların spot altına çevrilmiş karşılığıdır.
                            #
                            # 3) ISGLK (İş Portföy Altın Katılım BYF):
                            #    NAV_ISGLK = ((altın eşdeğeri gram × spot) + nakit) / pay sayısı
                            #    ZGOLD ile aynı mantık. Varlık türleri farklı olabilir ama hesap aynıdır.
                            #
                            # Basitleştirilmiş hesaplama (nakit kalemi küçük olduğu için yaklaşık):
                            # NAV ≈ (1 payın gramı) × (spot gram fiyatı)
                            # NAV değeri her zaman bu formüle göre hesaplanır (değişken)
                            # Note: If fixed NAV is not set, calculate it
                            if not nav_price:
                                if gold_backing and gold_backing > 0:
                                    try:
                                        print(f"{symbol}: Fetching gram gold price for NAV calculation...")
                                        gram_gold_price = self._fetch_gram_gold_price()
                                        if gram_gold_price is None:
                                            print(f"{symbol}: ERROR - gram_gold_price is None!")
                                        elif gram_gold_price == 0:
                                            print(f"{symbol}: ERROR - gram_gold_price is 0.00!")
                                        if gram_gold_price and gram_gold_price > 0:
                                            calculated_nav = gold_backing * gram_gold_price
                                            print(f"{symbol}: NAV Debug - gold_backing={gold_backing:.6f}, gram_gold_price={gram_gold_price:.2f}, calculated_nav={calculated_nav:.2f}")
                                            # Use calculated NAV if it's reasonable (between 0.1 and 10000 TL)
                                            if 0.1 <= calculated_nav <= 10000:
                                                nav_price = calculated_nav
                                                print(f"{symbol}: NAV (güncellenmiş) ≈ {gold_backing:.6f} gram × {gram_gold_price:.2f} TL/gram = {nav_price:.2f} TL (formüle göre hesaplandı)")
                                            else:
                                                print(f"Warning: {symbol} calculated NAV seems incorrect: {calculated_nav:.2f} TL (Gold backing: {gold_backing:.6f} gram, Gram price: {gram_gold_price:.2f} TL/gram)")
                                        else:
                                            print(f"Warning: {symbol} gram gold price is invalid: {gram_gold_price}")
                                    except Exception as nav_err:
                                        print(f"Warning: Could not calculate NAV for {symbol}: {type(nav_err).__name__}: {str(nav_err)[:100]}")
                                else:
                                    print(f"Warning: {symbol} gold_backing is invalid: {gold_backing}")
                            
                            # Try to get NAV from ticker info only as fallback if calculation failed
                            if not nav_price:
                                try:
                                    ticker = yf.Ticker(ticker_symbol)
                                    ticker_info = ticker.info
                                    nav_keys = ['navPrice', 'netAssetValue', 'nav', 'NAV', 'netAssetValuePerShare']
                                    for key in nav_keys:
                                        if key in ticker_info and ticker_info[key]:
                                            try:
                                                nav_price = float(ticker_info[key])
                                                if nav_price > 0:
                                                    print(f"{symbol}: NAV (fallback) = {nav_price:.2f} TL (ticker info'dan alındı)")
                                                    break
                                            except (ValueError, TypeError):
                                                continue
                                except Exception:
                                    pass
                            
                            # Print final NAV value
                            if nav_price:
                                print(f"{symbol}: Final NAV = {nav_price:.2f} TL")
                            else:
                                print(f"{symbol}: NAV hesaplanamadı")
                            
                            # Update gold_backing_grams from NAV if available (using fixed NAV values)
                            # Formula: gold_backing_grams = NAV / gram_gold_price
                            # This gives us the actual gold backing per share based on NAV
                            if nav_price and nav_price > 0:
                                if not gram_gold_price:
                                    # Try to fetch gram gold price if not already fetched
                                    gram_gold_price = self._fetch_gram_gold_price()
                                if gram_gold_price and gram_gold_price > 0:
                                    calculated_gold_backing = nav_price / gram_gold_price
                                    # Validate calculated gold_backing (should be reasonable, e.g., 0.01 to 1.0 grams per share)
                                    if 0.01 <= calculated_gold_backing <= 1.0:
                                        gold_backing = calculated_gold_backing
                                        print(f"{symbol}: gold_backing_grams NAV'dan güncellendi: {gold_backing:.6f} gram (NAV={nav_price:.2f} TL / gram_fiyat={gram_gold_price:.2f} TL/gram)")
                                    else:
                                        print(f"{symbol}: Warning - NAV'dan hesaplanan gold_backing makul değil: {calculated_gold_backing:.6f} gram, sabit değer kullanılıyor: {gold_backing}")
                            # If NAV not available or not from ticker, use static value from GOLD_ETFS dictionary
                            
                            # Get stopaj and expense ratio from ETF info
                            stopaj_rate = etf_info.get("stopaj_rate") if etf_info else None
                            expense_ratio = etf_info.get("expense_ratio") if etf_info else None
                            
                            etf = GoldETF(
                                symbol=symbol.upper(),
                                name=ticker_name,
                                current_price=round(current_price, 4),
                                change_percent=round(change_percent, 2),
                                volume=None,  # Volume not available in batch download
                                last_updated=datetime.now(),
                                gold_backing_grams=gold_backing,
                                nav_price=round(nav_price, 4) if nav_price else None,
                                stopaj_rate=stopaj_rate,
                                expense_ratio=expense_ratio
                            )
                            etfs.append(etf)
                            # Cache the result
                            self._cache[f"etf_{symbol.upper()}"] = etf
                        except (KeyError, IndexError) as e:
                            print(f"Error parsing batch data for {symbol}: {e}")
                            continue
                
                if etfs:
                    return etfs
        except Exception as e:
            error_msg = str(e)
            # Don't log the full error if it contains URL paths or rate limit messages
            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"Batch download failed due to rate limiting, falling back to individual requests")
            elif "Expecting value" in error_msg or ("JSON" in error_msg and "parse" in error_msg.lower()):
                print(f"Batch download failed: Yahoo Finance returned invalid response, falling back to individual requests")
            elif "No price data found" in error_msg or "delisted" in error_msg.lower():
                print(f"Batch download failed: Some symbols may have no data available, falling back to individual requests")
            else:
                print(f"Batch download failed, falling back to individual requests: {type(e).__name__}")
        
        # Fallback to individual requests with longer delays
        etfs = []
        for symbol, info in self.GOLD_ETFS.items():
            # Skip inactive (delisted) symbols
            if info.get("active") is False:
                print(f"Skipping {symbol} (marked as inactive/delisted)")
                continue
            
            etf = await self.fetch_etf_price(symbol)
            if etf:
                etfs.append(etf)
            # Add longer delay between requests to avoid rate limiting and blocking
            await asyncio.sleep(3.0)  # 3 seconds between requests
        
        # If we got at least some ETFs, return them (even if incomplete)
        if etfs:
            return etfs
        
        # Last resort: return cached data if available
        cached_etfs = []
        for symbol, info in self.GOLD_ETFS.items():
            # Skip inactive (delisted) symbols
            if info.get("active") is False:
                continue
            
            cache_key = f"etf_{symbol.upper()}"
            cached_etf = self._cache.get(cache_key)
            if cached_etf:
                cached_etfs.append(cached_etf)
        
        if cached_etfs:
            print("Warning: Returning cached data due to rate limiting")
            return cached_etfs
        
        return []
    

