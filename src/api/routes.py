"""
FastAPI Routes

API endpoints for the Inventory Management Agent system.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.models.inventory import (
    Product,
    InventoryItem,
    Location,
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
    PickOrder,
    PickOrderLine,
    Alert,
    SensorReading,
    OrderStatus,
    AlertSeverity,
)
from src.models.schemas import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockLevelResponse,
    ReconciliationRequest,
    ReconciliationResponse,
    PickOrderRequest,
    PickRouteResponse,
    PickRouteStep,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderApproval,
    AlertResponse,
    SensorReadingCreate,
    SensorReadingResponse,
    LocationCreate,
    LocationResponse,
    VendorCreate,
    VendorResponse,
)
from src.api.dependencies import WarehouseDep
from src.agents.orchestrator import process_request


router = APIRouter()


# ============================================================================
# Stock Endpoints
# ============================================================================


@router.get("/api/v1/stock/{sku}", response_model=StockLevelResponse, tags=["Stock"])
async def get_stock_level(
    sku: str,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Get real-time stock count for a SKU.
    
    Returns aggregated stock across all warehouse locations.
    """
    # Get product
    result = await db.execute(select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku}' not found",
        )
    
    # Get inventory items
    result = await db.execute(
        select(InventoryItem)
        .options(selectinload(InventoryItem.location))
        .where(InventoryItem.product_id == product.id)
    )
    inventory_items = result.scalars().all()
    
    total_on_hand = sum(item.quantity_on_hand for item in inventory_items)
    total_allocated = sum(item.quantity_allocated for item in inventory_items)
    total_available = total_on_hand - total_allocated
    
    # Determine status
    if total_available <= 0:
        stock_status = "out_of_stock"
    elif total_available < product.min_stock_level:
        stock_status = "critical"
    elif total_available < product.reorder_point:
        stock_status = "low"
    else:
        stock_status = "ok"
    
    locations = [
        {
            "location_code": item.location.code,
            "zone": item.location.zone,
            "quantity_on_hand": item.quantity_on_hand,
            "quantity_available": item.quantity_on_hand - item.quantity_allocated,
        }
        for item in inventory_items
        if item.quantity_on_hand > 0
    ]
    
    return StockLevelResponse(
        sku=sku,
        product_name=product.name,
        total_on_hand=total_on_hand,
        total_allocated=total_allocated,
        total_available=total_available,
        reorder_point=product.reorder_point,
        locations=locations,
        status=stock_status,
    )


@router.patch("/api/v1/stock/reconcile", response_model=ReconciliationResponse, tags=["Stock"])
async def reconcile_stock(
    request: ReconciliationRequest,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Manual/Audit update for stock reconciliation.
    
    Used after cycle counts to sync physical and system inventory.
    """
    # Use the audit agent for reconciliation
    from src.tools.inventory_tools import reconcile_inventory
    
    result = reconcile_inventory.invoke({
        "sku": request.sku,
        "location_code": request.location_code,
        "counted_quantity": request.counted_quantity,
        "performed_by": request.performed_by,
        "reason": request.reason,
    })
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    return ReconciliationResponse(
        success=True,
        sku=request.sku,
        location_code=request.location_code,
        previous_quantity=result.get("system_quantity", 0),
        new_quantity=request.counted_quantity,
        variance=result.get("variance", 0),
        audit_log_id=result.get("audit_log_id", ""),
    )


# ============================================================================
# Pick Order Endpoints
# ============================================================================


@router.post("/api/v1/pick/generate", response_model=PickRouteResponse, tags=["Picking"])
async def generate_pick_route(
    request: PickOrderRequest,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an optimized pick route for a set of items.
    
    Uses graph-based optimization to minimize travel distance.
    """
    from src.tools.operations_tools import generate_pick_route as gen_route
    
    items = [{"sku": item.sku, "quantity": item.quantity} for item in request.items]
    result = gen_route.invoke({"items": items})
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    
    # Create pick order in database
    order_number = f"PICK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    
    pick_order = PickOrder(
        id=str(uuid4()),
        order_number=order_number,
        customer_order_ref=request.customer_order_ref,
        status=OrderStatus.PENDING,
        priority=request.priority,
        total_items=result.get("total_items", 0),
        total_units=result.get("total_units", 0),
        estimated_time_minutes=result.get("estimated_time_minutes"),
        pick_route=str(result.get("route", [])),
    )
    db.add(pick_order)
    await db.commit()
    
    route_steps = [
        PickRouteStep(
            sequence=step["sequence"],
            location_code=step["location_code"],
            sku=step["sku"],
            product_name=step["product_name"],
            quantity=step["quantity"],
            zone=step["zone"],
            aisle=step["aisle"],
            coordinates=step["coordinates"],
        )
        for step in result.get("route", [])
    ]
    
    return PickRouteResponse(
        order_number=order_number,
        total_items=result.get("total_items", 0),
        total_units=result.get("total_units", 0),
        estimated_time_minutes=result.get("estimated_time_minutes", 0),
        total_distance_meters=result.get("total_distance_meters", 0),
        route=route_steps,
    )


# ============================================================================
# Alert Endpoints
# ============================================================================


@router.get("/api/v1/alerts/iot", response_model=list[AlertResponse], tags=["Alerts"])
async def get_iot_alerts(
    warehouse_id: WarehouseDep,
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current IoT sensor warnings and alerts.
    
    Includes temperature, humidity, and shock alerts.
    """
    query = select(Alert).order_by(Alert.created_at.desc())
    
    if severity:
        query = query.where(Alert.severity == severity)
    
    if acknowledged is not None:
        query = query.where(Alert.is_acknowledged == acknowledged)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return [
        AlertResponse(
            id=alert.id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            entity_type=alert.entity_type,
            entity_id=alert.entity_id,
            is_acknowledged=alert.is_acknowledged,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]


# ============================================================================
# Replenishment Endpoints
# ============================================================================


@router.post("/api/v1/replenish/approve", response_model=PurchaseOrderResponse, tags=["Replenishment"])
async def approve_purchase_order(
    request: PurchaseOrderApproval,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending purchase order.
    """
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.po_number == request.po_number)
    )
    po = result.scalar_one_or_none()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order '{request.po_number}' not found",
        )
    
    if po.status not in [OrderStatus.DRAFT, OrderStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve PO in status '{po.status.value}'",
        )
    
    po.status = OrderStatus.APPROVED
    po.approved_by = request.approved_by
    po.approved_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(po)
    
    return PurchaseOrderResponse(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        status=po.status,
        order_date=po.order_date,
        expected_delivery_date=po.expected_delivery_date,
        total_amount=po.total_amount,
        lines=[],  # Simplified for now
        notes=po.notes,
        created_by=po.created_by,
        created_at=po.created_at,
    )


# ============================================================================
# Product Management Endpoints
# ============================================================================


@router.post("/api/v1/products", response_model=ProductResponse, tags=["Products"])
async def create_product(
    product: ProductCreate,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new product."""
    # Check for existing SKU
    result = await db.execute(select(Product).where(Product.sku == product.sku))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU '{product.sku}' already exists",
        )
    
    db_product = Product(
        id=str(uuid4()),
        **product.model_dump(),
    )
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    
    return db_product


@router.get("/api/v1/products", response_model=list[ProductResponse], tags=["Products"])
async def list_products(
    warehouse_id: WarehouseDep,
    category: Optional[str] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all products with optional filtering."""
    query = select(Product)
    
    if category:
        query = query.where(Product.category == category)
    
    if active_only:
        query = query.where(Product.is_active == True)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================================
# Location Management Endpoints
# ============================================================================


@router.post("/api/v1/locations", response_model=LocationResponse, tags=["Locations"])
async def create_location(
    location: LocationCreate,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new warehouse location."""
    result = await db.execute(select(Location).where(Location.code == location.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Location '{location.code}' already exists",
        )
    
    db_location = Location(
        id=str(uuid4()),
        **location.model_dump(),
    )
    db.add(db_location)
    await db.commit()
    await db.refresh(db_location)
    
    return db_location


@router.get("/api/v1/locations", response_model=list[LocationResponse], tags=["Locations"])
async def list_locations(
    warehouse_id: WarehouseDep,
    zone: Optional[str] = None,
    location_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List warehouse locations."""
    query = select(Location).where(Location.is_active == True)
    
    if zone:
        query = query.where(Location.zone == zone)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================================
# Vendor Management Endpoints
# ============================================================================


@router.post("/api/v1/vendors", response_model=VendorResponse, tags=["Vendors"])
async def create_vendor(
    vendor: VendorCreate,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new vendor."""
    result = await db.execute(select(Vendor).where(Vendor.code == vendor.code))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vendor '{vendor.code}' already exists",
        )
    
    db_vendor = Vendor(
        id=str(uuid4()),
        **vendor.model_dump(),
    )
    db.add(db_vendor)
    await db.commit()
    await db.refresh(db_vendor)
    
    return db_vendor


@router.get("/api/v1/vendors", response_model=list[VendorResponse], tags=["Vendors"])
async def list_vendors(
    warehouse_id: WarehouseDep,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all vendors."""
    query = select(Vendor)
    
    if active_only:
        query = query.where(Vendor.is_active == True)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================================
# Sensor Data Endpoints
# ============================================================================


@router.post("/api/v1/sensors/readings", response_model=SensorReadingResponse, tags=["Sensors"])
async def create_sensor_reading(
    reading: SensorReadingCreate,
    warehouse_id: WarehouseDep,
    db: AsyncSession = Depends(get_db),
):
    """Record a new sensor reading (typically from IoT devices)."""
    db_reading = SensorReading(
        id=str(uuid4()),
        **reading.model_dump(),
    )
    db.add(db_reading)
    await db.commit()
    await db.refresh(db_reading)
    
    return db_reading


# ============================================================================
# Agent Interaction Endpoint
# ============================================================================


@router.post("/api/v1/agent/query", tags=["Agent"])
async def query_agent(
    query: str,
    warehouse_id: WarehouseDep,
):
    """
    Send a natural language query to the inventory management agent.
    
    The orchestrator will route your request to the appropriate specialized agent.
    
    Example queries:
    - "What's the current stock level for SKU-12345?"
    - "Generate a pick route for order items A, B, and C"
    - "Do we need to reorder any products?"
    - "Check for any environmental alerts"
    - "Reconcile inventory at location A-01-01-01"
    """
    result = await process_request(query)
    
    return {
        "query": query,
        "warehouse_id": warehouse_id,
        "response": result.get("response", ""),
        "agent_used": result.get("agent_used", ""),
        "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
    }


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "inventory-management-agent",
    }
