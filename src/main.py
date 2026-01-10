"""
Inventory Management Agent - Main Application Entry Point

FastAPI application for the warehouse inventory management system.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.db import init_db, close_db
from src.api.routes import router


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Inventory Management Agent", warehouse_id=settings.warehouse_id)
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Inventory Management Agent")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Inventory Management Agent",
    description="""
    An autonomous AI system for real-time warehouse logistics, 
    predictive replenishment, and spatial optimization.
    
    ## Features
    
    - **Real-time Stock Tracking**: Track inventory across all warehouse locations
    - **Intelligent Replenishment**: ML-driven reorder point optimization
    - **Pick Route Optimization**: Graph-based path optimization for pickers
    - **Environmental Monitoring**: IoT sensor integration for cold chain compliance
    - **Multi-Agent Architecture**: Specialized agents for different warehouse functions
    
    ## Agents
    
    - **Tracking Agent**: Manages digital twin of physical inventory
    - **Replenishment Agent**: Handles procurement and vendor management
    - **Operations Agent**: Optimizes picking and putaway workflows
    - **Audit Agent**: Conducts cycle counts and reconciliation
    - **Quality Agent**: Monitors expiration and environmental conditions
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Inventory Management Agent",
        "version": "0.1.0",
        "warehouse_id": settings.warehouse_id,
        "warehouse_name": settings.warehouse_name,
        "docs": "/docs",
        "health": "/health",
    }


def main():
    """Run the application with uvicorn."""
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
