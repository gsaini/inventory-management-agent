"""
Inventory Management Agent - Configuration Module
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="Primary LLM model")
    openai_model_mini: str = Field(default="gpt-4o-mini", description="Fast LLM model")

    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db",
        description="Async database connection URL",
    )
    database_sync_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/inventory_db",
        description="Sync database connection URL",
    )

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # MQTT/IoT Configuration
    mqtt_broker_host: str = Field(default="localhost", description="MQTT broker host")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker port")
    mqtt_username: Optional[str] = Field(default=None, description="MQTT username")
    mqtt_password: Optional[str] = Field(default=None, description="MQTT password")
    mqtt_topic_prefix: str = Field(
        default="warehouse/sensors", description="MQTT topic prefix for sensors"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_debug: bool = Field(default=False, description="Enable debug mode")

    # Warehouse Configuration
    warehouse_id: str = Field(default="WH001", description="Warehouse identifier")
    warehouse_name: str = Field(
        default="Main Distribution Center", description="Warehouse name"
    )

    # Alert Thresholds
    temp_min_celsius: float = Field(default=2.0, description="Minimum temperature threshold")
    temp_max_celsius: float = Field(default=8.0, description="Maximum temperature threshold")
    humidity_min_percent: float = Field(default=30.0, description="Minimum humidity threshold")
    humidity_max_percent: float = Field(default=60.0, description="Maximum humidity threshold")

    # Replenishment Settings
    default_lead_time_days: int = Field(default=7, description="Default vendor lead time")
    safety_stock_days: int = Field(default=3, description="Safety stock buffer in days")
    reorder_check_interval_hours: int = Field(
        default=1, description="Interval for checking reorder points"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
