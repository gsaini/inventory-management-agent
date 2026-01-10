"""
API Dependencies

Common dependencies for FastAPI routes.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.config import get_settings, Settings


async def get_current_warehouse(
    x_warehouse_id: Annotated[str | None, Header()] = None,
) -> str:
    """
    Get the current warehouse ID from headers or config.
    
    Args:
        x_warehouse_id: Optional warehouse ID from request header
        
    Returns:
        Warehouse ID to use for the request
    """
    settings = get_settings()
    return x_warehouse_id or settings.warehouse_id


async def get_settings_dep() -> Settings:
    """Get application settings as a dependency."""
    return get_settings()


WarehouseDep = Annotated[str, Depends(get_current_warehouse)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
