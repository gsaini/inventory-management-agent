"""
Inventory Management Agent - Configuration Module

Supports multiple LLM providers:
- ollama: Local open-source models (recommended for development)
- openai: OpenAI API (GPT-4o, etc.)
- openai_compatible: Any OpenAI-compatible API (vLLM, LM Studio, LocalAI)
- huggingface: HuggingFace Inference API
"""

from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    HUGGINGFACE = "huggingface"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM Provider Selection
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OLLAMA,
        description="LLM provider: ollama, openai, openai_compatible, huggingface",
    )

    # Ollama Configuration (Local Open Source - Recommended)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )
    ollama_model: str = Field(
        default="llama4:scout",
        description="Primary Ollama model",
    )
    ollama_model_mini: str = Field(
        default="llama4:scout",
        description="Fast/small Ollama model",
    )

    # OpenAI-Compatible API Configuration (vLLM, LM Studio, LocalAI, etc.)
    openai_compatible_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="OpenAI-compatible API base URL",
    )
    openai_compatible_api_key: str = Field(
        default="not-needed",
        description="API key for OpenAI-compatible server (often not needed for local)",
    )
    openai_compatible_model: str = Field(
        default="local-model",
        description="Model name for OpenAI-compatible API",
    )

    # OpenAI Configuration (Cloud)
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
    )
    openai_model: str = Field(default="gpt-4o", description="Primary OpenAI model")
    openai_model_mini: str = Field(default="gpt-4o-mini", description="Fast OpenAI model")

    # HuggingFace Configuration
    huggingface_api_key: Optional[str] = Field(
        default=None,
        description="HuggingFace API key",
    )
    huggingface_model: str = Field(
        default="meta-llama/Llama-4-Scout-17B-16E-Instruct",
        description="HuggingFace model ID",
    )

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
