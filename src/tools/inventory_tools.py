"""
Inventory Management Tools

Tools for tracking, reconciling, and managing inventory levels.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.db import get_sync_session
from src.models.inventory import (
    Product,
    InventoryItem,
    Location,
    AuditLog,
    MovementType,
)


@tool
def get_stock_level(sku: str) -> dict:
    """
    Get the current stock level for a product by SKU.
    
    Returns aggregated stock across all locations including:
    - Total quantity on hand
    - Total allocated quantity
    - Total available quantity
    - Stock status (ok, low, critical, out_of_stock)
    - List of locations with stock
    
    Args:
        sku: The product SKU to look up
        
    Returns:
        Dictionary with stock information
    """
    session = get_sync_session()
    try:
        # Get product
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        # Get all inventory items for this product
        inventory_items = session.execute(
            select(InventoryItem)
            .options(selectinload(InventoryItem.location))
            .where(InventoryItem.product_id == product.id)
        ).scalars().all()
        
        total_on_hand = sum(item.quantity_on_hand for item in inventory_items)
        total_allocated = sum(item.quantity_allocated for item in inventory_items)
        total_available = total_on_hand - total_allocated
        
        # Determine stock status
        if total_available <= 0:
            status = "out_of_stock"
        elif total_available < product.min_stock_level:
            status = "critical"
        elif total_available < product.reorder_point:
            status = "low"
        else:
            status = "ok"
        
        locations = [
            {
                "location_code": item.location.code,
                "zone": item.location.zone,
                "quantity_on_hand": item.quantity_on_hand,
                "quantity_available": item.quantity_on_hand - item.quantity_allocated,
                "lot_number": item.lot_number,
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
            }
            for item in inventory_items
            if item.quantity_on_hand > 0
        ]
        
        return {
            "sku": sku,
            "product_name": product.name,
            "total_on_hand": total_on_hand,
            "total_allocated": total_allocated,
            "total_available": total_available,
            "reorder_point": product.reorder_point,
            "reorder_quantity": product.reorder_quantity,
            "min_stock_level": product.min_stock_level,
            "velocity_class": product.velocity_class,
            "status": status,
            "locations": locations,
        }
    finally:
        session.close()


@tool
def update_stock_quantity(
    sku: str,
    location_code: str,
    quantity_change: int,
    movement_type: str,
    reason: Optional[str] = None,
    reference_number: Optional[str] = None,
) -> dict:
    """
    Update stock quantity at a specific location.
    
    Args:
        sku: The product SKU
        location_code: The location code
        quantity_change: The quantity to add (positive) or remove (negative)
        movement_type: Type of movement (receiving, pick, transfer, adjustment, return, write_off)
        reason: Optional reason for the change
        reference_number: Optional reference (PO number, pick order, etc.)
        
    Returns:
        Dictionary with update result
    """
    session = get_sync_session()
    try:
        # Get product and location
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        # Find or create inventory item
        inventory_item = session.execute(
            select(InventoryItem).where(
                InventoryItem.product_id == product.id,
                InventoryItem.location_id == location.id,
            )
        ).scalar_one_or_none()
        
        if not inventory_item:
            if quantity_change < 0:
                return {"error": "Cannot remove stock from location with no inventory"}
            
            inventory_item = InventoryItem(
                id=str(uuid4()),
                product_id=product.id,
                location_id=location.id,
                quantity_on_hand=0,
                quantity_allocated=0,
                quantity_available=0,
            )
            session.add(inventory_item)
        
        previous_quantity = inventory_item.quantity_on_hand
        new_quantity = previous_quantity + quantity_change
        
        if new_quantity < 0:
            return {
                "error": f"Insufficient stock. Current: {previous_quantity}, requested: {abs(quantity_change)}"
            }
        
        inventory_item.quantity_on_hand = new_quantity
        inventory_item.quantity_available = new_quantity - inventory_item.quantity_allocated
        inventory_item.last_movement_at = datetime.utcnow()
        
        # Update location capacity
        location.current_units += quantity_change
        
        # Create audit log
        audit_log = AuditLog(
            id=str(uuid4()),
            entity_type="inventory_item",
            entity_id=inventory_item.id,
            action="stock_update",
            movement_type=MovementType(movement_type),
            quantity_before=previous_quantity,
            quantity_after=new_quantity,
            quantity_change=quantity_change,
            reason=reason,
            reference_number=reference_number,
            agent_name="tracking_agent",
        )
        session.add(audit_log)
        session.commit()
        
        return {
            "success": True,
            "sku": sku,
            "location_code": location_code,
            "previous_quantity": previous_quantity,
            "new_quantity": new_quantity,
            "quantity_change": quantity_change,
            "movement_type": movement_type,
            "audit_log_id": audit_log.id,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@tool
def reconcile_inventory(
    sku: str,
    location_code: str,
    counted_quantity: int,
    performed_by: str = "system",
    reason: Optional[str] = None,
) -> dict:
    """
    Reconcile inventory after a cycle count or audit.
    
    Compares the counted quantity with system quantity and creates
    an adjustment if there's a discrepancy.
    
    Args:
        sku: The product SKU
        location_code: The location code
        counted_quantity: The physically counted quantity
        performed_by: Who performed the count
        reason: Optional reason for discrepancy
        
    Returns:
        Dictionary with reconciliation result
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        inventory_item = session.execute(
            select(InventoryItem).where(
                InventoryItem.product_id == product.id,
                InventoryItem.location_id == location.id,
            )
        ).scalar_one_or_none()
        
        system_quantity = inventory_item.quantity_on_hand if inventory_item else 0
        variance = counted_quantity - system_quantity
        
        if variance == 0:
            # No discrepancy, just update count timestamp
            if inventory_item:
                inventory_item.last_counted_at = datetime.utcnow()
                session.commit()
            
            return {
                "success": True,
                "sku": sku,
                "location_code": location_code,
                "system_quantity": system_quantity,
                "counted_quantity": counted_quantity,
                "variance": 0,
                "adjustment_made": False,
            }
        
        # Create or update inventory item
        if not inventory_item:
            inventory_item = InventoryItem(
                id=str(uuid4()),
                product_id=product.id,
                location_id=location.id,
                quantity_on_hand=counted_quantity,
                quantity_allocated=0,
                quantity_available=counted_quantity,
            )
            session.add(inventory_item)
        else:
            inventory_item.quantity_on_hand = counted_quantity
            inventory_item.quantity_available = counted_quantity - inventory_item.quantity_allocated
        
        inventory_item.last_counted_at = datetime.utcnow()
        inventory_item.last_movement_at = datetime.utcnow()
        
        # Create audit log for the adjustment
        audit_log = AuditLog(
            id=str(uuid4()),
            entity_type="inventory_item",
            entity_id=inventory_item.id,
            action="reconciliation",
            movement_type=MovementType.ADJUSTMENT,
            quantity_before=system_quantity,
            quantity_after=counted_quantity,
            quantity_change=variance,
            reason=reason or f"Cycle count reconciliation by {performed_by}",
            performed_by=performed_by,
            agent_name="audit_agent",
        )
        session.add(audit_log)
        session.commit()
        
        return {
            "success": True,
            "sku": sku,
            "location_code": location_code,
            "system_quantity": system_quantity,
            "counted_quantity": counted_quantity,
            "variance": variance,
            "adjustment_made": True,
            "audit_log_id": audit_log.id,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@tool
def get_inventory_by_location(location_code: str) -> dict:
    """
    Get all inventory items at a specific location.
    
    Args:
        location_code: The location code to query
        
    Returns:
        Dictionary with location inventory details
    """
    session = get_sync_session()
    try:
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        inventory_items = session.execute(
            select(InventoryItem)
            .options(selectinload(InventoryItem.product))
            .where(InventoryItem.location_id == location.id)
        ).scalars().all()
        
        items = [
            {
                "sku": item.product.sku,
                "product_name": item.product.name,
                "quantity_on_hand": item.quantity_on_hand,
                "quantity_allocated": item.quantity_allocated,
                "quantity_available": item.quantity_on_hand - item.quantity_allocated,
                "lot_number": item.lot_number,
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                "last_movement": item.last_movement_at.isoformat() if item.last_movement_at else None,
            }
            for item in inventory_items
            if item.quantity_on_hand > 0
        ]
        
        return {
            "location_code": location_code,
            "zone": location.zone,
            "location_type": location.location_type.value,
            "capacity_units": location.capacity_units,
            "current_units": location.current_units,
            "utilization_percent": round(
                (location.current_units / location.capacity_units) * 100, 2
            ) if location.capacity_units > 0 else 0,
            "items": items,
            "total_items": len(items),
        }
    finally:
        session.close()


@tool
def get_expiring_items(days_threshold: int = 30) -> dict:
    """
    Get inventory items expiring within the specified number of days.
    
    Args:
        days_threshold: Number of days to look ahead for expiration
        
    Returns:
        Dictionary with expiring items
    """
    session = get_sync_session()
    try:
        threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
        
        items = session.execute(
            select(InventoryItem)
            .options(
                selectinload(InventoryItem.product),
                selectinload(InventoryItem.location),
            )
            .where(
                InventoryItem.expiry_date.isnot(None),
                InventoryItem.expiry_date <= threshold_date,
                InventoryItem.quantity_on_hand > 0,
            )
            .order_by(InventoryItem.expiry_date)
        ).scalars().all()
        
        expiring_items = []
        for item in items:
            days_until_expiry = (item.expiry_date - datetime.utcnow()).days
            
            expiring_items.append({
                "sku": item.product.sku,
                "product_name": item.product.name,
                "location_code": item.location.code,
                "quantity": item.quantity_on_hand,
                "lot_number": item.lot_number,
                "expiry_date": item.expiry_date.isoformat(),
                "days_until_expiry": days_until_expiry,
                "status": "expired" if days_until_expiry < 0 else (
                    "critical" if days_until_expiry <= 7 else "warning"
                ),
            })
        
        return {
            "threshold_days": days_threshold,
            "total_items": len(expiring_items),
            "expired": len([i for i in expiring_items if i["status"] == "expired"]),
            "critical": len([i for i in expiring_items if i["status"] == "critical"]),
            "warning": len([i for i in expiring_items if i["status"] == "warning"]),
            "items": expiring_items,
        }
    finally:
        session.close()


@tool
def allocate_stock(sku: str, location_code: str, quantity: int, order_reference: str) -> dict:
    """
    Allocate stock for an order (reserve it for picking).
    
    Args:
        sku: The product SKU
        location_code: The location to allocate from
        quantity: Quantity to allocate
        order_reference: Reference to the order requiring this stock
        
    Returns:
        Dictionary with allocation result
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        inventory_item = session.execute(
            select(InventoryItem).where(
                InventoryItem.product_id == product.id,
                InventoryItem.location_id == location.id,
            )
        ).scalar_one_or_none()
        
        if not inventory_item:
            return {"error": f"No inventory found for {sku} at {location_code}"}
        
        available = inventory_item.quantity_on_hand - inventory_item.quantity_allocated
        if available < quantity:
            return {
                "error": f"Insufficient available stock. Available: {available}, requested: {quantity}"
            }
        
        inventory_item.quantity_allocated += quantity
        inventory_item.quantity_available = (
            inventory_item.quantity_on_hand - inventory_item.quantity_allocated
        )
        
        # Audit log
        audit_log = AuditLog(
            id=str(uuid4()),
            entity_type="inventory_item",
            entity_id=inventory_item.id,
            action="allocation",
            quantity_change=quantity,
            reference_number=order_reference,
            reason=f"Stock allocated for order {order_reference}",
            agent_name="operations_agent",
        )
        session.add(audit_log)
        session.commit()
        
        return {
            "success": True,
            "sku": sku,
            "location_code": location_code,
            "quantity_allocated": quantity,
            "remaining_available": inventory_item.quantity_available,
            "order_reference": order_reference,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@tool
def deallocate_stock(sku: str, location_code: str, quantity: int, reason: str) -> dict:
    """
    Deallocate previously allocated stock (e.g., order cancelled).
    
    Args:
        sku: The product SKU
        location_code: The location to deallocate from
        quantity: Quantity to deallocate
        reason: Reason for deallocation
        
    Returns:
        Dictionary with deallocation result
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        inventory_item = session.execute(
            select(InventoryItem).where(
                InventoryItem.product_id == product.id,
                InventoryItem.location_id == location.id,
            )
        ).scalar_one_or_none()
        
        if not inventory_item:
            return {"error": f"No inventory found for {sku} at {location_code}"}
        
        if inventory_item.quantity_allocated < quantity:
            return {
                "error": f"Cannot deallocate {quantity}. Only {inventory_item.quantity_allocated} allocated."
            }
        
        inventory_item.quantity_allocated -= quantity
        inventory_item.quantity_available = (
            inventory_item.quantity_on_hand - inventory_item.quantity_allocated
        )
        
        audit_log = AuditLog(
            id=str(uuid4()),
            entity_type="inventory_item",
            entity_id=inventory_item.id,
            action="deallocation",
            quantity_change=-quantity,
            reason=reason,
            agent_name="operations_agent",
        )
        session.add(audit_log)
        session.commit()
        
        return {
            "success": True,
            "sku": sku,
            "location_code": location_code,
            "quantity_deallocated": quantity,
            "new_available": inventory_item.quantity_available,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()
