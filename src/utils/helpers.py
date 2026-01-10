"""
Helper Utility Functions
"""

import random
import string
from datetime import datetime
from typing import Optional


def generate_sku(
    category_prefix: str = "SKU",
    length: int = 8,
) -> str:
    """
    Generate a random SKU code.
    
    Args:
        category_prefix: Prefix for the SKU
        length: Length of the random portion
        
    Returns:
        Generated SKU string
    """
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{category_prefix}-{random_part}"


def generate_location_code(
    zone: str,
    aisle: str,
    rack: str,
    shelf: str,
    bin: str,
) -> str:
    """
    Generate a standardized location code.
    
    Args:
        zone: Zone identifier
        aisle: Aisle number
        rack: Rack number
        shelf: Shelf level
        bin: Bin position
        
    Returns:
        Location code in format ZONE-AISLE-RACK-SHELF-BIN
    """
    return f"{zone}-{aisle}-{rack}-{shelf}-{bin}"


def calculate_cubic_volume(
    length_cm: float,
    width_cm: float,
    height_cm: float,
) -> float:
    """
    Calculate cubic volume in cubic meters.
    
    Args:
        length_cm: Length in centimeters
        width_cm: Width in centimeters
        height_cm: Height in centimeters
        
    Returns:
        Volume in cubic meters
    """
    return (length_cm * width_cm * height_cm) / 1_000_000


def format_currency(
    amount: float,
    currency_symbol: str = "$",
    decimals: int = 2,
) -> str:
    """
    Format a number as currency.
    
    Args:
        amount: The amount to format
        currency_symbol: Currency symbol to use
        decimals: Number of decimal places
        
    Returns:
        Formatted currency string
    """
    return f"{currency_symbol}{amount:,.{decimals}f}"


def calculate_reorder_date(
    current_stock: int,
    daily_demand: float,
    lead_time_days: int,
    safety_stock: int = 0,
) -> Optional[datetime]:
    """
    Calculate the date when reorder should be triggered.
    
    Args:
        current_stock: Current available stock
        daily_demand: Average daily consumption
        lead_time_days: Vendor lead time
        safety_stock: Safety stock buffer
        
    Returns:
        Datetime when reorder should be placed, or None if not needed
    """
    if daily_demand <= 0:
        return None
    
    # Calculate days until we hit reorder point
    reorder_point = (daily_demand * lead_time_days) + safety_stock
    
    if current_stock <= reorder_point:
        # Already at or below reorder point
        return datetime.utcnow()
    
    days_until_reorder = (current_stock - reorder_point) / daily_demand
    
    from datetime import timedelta
    return datetime.utcnow() + timedelta(days=days_until_reorder)


def classify_velocity(
    annual_sales_volume: float,
    total_skus_volume: list[float],
    a_threshold: float = 0.8,
    b_threshold: float = 0.95,
) -> str:
    """
    Classify a product's velocity using ABC analysis.
    
    Args:
        annual_sales_volume: This product's annual sales
        total_skus_volume: List of all SKUs' annual volumes
        a_threshold: Cumulative percentage for A items
        b_threshold: Cumulative percentage for B items
        
    Returns:
        "A", "B", or "C" classification
    """
    if not total_skus_volume:
        return "C"
    
    sorted_volumes = sorted(total_skus_volume, reverse=True)
    total_volume = sum(sorted_volumes)
    
    if total_volume == 0:
        return "C"
    
    cumulative = 0
    for i, vol in enumerate(sorted_volumes):
        cumulative += vol
        cumulative_pct = cumulative / total_volume
        
        if vol == annual_sales_volume:
            if cumulative_pct <= a_threshold:
                return "A"
            elif cumulative_pct <= b_threshold:
                return "B"
            else:
                return "C"
    
    return "C"


def parse_location_code(location_code: str) -> dict:
    """
    Parse a location code into its components.
    
    Args:
        location_code: Location code in format ZONE-AISLE-RACK-SHELF-BIN
        
    Returns:
        Dictionary with zone, aisle, rack, shelf, bin
    """
    parts = location_code.split("-")
    
    if len(parts) >= 5:
        return {
            "zone": parts[0],
            "aisle": parts[1],
            "rack": parts[2],
            "shelf": parts[3],
            "bin": parts[4],
        }
    elif len(parts) >= 3:
        return {
            "zone": parts[0],
            "aisle": parts[1],
            "rack": parts[2] if len(parts) > 2 else "",
            "shelf": parts[3] if len(parts) > 3 else "",
            "bin": parts[4] if len(parts) > 4 else "",
        }
    else:
        return {
            "zone": location_code,
            "aisle": "",
            "rack": "",
            "shelf": "",
            "bin": "",
        }
