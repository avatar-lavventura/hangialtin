from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class GoldETF(BaseModel):
    symbol: str
    name: str
    current_price: float
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    last_updated: Optional[datetime] = None
    gold_backing_grams: Optional[float] = None  # Altın karşılığı (gram)
    nav_price: Optional[float] = None  # Net Asset Value (NAV)
    stopaj_rate: Optional[float] = None  # Stopaj oranı (%)
    expense_ratio: Optional[float] = None  # Yönetim ücreti/harcama oranı (%)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ComparisonResult(BaseModel):
    cheapest: GoldETF
    all_etfs: List[GoldETF]
    price_difference: Dict[str, Dict[str, float]]  # Difference from cheapest: {symbol: {"absolute": diff, "percent": diff%}}
    recommendation: str
    spot_gram_gold_price: Optional[float] = None  # Spot gram altın fiyatı (TL/gram)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
