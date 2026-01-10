"""
Inventory Management Agent - Database Models

SQLAlchemy models for warehouse inventory management including products,
locations, vendors, purchase orders, and sensor data.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# ============================================================================
# Enums
# ============================================================================


class LocationType(str, Enum):
    """Types of warehouse locations."""

    RECEIVING = "receiving"
    STORAGE = "storage"
    PICKING = "picking"
    PACKING = "packing"
    SHIPPING = "shipping"
    COLD_STORAGE = "cold_storage"
    HAZMAT = "hazmat"


class OrderStatus(str, Enum):
    """Status of purchase or pick orders."""

    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts."""

    LOW_STOCK = "low_stock"
    EXPIRY_WARNING = "expiry_warning"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SHRINKAGE = "shrinkage"
    DISCREPANCY = "discrepancy"
    SENSOR_OFFLINE = "sensor_offline"


class MovementType(str, Enum):
    """Types of inventory movement."""

    RECEIVING = "receiving"
    PUTAWAY = "putaway"
    PICK = "pick"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    WRITE_OFF = "write_off"


# ============================================================================
# Product & Inventory Models
# ============================================================================


class Product(Base):
    """Product master data."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="EACH")
    weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    length_cm: Mapped[Optional[float]] = mapped_column(Float)
    width_cm: Mapped[Optional[float]] = mapped_column(Float)
    height_cm: Mapped[Optional[float]] = mapped_column(Float)
    requires_cold_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fragile: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_days: Mapped[Optional[int]] = mapped_column(Integer)
    barcode: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    reorder_point: Mapped[int] = mapped_column(Integer, default=10)
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=50)
    min_stock_level: Mapped[int] = mapped_column(Integer, default=5)
    max_stock_level: Mapped[int] = mapped_column(Integer, default=500)
    velocity_class: Mapped[str] = mapped_column(String(1), default="C")  # A, B, or C
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="product")
    purchase_order_lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="product")
    pick_order_lines: Mapped[list["PickOrderLine"]] = relationship(back_populates="product")


class Location(Base):
    """Warehouse location (zone, aisle, rack, shelf, bin)."""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    zone: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    aisle: Mapped[str] = mapped_column(String(10), nullable=False)
    rack: Mapped[str] = mapped_column(String(10), nullable=False)
    shelf: Mapped[str] = mapped_column(String(10), nullable=False)
    bin: Mapped[str] = mapped_column(String(10), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        SQLEnum(LocationType), default=LocationType.STORAGE
    )
    capacity_units: Mapped[int] = mapped_column(Integer, default=100)
    current_units: Mapped[int] = mapped_column(Integer, default=0)
    x_coordinate: Mapped[float] = mapped_column(Float, default=0.0)
    y_coordinate: Mapped[float] = mapped_column(Float, default=0.0)
    z_coordinate: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    has_temperature_control: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="location")
    sensor_readings: Mapped[list["SensorReading"]] = relationship(back_populates="location")

    __table_args__ = (
        Index("ix_location_zone_aisle", "zone", "aisle"),
        UniqueConstraint("zone", "aisle", "rack", "shelf", "bin", name="uq_location_full"),
    )


class InventoryItem(Base):
    """Actual inventory at a specific location."""

    __tablename__ = "inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("locations.id"), nullable=False, index=True
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    quantity_allocated: Mapped[int] = mapped_column(Integer, default=0)
    quantity_available: Mapped[int] = mapped_column(Integer, default=0)
    lot_number: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    received_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_counted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_movement_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="inventory_items")
    location: Mapped["Location"] = relationship(back_populates="inventory_items")

    __table_args__ = (
        Index("ix_inventory_product_location", "product_id", "location_id"),
        Index("ix_inventory_expiry", "expiry_date"),
    )


# ============================================================================
# Vendor & Purchase Order Models
# ============================================================================


class Vendor(Base):
    """Vendor/Supplier master data."""

    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(Text)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    min_order_value: Mapped[float] = mapped_column(Float, default=0.0)
    payment_terms: Mapped[str] = mapped_column(String(50), default="NET30")
    quality_rating: Mapped[float] = mapped_column(Float, default=5.0)  # 1-5 scale
    delivery_rating: Mapped[float] = mapped_column(Float, default=5.0)  # 1-5 scale
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")


class PurchaseOrder(Base):
    """Purchase order header."""

    __tablename__ = "purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendors.id"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.DRAFT)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expected_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100), default="system")
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    vendor: Mapped["Vendor"] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    """Purchase order line item."""

    __tablename__ = "purchase_order_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purchase_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(back_populates="purchase_order_lines")


# ============================================================================
# Pick Order Models
# ============================================================================


class PickOrder(Base):
    """Pick order header for fulfillment."""

    __tablename__ = "pick_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_order_ref: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 = highest
    assigned_picker: Mapped[Optional[str]] = mapped_column(String(100))
    pick_route: Mapped[Optional[str]] = mapped_column(Text)  # JSON encoded route
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int] = mapped_column(Integer, default=0)
    estimated_time_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    actual_time_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    lines: Mapped[list["PickOrderLine"]] = relationship(back_populates="pick_order")


class PickOrderLine(Base):
    """Pick order line item."""

    __tablename__ = "pick_order_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    pick_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pick_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=False, index=True
    )
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("locations.id"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_picked: Mapped[int] = mapped_column(Integer, default=0)
    pick_sequence: Mapped[Optional[int]] = mapped_column(Integer)
    picked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    pick_order: Mapped["PickOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(back_populates="pick_order_lines")


# ============================================================================
# Monitoring & Audit Models
# ============================================================================


class SensorReading(Base):
    """IoT sensor readings for environmental monitoring."""

    __tablename__ = "sensor_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sensor_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("locations.id"), index=True
    )
    temperature_celsius: Mapped[Optional[float]] = mapped_column(Float)
    humidity_percent: Mapped[Optional[float]] = mapped_column(Float)
    shock_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    battery_level: Mapped[Optional[float]] = mapped_column(Float)
    reading_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    location: Mapped[Optional["Location"]] = relationship(back_populates="sensor_readings")

    __table_args__ = (Index("ix_sensor_reading_time", "sensor_id", "reading_timestamp"),)


class AuditLog(Base):
    """Audit trail for inventory changes."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    movement_type: Mapped[Optional[MovementType]] = mapped_column(SQLEnum(MovementType))
    quantity_before: Mapped[Optional[int]] = mapped_column(Integer)
    quantity_after: Mapped[Optional[int]] = mapped_column(Integer)
    quantity_change: Mapped[Optional[int]] = mapped_column(Integer)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    performed_by: Mapped[str] = mapped_column(String(100), default="system")
    agent_name: Mapped[Optional[str]] = mapped_column(String(100))
    metadata: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


class Alert(Base):
    """System alerts and notifications."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    alert_type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity), default=AlertSeverity.INFO
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_alert_status", "alert_type", "is_acknowledged"),)
