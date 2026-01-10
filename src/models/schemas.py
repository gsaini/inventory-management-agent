"""
Pydantic Schemas for API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Enums (matching database enums)
# ============================================================================


class LocationType(str, Enum):
    RECEIVING = "receiving"
    STORAGE = "storage"
    PICKING = "picking"
    PACKING = "packing"
    SHIPPING = "shipping"
    COLD_STORAGE = "cold_storage"
    HAZMAT = "hazmat"


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    LOW_STOCK = "low_stock"
    EXPIRY_WARNING = "expiry_warning"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SHRINKAGE = "shrinkage"
    DISCREPANCY = "discrepancy"
    SENSOR_OFFLINE = "sensor_offline"


# ============================================================================
# Product Schemas
# ============================================================================


class ProductBase(BaseModel):
    """Base product schema."""

    sku: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    category: str = Field(..., max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    unit_of_measure: str = Field(default="EACH", max_length=20)
    weight_kg: Optional[float] = None
    requires_cold_storage: bool = False
    is_fragile: bool = False
    is_hazmat: bool = False
    shelf_life_days: Optional[int] = None
    barcode: Optional[str] = Field(None, max_length=50)
    reorder_point: int = Field(default=10, ge=0)
    reorder_quantity: int = Field(default=50, ge=1)
    velocity_class: str = Field(default="C", pattern="^[ABC]$")
    unit_cost: float = Field(default=0.0, ge=0)


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    reorder_point: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=1)
    velocity_class: Optional[str] = Field(None, pattern="^[ABC]$")
    unit_cost: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Product response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Location Schemas
# ============================================================================


class LocationBase(BaseModel):
    """Base location schema."""

    code: str = Field(..., max_length=50)
    zone: str = Field(..., max_length=10)
    aisle: str = Field(..., max_length=10)
    rack: str = Field(..., max_length=10)
    shelf: str = Field(..., max_length=10)
    bin: str = Field(..., max_length=10)
    location_type: LocationType = LocationType.STORAGE
    capacity_units: int = Field(default=100, ge=1)
    x_coordinate: float = 0.0
    y_coordinate: float = 0.0
    z_coordinate: float = 0.0
    has_temperature_control: bool = False


class LocationCreate(LocationBase):
    """Schema for creating a location."""

    pass


class LocationResponse(LocationBase):
    """Location response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    current_units: int
    is_active: bool
    created_at: datetime


# ============================================================================
# Inventory Schemas
# ============================================================================


class InventoryItemBase(BaseModel):
    """Base inventory item schema."""

    product_id: str
    location_id: str
    quantity_on_hand: int = Field(default=0, ge=0)
    lot_number: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, max_length=50)
    expiry_date: Optional[datetime] = None


class InventoryItemCreate(InventoryItemBase):
    """Schema for creating inventory."""

    pass


class InventoryItemUpdate(BaseModel):
    """Schema for updating inventory."""

    quantity_on_hand: Optional[int] = Field(None, ge=0)
    quantity_allocated: Optional[int] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None


class InventoryItemResponse(InventoryItemBase):
    """Inventory item response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    quantity_allocated: int
    quantity_available: int
    received_date: datetime
    last_counted_at: Optional[datetime]
    last_movement_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class StockLevelResponse(BaseModel):
    """Aggregated stock level for a SKU."""

    sku: str
    product_name: str
    total_on_hand: int
    total_allocated: int
    total_available: int
    reorder_point: int
    locations: list[dict]
    status: str  # "ok", "low", "critical", "out_of_stock"


class ReconciliationRequest(BaseModel):
    """Request to reconcile stock."""

    sku: str
    location_code: str
    counted_quantity: int = Field(..., ge=0)
    reason: Optional[str] = None
    performed_by: str = "system"


class ReconciliationResponse(BaseModel):
    """Response from stock reconciliation."""

    success: bool
    sku: str
    location_code: str
    previous_quantity: int
    new_quantity: int
    variance: int
    audit_log_id: str


# ============================================================================
# Vendor & Purchase Order Schemas
# ============================================================================


class VendorBase(BaseModel):
    """Base vendor schema."""

    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    lead_time_days: int = Field(default=7, ge=1)
    min_order_value: float = Field(default=0.0, ge=0)
    payment_terms: str = Field(default="NET30", max_length=50)


class VendorCreate(VendorBase):
    """Schema for creating a vendor."""

    pass


class VendorResponse(VendorBase):
    """Vendor response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    quality_rating: float
    delivery_rating: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PurchaseOrderLineCreate(BaseModel):
    """Schema for creating a PO line."""

    product_id: str
    quantity_ordered: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)


class PurchaseOrderCreate(BaseModel):
    """Schema for creating a purchase order."""

    vendor_id: str
    lines: list[PurchaseOrderLineCreate]
    notes: Optional[str] = None


class PurchaseOrderLineResponse(BaseModel):
    """PO line response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    line_number: int
    quantity_ordered: int
    quantity_received: int
    unit_price: float
    line_total: float


class PurchaseOrderResponse(BaseModel):
    """Purchase order response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    po_number: str
    vendor_id: str
    status: OrderStatus
    order_date: datetime
    expected_delivery_date: Optional[datetime]
    total_amount: float
    lines: list[PurchaseOrderLineResponse]
    notes: Optional[str]
    created_by: str
    created_at: datetime


class PurchaseOrderApproval(BaseModel):
    """Schema for approving a PO."""

    po_number: str
    approved_by: str


# ============================================================================
# Pick Order Schemas
# ============================================================================


class PickOrderLineRequest(BaseModel):
    """Schema for requesting a pick line."""

    sku: str
    quantity: int = Field(..., ge=1)


class PickOrderRequest(BaseModel):
    """Schema for requesting a pick order."""

    customer_order_ref: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    items: list[PickOrderLineRequest]


class PickRouteStep(BaseModel):
    """A single step in an optimized pick route."""

    sequence: int
    location_code: str
    sku: str
    product_name: str
    quantity: int
    zone: str
    aisle: str
    coordinates: dict[str, float]


class PickRouteResponse(BaseModel):
    """Optimized pick route response."""

    order_number: str
    total_items: int
    total_units: int
    estimated_time_minutes: int
    total_distance_meters: float
    route: list[PickRouteStep]


class PickOrderResponse(BaseModel):
    """Pick order response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    customer_order_ref: Optional[str]
    status: OrderStatus
    priority: int
    assigned_picker: Optional[str]
    total_items: int
    total_units: int
    estimated_time_minutes: Optional[int]
    created_at: datetime


# ============================================================================
# Alert & Sensor Schemas
# ============================================================================


class SensorReadingCreate(BaseModel):
    """Schema for creating a sensor reading."""

    sensor_id: str = Field(..., max_length=50)
    location_id: Optional[str] = None
    temperature_celsius: Optional[float] = None
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    shock_detected: bool = False
    battery_level: Optional[float] = Field(None, ge=0, le=100)


class SensorReadingResponse(BaseModel):
    """Sensor reading response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    sensor_id: str
    location_id: Optional[str]
    temperature_celsius: Optional[float]
    humidity_percent: Optional[float]
    shock_detected: bool
    battery_level: Optional[float]
    reading_timestamp: datetime


class AlertResponse(BaseModel):
    """Alert response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    is_acknowledged: bool
    created_at: datetime


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging an alert."""

    alert_id: str
    acknowledged_by: str


# ============================================================================
# Agent State Schemas
# ============================================================================


class AgentTask(BaseModel):
    """A task for an agent to execute."""

    task_id: str
    task_type: str
    priority: int = Field(default=5, ge=1, le=10)
    payload: dict
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResult(BaseModel):
    """Result from an agent execution."""

    task_id: str
    agent_name: str
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    execution_time_ms: int
    completed_at: datetime = Field(default_factory=datetime.utcnow)


class WarehouseState(BaseModel):
    """Global warehouse state."""

    warehouse_id: str
    total_products: int
    total_locations: int
    total_inventory_value: float
    pending_purchase_orders: int
    pending_pick_orders: int
    active_alerts: int
    critical_alerts: int
    last_updated: datetime
