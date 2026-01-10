# Inventory Management Agent - Project Context

## Overview
This is a **multi-agent warehouse management system** built with LangChain/LangGraph and FastAPI. It manages inventory tracking, automated replenishment, warehouse operations optimization, and IoT sensor monitoring.

## Tech Stack
- **Python 3.11+** with type hints
- **LangChain 0.1.0+ / LangGraph** - AI agent framework with tool-calling
- **FastAPI** - REST API backend (async)
- **SQLAlchemy 2.0** - ORM with async support (asyncpg for PostgreSQL)
- **OpenAI GPT-4o** - Primary LLM (configurable via `OPENAI_MODEL`)
- **NetworkX** - Graph-based pick route optimization (TSP)
- **Pydantic v2** - Data validation and settings
- **PostgreSQL** - Database (with optional GIS extensions)

## Project Structure
```
src/
├── config.py                  # Settings from environment variables
├── main.py                    # FastAPI entry point (uvicorn)
├── models/
│   ├── inventory.py           # 12 SQLAlchemy models, 5 enums
│   └── schemas.py             # ~30 Pydantic request/response schemas
├── db/
│   └── database.py            # Async/sync session factories
├── tools/                     # LangChain @tool decorated functions
│   ├── inventory_tools.py     # get_stock_level, update_stock_quantity, reconcile_inventory, allocate_stock, deallocate_stock, get_inventory_by_location, get_expiring_items
│   ├── replenishment_tools.py # calculate_reorder_point, calculate_eoq, get_vendor_info, create_purchase_order, get_pending_purchase_orders, calculate_days_of_cover
│   ├── operations_tools.py    # generate_pick_route (TSP), get_optimal_putaway_location, get_warehouse_layout, calculate_route_distance
│   └── sensor_tools.py        # get_sensor_readings, check_environmental_alerts, get_location_conditions
├── agents/                    # LangGraph StateGraph agents
│   ├── tracking_agent.py      # Digital twin - inventory state management
│   ├── replenishment_agent.py # Procurement - EOQ, JIT, vendor selection
│   ├── operations_agent.py    # Workflow - picking routes, putaway optimization
│   ├── audit_agent.py         # Compliance - cycle counts, discrepancy resolution
│   ├── quality_agent.py       # Quality - expiration, cold chain, FIFO
│   └── orchestrator.py        # Central router - analyzes requests, delegates to specialists
├── api/
│   └── routes.py              # All REST endpoints under /api/v1
└── utils/
    └── helpers.py             # generate_sku, format_currency, date helpers

scripts/
└── seed_database.py           # Populates DB with sample products, vendors, locations

tests/
├── conftest.py                # Pytest fixtures (SQLite in-memory for tests)
├── test_inventory_tools.py    # Inventory tool test stubs
└── test_operations_tools.py   # Operations tool test stubs
```

## Database Models (src/models/inventory.py)
| Model | Purpose |
|-------|---------|
| Product | SKU, name, category, reorder_point, reorder_quantity, lead_time_days |
| InventoryItem | Links Product to Location with quantity, lot_number, expiration_date |
| Location | Warehouse zones/bins with coordinates (aisle, rack, level) |
| Vendor | Supplier info with lead_time, reliability_score |
| PurchaseOrder | Header for procurement orders |
| PurchaseOrderLine | Line items for POs |
| PickOrder | Header for pick/ship orders |
| PickOrderLine | Line items with pick sequence |
| SensorReading | IoT data (temperature, humidity) by location |
| AuditLog | System event tracking |
| Alert | Active alerts (low_stock, expiring, environmental) |

## Key Enums
- `LocationType`: RECEIVING, STORAGE, PICKING, SHIPPING, COLD_STORAGE
- `OrderStatus`: DRAFT, PENDING, APPROVED, IN_PROGRESS, COMPLETED, CANCELLED
- `AlertType`: LOW_STOCK, EXPIRING_SOON, ENVIRONMENTAL, DISCREPANCY
- `AlertSeverity`: LOW, MEDIUM, HIGH, CRITICAL

## API Endpoints (src/api/routes.py)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/v1/stock/{sku} | Get stock level for SKU |
| GET | /api/v1/stock | List all stock levels |
| PATCH | /api/v1/stock/reconcile | Reconcile inventory counts |
| POST | /api/v1/pick/generate | Generate optimized pick route |
| GET | /api/v1/alerts/iot | Get IoT/environmental alerts |
| GET | /api/v1/alerts | Get all active alerts |
| POST | /api/v1/replenish/approve | Approve purchase order |
| GET | /api/v1/replenish/suggestions | Get reorder suggestions |
| POST | /api/v1/agent/query | Natural language query to orchestrator |
| GET | /api/v1/health | Health check |

## Agent Architecture
The **Orchestrator** (src/agents/orchestrator.py) receives all requests and routes to specialized agents:

1. **Tracking Agent** - "What's the stock level of SKU-001?"
2. **Replenishment Agent** - "Should we reorder product X?"
3. **Operations Agent** - "Generate pick route for order #123"
4. **Audit Agent** - "Run cycle count for zone A"
5. **Quality Agent** - "Check for expiring items in cold storage"

Each agent uses LangGraph's `StateGraph` with:
- `agent_node` - LLM reasoning with tools
- `tools` - ToolNode executing @tool functions
- `extract_result` - Formats final response

## Environment Variables (.env)
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/inventory_db
SYNC_DATABASE_URL=postgresql://user:pass@localhost:5432/inventory_db
# Optional: MQTT_BROKER_HOST, MQTT_BROKER_PORT for IoT
```

## Common Development Tasks

### Adding a new tool
1. Add function in appropriate `src/tools/*.py` with `@tool` decorator
2. Import in the relevant agent's tool list
3. Tool must use sync database session (tools run in sync context)

### Adding a new agent
1. Create `src/agents/new_agent.py` following existing pattern
2. Define tools list, SYSTEM_PROMPT, AgentState TypedDict
3. Build StateGraph with agent_node, tools, extract_result
4. Add to `AgentType` enum in orchestrator.py
5. Update orchestrator's routing logic

### Adding a new endpoint
1. Add route in `src/api/routes.py`
2. Create Pydantic schemas in `src/models/schemas.py`
3. Use `async def` for async database operations

## Testing
```bash
pytest tests/ -v
```
Tests use SQLite in-memory database (see tests/conftest.py).

## Notes for AI Assistants
- LangChain tools MUST be synchronous (use `get_sync_session()`)
- API routes are async (use `get_async_session()`)
- Pick route optimization uses nearest-neighbor TSP heuristic
- Putaway uses A/B/C velocity classification
- All coordinates are (aisle, rack, level) tuples
