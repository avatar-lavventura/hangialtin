from typing import List, Optional
from app.models import GoldETF, ComparisonResult


class ComparisonService:
    """
    Service to compare gold ETFs and find the cheapest option.
    Similar to hangikredi's comparison approach.
    """
    
    @staticmethod
    def find_cheapest(etfs: List[GoldETF]) -> Optional[GoldETF]:
        """
        Finds the cheapest gold ETF based on current price.
        """
        if not etfs:
            return None
        
        return min(etfs, key=lambda x: x.current_price)
    
    @staticmethod
    def compare_etfs(etfs: List[GoldETF]) -> ComparisonResult:
        """
        Compares all gold ETFs by unit gold price (TL/gram).
        Returns detailed comparison based on price per gram of gold backing.
        """
        if not etfs:
            raise ValueError("No ETFs provided for comparison")
        
        # Filter ETFs with gold backing information
        etfs_with_backing = [etf for etf in etfs if etf.gold_backing_grams]
        
        if not etfs_with_backing:
            # Fallback to unit price comparison if no gold backing info
            cheapest = ComparisonService.find_cheapest(etfs)
            price_difference = {}
            for etf in etfs:
                if etf.symbol != cheapest.symbol:
                    diff = etf.current_price - cheapest.current_price
                    diff_percent = (diff / cheapest.current_price) * 100
                    price_difference[etf.symbol] = {
                        "absolute": round(diff, 4),
                        "percent": round(diff_percent, 2)
                    }
            
            recommendation = (
                f"Birim fiyatına göre en ucuz seçenek: {cheapest.symbol} "
                f"({cheapest.current_price} TL/birim)."
            )
            
            return ComparisonResult(
                cheapest=cheapest,
                all_etfs=sorted(etfs, key=lambda x: x.current_price),
                price_difference=price_difference,
                recommendation=recommendation
            )
        
        # Calculate price per gram for each ETF with gold backing
        etfs_with_per_gram = []
        for etf in etfs_with_backing:
            per_gram_price = etf.current_price / etf.gold_backing_grams
            etfs_with_per_gram.append((etf, per_gram_price))
        
        # Sort by price per gram (cheapest first)
        etfs_with_per_gram.sort(key=lambda x: x[1])
        cheapest_per_gram_etf, cheapest_per_gram_price = etfs_with_per_gram[0]
        
        # Calculate price differences per gram for ALL ETFs (including those without gold backing)
        price_difference = {}
        for etf in etfs:
            if etf.gold_backing_grams:
                # For ETFs with gold backing, compare per-gram prices
                per_gram_price = etf.current_price / etf.gold_backing_grams
                if etf.symbol != cheapest_per_gram_etf.symbol:
                    diff = per_gram_price - cheapest_per_gram_price
                    diff_percent = (diff / cheapest_per_gram_price) * 100
                    price_difference[etf.symbol] = {
                        "absolute": round(diff, 4),
                        "percent": round(diff_percent, 2),
                        "per_gram_price": round(per_gram_price, 4)
                    }
            else:
                # For ETFs without gold backing, we can't compare per-gram, so skip
                pass
        
        # Generate recommendation based on per-gram price
        if price_difference:
            avg_diff = sum(diff["percent"] for diff in price_difference.values()) / len(price_difference)
            recommendation = (
                f"Gram başına fiyatına göre en ucuz seçenek: {cheapest_per_gram_etf.symbol} "
                f"({round(cheapest_per_gram_price, 4)} TL/gram). "
                f"Ortalama olarak diğer seçeneklerden %{round(avg_diff, 2)} daha ucuz."
            )
        else:
            recommendation = (
                f"Tek seçenek: {cheapest_per_gram_etf.symbol} "
                f"({round(cheapest_per_gram_price, 4)} TL/gram)."
            )
        
        # Return ETFs sorted by per-gram price
        sorted_etfs = [etf for etf, _ in etfs_with_per_gram]
        # Add ETFs without gold backing info at the end
        etfs_without_backing = [etf for etf in etfs if not etf.gold_backing_grams]
        sorted_etfs.extend(sorted(etfs_without_backing, key=lambda x: x.current_price))
        
        return ComparisonResult(
            cheapest=cheapest_per_gram_etf,
            all_etfs=sorted_etfs,
            price_difference=price_difference,
            recommendation=recommendation
        )
    
    @staticmethod
    def get_best_value(etfs: List[GoldETF]) -> Optional[GoldETF]:
        """
        Finds the best value ETF considering price and other factors.
        Can be extended to include fees, liquidity, etc.
        """
        if not etfs:
            return None
        
        # For now, just return cheapest
        # Can be enhanced with:
        # - Trading fees
        # - Spread
        # - Liquidity (volume)
        # - Historical performance
        return ComparisonService.find_cheapest(etfs)
    
    @staticmethod
    def compare_two_etfs(etf1: GoldETF, etf2: GoldETF) -> dict:
        """
        Compares two specific ETFs by unit price.
        Returns detailed comparison information including per-gram comparison if gold backing is available.
        """
        # Determine which is cheaper
        cheaper = etf1 if etf1.current_price < etf2.current_price else etf2
        more_expensive = etf2 if cheaper.symbol == etf1.symbol else etf1
        
        # Calculate differences
        price_diff = more_expensive.current_price - cheaper.current_price
        price_diff_percent = (price_diff / cheaper.current_price) * 100
        
        # Calculate per-gram prices if gold backing is available
        per_gram_comparison = None
        if etf1.gold_backing_grams and etf2.gold_backing_grams:
            etf1_per_gram = etf1.current_price / etf1.gold_backing_grams
            etf2_per_gram = etf2.current_price / etf2.gold_backing_grams
            cheaper_per_gram = etf1_per_gram if etf1_per_gram < etf2_per_gram else etf2_per_gram
            more_expensive_per_gram = etf2_per_gram if cheaper_per_gram == etf1_per_gram else etf1_per_gram
            per_gram_diff = more_expensive_per_gram - cheaper_per_gram
            per_gram_diff_percent = (per_gram_diff / cheaper_per_gram) * 100
            
            per_gram_comparison = {
                "etf1_per_gram": round(etf1_per_gram, 4),
                "etf2_per_gram": round(etf2_per_gram, 4),
                "cheaper_per_gram": round(cheaper_per_gram, 4),
                "difference_per_gram": round(per_gram_diff, 4),
                "difference_percent": round(per_gram_diff_percent, 2),
                "cheaper_per_gram_symbol": etf1.symbol if cheaper_per_gram == etf1_per_gram else etf2.symbol
            }
        
        return {
            "etf1": {
                "symbol": etf1.symbol,
                "name": etf1.name,
                "price": etf1.current_price,
                "change_percent": etf1.change_percent,
                "volume": etf1.volume,
                "gold_backing_grams": etf1.gold_backing_grams
            },
            "etf2": {
                "symbol": etf2.symbol,
                "name": etf2.name,
                "price": etf2.current_price,
                "change_percent": etf2.change_percent,
                "volume": etf2.volume,
                "gold_backing_grams": etf2.gold_backing_grams
            },
            "cheaper": {
                "symbol": cheaper.symbol,
                "name": cheaper.name,
                "price": cheaper.current_price
            },
            "price_difference": {
                "absolute": round(price_diff, 4),
                "percent": round(price_diff_percent, 2)
            },
            "per_gram_comparison": per_gram_comparison,
            "comparison": f"{cheaper.symbol} ({cheaper.current_price} TL) {more_expensive.symbol}'den {round(price_diff, 4)} TL (%{round(price_diff_percent, 2)}) daha ucuz.",
            "recommendation": f"Birim fiyatına göre {cheaper.symbol} daha ucuz: {cheaper.current_price} TL vs {more_expensive.current_price} TL (Fark: {round(price_diff, 4)} TL, %{round(price_diff_percent, 2)})"
        }

