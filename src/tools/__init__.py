"""
Agent Tools Package
"""

from src.tools.inventory_tools import (
    get_stock_level,
    update_stock_quantity,
    reconcile_inventory,
    get_inventory_by_location,
    get_expiring_items,
    allocate_stock,
    deallocate_stock,
)

from src.tools.replenishment_tools import (
    calculate_reorder_point,
    calculate_economic_order_quantity,
    get_vendor_info,
    create_purchase_order,
    get_pending_purchase_orders,
    calculate_days_of_cover,
)

from src.tools.operations_tools import (
    generate_pick_route,
    get_optimal_putaway_location,
    get_warehouse_layout,
    calculate_route_distance,
)

from src.tools.sensor_tools import (
    get_sensor_readings,
    check_environmental_alerts,
    get_location_conditions,
)

__all__ = [
    # Inventory tools
    "get_stock_level",
    "update_stock_quantity",
    "reconcile_inventory",
    "get_inventory_by_location",
    "get_expiring_items",
    "allocate_stock",
    "deallocate_stock",
    # Replenishment tools
    "calculate_reorder_point",
    "calculate_economic_order_quantity",
    "get_vendor_info",
    "create_purchase_order",
    "get_pending_purchase_orders",
    "calculate_days_of_cover",
    # Operations tools
    "generate_pick_route",
    "get_optimal_putaway_location",
    "get_warehouse_layout",
    "calculate_route_distance",
    # Sensor tools
    "get_sensor_readings",
    "check_environmental_alerts",
    "get_location_conditions",
]
