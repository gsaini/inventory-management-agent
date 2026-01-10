"""
Replenishment Tools

Tools for calculating reorder points, economic order quantities,
and managing purchase orders.
"""

import math
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
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
    AuditLog,
    OrderStatus,
)


@tool
def calculate_reorder_point(
    sku: str,
    average_daily_demand: float,
    lead_time_days: int,
    safety_stock_days: int = 3,
) -> dict:
    """
    Calculate the optimal reorder point for a product.
    
    Reorder Point = (Average Daily Demand × Lead Time) + Safety Stock
    
    Args:
        sku: The product SKU
        average_daily_demand: Average daily sales/consumption
        lead_time_days: Vendor lead time in days
        safety_stock_days: Additional buffer days for safety stock
        
    Returns:
        Dictionary with reorder point calculation
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        # Calculate safety stock
        safety_stock = int(average_daily_demand * safety_stock_days)
        
        # Calculate reorder point
        reorder_point = int((average_daily_demand * lead_time_days) + safety_stock)
        
        # Get current stock level
        total_stock = session.execute(
            select(func.sum(InventoryItem.quantity_on_hand))
            .where(InventoryItem.product_id == product.id)
        ).scalar() or 0
        
        current_rop = product.reorder_point
        
        return {
            "sku": sku,
            "product_name": product.name,
            "average_daily_demand": average_daily_demand,
            "lead_time_days": lead_time_days,
            "safety_stock_days": safety_stock_days,
            "calculated_safety_stock": safety_stock,
            "calculated_reorder_point": reorder_point,
            "current_reorder_point": current_rop,
            "current_stock": total_stock,
            "days_of_cover": round(total_stock / average_daily_demand, 1) if average_daily_demand > 0 else float('inf'),
            "needs_reorder": total_stock <= reorder_point,
        }
    finally:
        session.close()


@tool
def calculate_economic_order_quantity(
    sku: str,
    annual_demand: int,
    ordering_cost: float,
    holding_cost_percent: float = 0.25,
) -> dict:
    """
    Calculate the Economic Order Quantity (EOQ) using the Wilson formula.
    
    EOQ = √((2 × Annual Demand × Ordering Cost) / Holding Cost per Unit)
    
    Args:
        sku: The product SKU
        annual_demand: Expected annual demand in units
        ordering_cost: Cost per order (shipping, admin, etc.)
        holding_cost_percent: Annual holding cost as percentage of unit cost
        
    Returns:
        Dictionary with EOQ calculation
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        if product.unit_cost <= 0:
            return {"error": "Product unit cost must be greater than 0"}
        
        # Calculate holding cost per unit
        holding_cost_per_unit = product.unit_cost * holding_cost_percent
        
        # Calculate EOQ
        eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
        eoq = int(round(eoq))
        
        # Calculate orders per year
        orders_per_year = annual_demand / eoq if eoq > 0 else 0
        
        # Calculate costs
        total_ordering_cost = orders_per_year * ordering_cost
        average_inventory = eoq / 2
        total_holding_cost = average_inventory * holding_cost_per_unit
        total_cost = total_ordering_cost + total_holding_cost
        
        return {
            "sku": sku,
            "product_name": product.name,
            "unit_cost": product.unit_cost,
            "annual_demand": annual_demand,
            "ordering_cost": ordering_cost,
            "holding_cost_percent": holding_cost_percent,
            "holding_cost_per_unit": round(holding_cost_per_unit, 2),
            "economic_order_quantity": eoq,
            "current_reorder_quantity": product.reorder_quantity,
            "orders_per_year": round(orders_per_year, 1),
            "average_inventory": round(average_inventory, 0),
            "annual_ordering_cost": round(total_ordering_cost, 2),
            "annual_holding_cost": round(total_holding_cost, 2),
            "total_annual_cost": round(total_cost, 2),
        }
    finally:
        session.close()


@tool
def get_vendor_info(vendor_code: Optional[str] = None, sku: Optional[str] = None) -> dict:
    """
    Get vendor information and performance metrics.
    
    Args:
        vendor_code: Optional vendor code to look up specific vendor
        sku: Optional SKU to find vendors for a product
        
    Returns:
        Dictionary with vendor information
    """
    session = get_sync_session()
    try:
        if vendor_code:
            vendor = session.execute(
                select(Vendor).where(Vendor.code == vendor_code, Vendor.is_active == True)
            ).scalar_one_or_none()
            
            if not vendor:
                return {"error": f"Vendor '{vendor_code}' not found or inactive"}
            
            # Get recent PO performance
            recent_pos = session.execute(
                select(PurchaseOrder)
                .where(
                    PurchaseOrder.vendor_id == vendor.id,
                    PurchaseOrder.status == OrderStatus.COMPLETED,
                )
                .order_by(PurchaseOrder.actual_delivery_date.desc())
                .limit(10)
            ).scalars().all()
            
            on_time_deliveries = sum(
                1 for po in recent_pos
                if po.actual_delivery_date and po.expected_delivery_date
                and po.actual_delivery_date <= po.expected_delivery_date
            )
            on_time_rate = (on_time_deliveries / len(recent_pos) * 100) if recent_pos else 100
            
            return {
                "vendor_code": vendor.code,
                "vendor_name": vendor.name,
                "contact_name": vendor.contact_name,
                "email": vendor.email,
                "lead_time_days": vendor.lead_time_days,
                "min_order_value": vendor.min_order_value,
                "payment_terms": vendor.payment_terms,
                "quality_rating": vendor.quality_rating,
                "delivery_rating": vendor.delivery_rating,
                "on_time_delivery_rate": round(on_time_rate, 1),
                "recent_orders": len(recent_pos),
            }
        else:
            # Return all active vendors
            vendors = session.execute(
                select(Vendor).where(Vendor.is_active == True).order_by(Vendor.name)
            ).scalars().all()
            
            return {
                "total_vendors": len(vendors),
                "vendors": [
                    {
                        "vendor_code": v.code,
                        "vendor_name": v.name,
                        "lead_time_days": v.lead_time_days,
                        "quality_rating": v.quality_rating,
                        "delivery_rating": v.delivery_rating,
                    }
                    for v in vendors
                ],
            }
    finally:
        session.close()


@tool
def create_purchase_order(
    vendor_code: str,
    items: list[dict],
    notes: Optional[str] = None,
) -> dict:
    """
    Create a new purchase order.
    
    Args:
        vendor_code: The vendor to order from
        items: List of dicts with 'sku', 'quantity', and optional 'unit_price'
        notes: Optional notes for the PO
        
    Returns:
        Dictionary with created PO details
    """
    session = get_sync_session()
    try:
        vendor = session.execute(
            select(Vendor).where(Vendor.code == vendor_code, Vendor.is_active == True)
        ).scalar_one_or_none()
        
        if not vendor:
            return {"error": f"Vendor '{vendor_code}' not found or inactive"}
        
        # Generate PO number
        po_count = session.execute(
            select(func.count(PurchaseOrder.id))
        ).scalar() or 0
        po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{po_count + 1:04d}"
        
        # Create PO header
        purchase_order = PurchaseOrder(
            id=str(uuid4()),
            po_number=po_number,
            vendor_id=vendor.id,
            status=OrderStatus.DRAFT,
            order_date=datetime.utcnow(),
            expected_delivery_date=datetime.utcnow() + timedelta(days=vendor.lead_time_days),
            notes=notes,
            created_by="replenishment_agent",
        )
        session.add(purchase_order)
        
        # Create PO lines
        total_amount = 0
        po_lines = []
        
        for idx, item in enumerate(items, 1):
            product = session.execute(
                select(Product).where(Product.sku == item["sku"])
            ).scalar_one_or_none()
            
            if not product:
                session.rollback()
                return {"error": f"Product '{item['sku']}' not found"}
            
            unit_price = item.get("unit_price", product.unit_cost)
            line_total = unit_price * item["quantity"]
            total_amount += line_total
            
            po_line = PurchaseOrderLine(
                id=str(uuid4()),
                purchase_order_id=purchase_order.id,
                product_id=product.id,
                line_number=idx,
                quantity_ordered=item["quantity"],
                unit_price=unit_price,
                line_total=line_total,
            )
            session.add(po_line)
            po_lines.append({
                "line_number": idx,
                "sku": product.sku,
                "product_name": product.name,
                "quantity": item["quantity"],
                "unit_price": unit_price,
                "line_total": line_total,
            })
        
        # Check minimum order value
        if total_amount < vendor.min_order_value:
            session.rollback()
            return {
                "error": f"Order total ${total_amount:.2f} is below vendor minimum ${vendor.min_order_value:.2f}"
            }
        
        purchase_order.total_amount = total_amount
        
        # Audit log
        audit_log = AuditLog(
            id=str(uuid4()),
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            action="created",
            reference_number=po_number,
            reason="Auto-generated by replenishment agent",
            agent_name="replenishment_agent",
        )
        session.add(audit_log)
        session.commit()
        
        return {
            "success": True,
            "po_number": po_number,
            "vendor_code": vendor_code,
            "vendor_name": vendor.name,
            "status": OrderStatus.DRAFT.value,
            "total_amount": total_amount,
            "expected_delivery_date": purchase_order.expected_delivery_date.isoformat(),
            "lines": po_lines,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@tool
def get_pending_purchase_orders() -> dict:
    """
    Get all pending purchase orders awaiting approval or delivery.
    
    Returns:
        Dictionary with pending PO information
    """
    session = get_sync_session()
    try:
        pending_statuses = [OrderStatus.DRAFT, OrderStatus.PENDING, OrderStatus.APPROVED]
        
        orders = session.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.vendor))
            .where(PurchaseOrder.status.in_(pending_statuses))
            .order_by(PurchaseOrder.expected_delivery_date)
        ).scalars().all()
        
        po_list = []
        for order in orders:
            days_until_delivery = None
            if order.expected_delivery_date:
                days_until_delivery = (order.expected_delivery_date - datetime.utcnow()).days
            
            po_list.append({
                "po_number": order.po_number,
                "vendor_name": order.vendor.name,
                "status": order.status.value,
                "order_date": order.order_date.isoformat(),
                "expected_delivery_date": order.expected_delivery_date.isoformat() if order.expected_delivery_date else None,
                "days_until_delivery": days_until_delivery,
                "total_amount": order.total_amount,
            })
        
        return {
            "total_pending": len(po_list),
            "total_value": sum(po["total_amount"] for po in po_list),
            "orders": po_list,
        }
    finally:
        session.close()


@tool
def calculate_days_of_cover(sku: str, average_daily_demand: float) -> dict:
    """
    Calculate how many days of inventory coverage exist for a product.
    
    Args:
        sku: The product SKU
        average_daily_demand: Average daily sales/consumption
        
    Returns:
        Dictionary with days of cover analysis
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product with SKU '{sku}' not found"}
        
        # Get current stock
        total_stock = session.execute(
            select(func.sum(InventoryItem.quantity_on_hand))
            .where(InventoryItem.product_id == product.id)
        ).scalar() or 0
        
        total_allocated = session.execute(
            select(func.sum(InventoryItem.quantity_allocated))
            .where(InventoryItem.product_id == product.id)
        ).scalar() or 0
        
        available_stock = total_stock - total_allocated
        
        # Get incoming PO quantities
        incoming_qty = session.execute(
            select(func.sum(PurchaseOrderLine.quantity_ordered - PurchaseOrderLine.quantity_received))
            .join(PurchaseOrder)
            .where(
                PurchaseOrderLine.product_id == product.id,
                PurchaseOrder.status.in_([OrderStatus.APPROVED, OrderStatus.IN_PROGRESS]),
            )
        ).scalar() or 0
        
        # Calculate days of cover
        if average_daily_demand <= 0:
            days_of_cover = float('inf')
            days_with_incoming = float('inf')
        else:
            days_of_cover = available_stock / average_daily_demand
            days_with_incoming = (available_stock + incoming_qty) / average_daily_demand
        
        # Determine status
        if days_of_cover <= 0:
            status = "out_of_stock"
        elif days_of_cover < product.reorder_point / average_daily_demand if average_daily_demand > 0 else 0:
            status = "critical"
        elif days_of_cover < 14:
            status = "low"
        else:
            status = "healthy"
        
        return {
            "sku": sku,
            "product_name": product.name,
            "average_daily_demand": average_daily_demand,
            "current_stock": total_stock,
            "allocated_stock": total_allocated,
            "available_stock": available_stock,
            "incoming_po_quantity": incoming_qty,
            "days_of_cover": round(days_of_cover, 1) if days_of_cover != float('inf') else "unlimited",
            "days_of_cover_with_incoming": round(days_with_incoming, 1) if days_with_incoming != float('inf') else "unlimited",
            "status": status,
            "reorder_point": product.reorder_point,
            "reorder_quantity": product.reorder_quantity,
        }
    finally:
        session.close()
