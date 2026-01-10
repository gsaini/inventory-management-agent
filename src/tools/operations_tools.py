"""
Operations Tools

Tools for pick route optimization, putaway suggestions, and warehouse layout management.
Uses graph theory for pathfinding optimization.
"""

import json
import math
from typing import Optional
from uuid import uuid4

import networkx as nx
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db import get_sync_session
from src.models.inventory import (
    Product,
    InventoryItem,
    Location,
    LocationType,
)


def _calculate_distance(loc1: Location, loc2: Location) -> float:
    """Calculate Euclidean distance between two locations."""
    return math.sqrt(
        (loc1.x_coordinate - loc2.x_coordinate) ** 2
        + (loc1.y_coordinate - loc2.y_coordinate) ** 2
        + (loc1.z_coordinate - loc2.z_coordinate) ** 2
    )


def _build_warehouse_graph(session) -> nx.Graph:
    """Build a weighted graph of the warehouse layout."""
    locations = session.execute(
        select(Location).where(Location.is_active == True)
    ).scalars().all()
    
    G = nx.Graph()
    
    # Add nodes
    for loc in locations:
        G.add_node(
            loc.code,
            zone=loc.zone,
            aisle=loc.aisle,
            x=loc.x_coordinate,
            y=loc.y_coordinate,
            z=loc.z_coordinate,
            location_type=loc.location_type.value,
        )
    
    # Add edges between locations in the same zone/aisle
    for i, loc1 in enumerate(locations):
        for loc2 in locations[i + 1:]:
            # Only connect locations that are reasonably close
            distance = _calculate_distance(loc1, loc2)
            
            # Connect locations in same aisle directly
            if loc1.zone == loc2.zone and loc1.aisle == loc2.aisle:
                G.add_edge(loc1.code, loc2.code, weight=distance)
            # Connect aisle endpoints
            elif loc1.zone == loc2.zone and distance < 20:
                G.add_edge(loc1.code, loc2.code, weight=distance * 1.5)  # Penalty for crossing aisles
    
    return G


@tool
def generate_pick_route(items: list[dict]) -> dict:
    """
    Generate an optimized pick route using the nearest neighbor heuristic
    for the Traveling Salesman Problem.
    
    Args:
        items: List of dicts with 'sku' and 'quantity' to pick
        
    Returns:
        Dictionary with optimized route and metrics
    """
    session = get_sync_session()
    try:
        # Build warehouse graph
        G = _build_warehouse_graph(session)
        
        if len(G.nodes) == 0:
            return {"error": "No locations found in warehouse"}
        
        # Find locations for each item
        pick_locations = []
        for item in items:
            product = session.execute(
                select(Product).where(Product.sku == item["sku"])
            ).scalar_one_or_none()
            
            if not product:
                return {"error": f"Product '{item['sku']}' not found"}
            
            # Find inventory with available stock (FIFO - oldest first)
            inventory = session.execute(
                select(InventoryItem)
                .options(selectinload(InventoryItem.location))
                .where(
                    InventoryItem.product_id == product.id,
                    InventoryItem.quantity_on_hand - InventoryItem.quantity_allocated >= item["quantity"],
                )
                .order_by(InventoryItem.received_date)
            ).scalars().first()
            
            if not inventory:
                return {"error": f"Insufficient stock for '{item['sku']}'"}
            
            pick_locations.append({
                "sku": item["sku"],
                "product_name": product.name,
                "quantity": item["quantity"],
                "location": inventory.location,
                "lot_number": inventory.lot_number,
            })
        
        if not pick_locations:
            return {"error": "No items to pick"}
        
        # Find a shipping dock as the starting/ending point
        shipping_locations = [
            n for n, d in G.nodes(data=True)
            if d.get("location_type") == LocationType.SHIPPING.value
        ]
        start_location = shipping_locations[0] if shipping_locations else list(G.nodes())[0]
        
        # Build route using nearest neighbor heuristic
        route = []
        remaining = [pl["location"].code for pl in pick_locations]
        current = start_location
        total_distance = 0
        
        # Create location to pick info mapping
        location_to_pick = {pl["location"].code: pl for pl in pick_locations}
        
        while remaining:
            # Find nearest unvisited location
            nearest = None
            nearest_distance = float('inf')
            
            for loc_code in remaining:
                try:
                    distance = nx.shortest_path_length(G, current, loc_code, weight='weight')
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest = loc_code
                except nx.NetworkXNoPath:
                    # If no path, use direct Euclidean distance
                    loc = location_to_pick[loc_code]["location"]
                    current_loc = session.execute(
                        select(Location).where(Location.code == current)
                    ).scalar_one_or_none()
                    if current_loc:
                        distance = _calculate_distance(current_loc, loc)
                        if distance < nearest_distance:
                            nearest_distance = distance
                            nearest = loc_code
            
            if nearest:
                remaining.remove(nearest)
                total_distance += nearest_distance
                
                pick_info = location_to_pick[nearest]
                route.append({
                    "sequence": len(route) + 1,
                    "location_code": nearest,
                    "sku": pick_info["sku"],
                    "product_name": pick_info["product_name"],
                    "quantity": pick_info["quantity"],
                    "zone": pick_info["location"].zone,
                    "aisle": pick_info["location"].aisle,
                    "coordinates": {
                        "x": pick_info["location"].x_coordinate,
                        "y": pick_info["location"].y_coordinate,
                        "z": pick_info["location"].z_coordinate,
                    },
                    "lot_number": pick_info.get("lot_number"),
                })
                current = nearest
        
        # Return to start
        try:
            return_distance = nx.shortest_path_length(G, current, start_location, weight='weight')
            total_distance += return_distance
        except nx.NetworkXNoPath:
            pass
        
        # Estimate time (assuming 2m/s walking speed + 30s per pick)
        walking_time_seconds = total_distance / 2
        pick_time_seconds = len(route) * 30
        total_time_minutes = int((walking_time_seconds + pick_time_seconds) / 60)
        
        return {
            "success": True,
            "start_location": start_location,
            "total_items": len(route),
            "total_units": sum(r["quantity"] for r in route),
            "total_distance_meters": round(total_distance, 2),
            "estimated_time_minutes": total_time_minutes,
            "route": route,
        }
    finally:
        session.close()


@tool
def get_optimal_putaway_location(
    sku: str,
    quantity: int,
    lot_number: Optional[str] = None,
) -> dict:
    """
    Suggest the optimal location for putting away received inventory.
    
    Considers:
    - Product velocity class (A items near shipping)
    - Temperature requirements
    - Available capacity
    - Consolidation with existing stock
    
    Args:
        sku: The product SKU
        quantity: Quantity to put away
        lot_number: Optional lot number
        
    Returns:
        Dictionary with suggested locations
    """
    session = get_sync_session()
    try:
        product = session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        
        if not product:
            return {"error": f"Product '{sku}' not found"}
        
        # Determine required location type
        if product.requires_cold_storage:
            required_type = LocationType.COLD_STORAGE
        elif product.is_hazmat:
            required_type = LocationType.HAZMAT
        else:
            required_type = LocationType.STORAGE
        
        # Get available locations
        query = select(Location).where(
            Location.is_active == True,
            Location.location_type == required_type,
            Location.capacity_units - Location.current_units >= quantity,
        )
        
        # Filter for temperature controlled if needed
        if product.requires_cold_storage:
            query = query.where(Location.has_temperature_control == True)
        
        locations = session.execute(query).scalars().all()
        
        if not locations:
            return {"error": "No suitable locations with sufficient capacity"}
        
        suggestions = []
        
        # First priority: Consolidate with existing stock of same product/lot
        existing_inventory = session.execute(
            select(InventoryItem)
            .options(selectinload(InventoryItem.location))
            .where(
                InventoryItem.product_id == product.id,
                InventoryItem.quantity_on_hand > 0,
            )
        ).scalars().all()
        
        for inv in existing_inventory:
            loc = inv.location
            available_capacity = loc.capacity_units - loc.current_units
            if available_capacity >= quantity:
                # Prefer same lot consolidation
                priority = 1 if inv.lot_number == lot_number else 2
                suggestions.append({
                    "location_code": loc.code,
                    "zone": loc.zone,
                    "aisle": loc.aisle,
                    "available_capacity": available_capacity,
                    "existing_quantity": inv.quantity_on_hand,
                    "consolidation": True,
                    "same_lot": inv.lot_number == lot_number,
                    "priority": priority,
                    "reason": "Consolidate with existing stock",
                })
        
        # Second priority: Based on velocity class
        # A items should be closer to shipping (lower y coordinate assumed)
        velocity_zones = {"A": ["A", "B"], "B": ["B", "C"], "C": ["C", "D", "E"]}
        preferred_zones = velocity_zones.get(product.velocity_class, ["C", "D"])
        
        for loc in locations:
            if loc.code not in [s["location_code"] for s in suggestions]:
                in_preferred_zone = loc.zone in preferred_zones
                suggestions.append({
                    "location_code": loc.code,
                    "zone": loc.zone,
                    "aisle": loc.aisle,
                    "available_capacity": loc.capacity_units - loc.current_units,
                    "existing_quantity": 0,
                    "consolidation": False,
                    "same_lot": False,
                    "priority": 3 if in_preferred_zone else 4,
                    "reason": "Velocity-based placement" if in_preferred_zone else "Available capacity",
                })
        
        # Sort by priority
        suggestions.sort(key=lambda x: (x["priority"], -x["available_capacity"]))
        
        return {
            "sku": sku,
            "product_name": product.name,
            "quantity": quantity,
            "velocity_class": product.velocity_class,
            "requires_cold_storage": product.requires_cold_storage,
            "required_location_type": required_type.value,
            "suggestions": suggestions[:5],  # Top 5 suggestions
        }
    finally:
        session.close()


@tool
def get_warehouse_layout() -> dict:
    """
    Get the warehouse layout structure and zone statistics.
    
    Returns:
        Dictionary with warehouse layout information
    """
    session = get_sync_session()
    try:
        locations = session.execute(
            select(Location).where(Location.is_active == True)
        ).scalars().all()
        
        if not locations:
            return {"error": "No locations defined in warehouse"}
        
        # Aggregate by zone
        zones = {}
        for loc in locations:
            if loc.zone not in zones:
                zones[loc.zone] = {
                    "zone": loc.zone,
                    "location_count": 0,
                    "total_capacity": 0,
                    "used_capacity": 0,
                    "aisles": set(),
                    "location_types": set(),
                }
            
            zones[loc.zone]["location_count"] += 1
            zones[loc.zone]["total_capacity"] += loc.capacity_units
            zones[loc.zone]["used_capacity"] += loc.current_units
            zones[loc.zone]["aisles"].add(loc.aisle)
            zones[loc.zone]["location_types"].add(loc.location_type.value)
        
        # Convert sets to lists and calculate utilization
        zone_stats = []
        for zone_data in zones.values():
            utilization = (
                zone_data["used_capacity"] / zone_data["total_capacity"] * 100
                if zone_data["total_capacity"] > 0 else 0
            )
            zone_stats.append({
                "zone": zone_data["zone"],
                "location_count": zone_data["location_count"],
                "total_capacity": zone_data["total_capacity"],
                "used_capacity": zone_data["used_capacity"],
                "utilization_percent": round(utilization, 2),
                "aisles": sorted(list(zone_data["aisles"])),
                "location_types": list(zone_data["location_types"]),
            })
        
        zone_stats.sort(key=lambda x: x["zone"])
        
        # Overall stats
        total_locations = len(locations)
        total_capacity = sum(loc.capacity_units for loc in locations)
        total_used = sum(loc.current_units for loc in locations)
        
        return {
            "total_locations": total_locations,
            "total_capacity_units": total_capacity,
            "total_used_units": total_used,
            "overall_utilization_percent": round(total_used / total_capacity * 100, 2) if total_capacity > 0 else 0,
            "zones": zone_stats,
        }
    finally:
        session.close()


@tool
def calculate_route_distance(location_codes: list[str]) -> dict:
    """
    Calculate the total distance for a given route through locations.
    
    Args:
        location_codes: Ordered list of location codes representing the route
        
    Returns:
        Dictionary with distance calculation
    """
    session = get_sync_session()
    try:
        if len(location_codes) < 2:
            return {"error": "Need at least 2 locations to calculate route"}
        
        # Build graph
        G = _build_warehouse_graph(session)
        
        # Calculate distance
        total_distance = 0
        segments = []
        
        for i in range(len(location_codes) - 1):
            start = location_codes[i]
            end = location_codes[i + 1]
            
            if start not in G.nodes:
                return {"error": f"Location '{start}' not found"}
            if end not in G.nodes:
                return {"error": f"Location '{end}' not found"}
            
            try:
                distance = nx.shortest_path_length(G, start, end, weight='weight')
                path = nx.shortest_path(G, start, end, weight='weight')
            except nx.NetworkXNoPath:
                # Fallback to direct distance
                start_loc = session.execute(
                    select(Location).where(Location.code == start)
                ).scalar_one_or_none()
                end_loc = session.execute(
                    select(Location).where(Location.code == end)
                ).scalar_one_or_none()
                
                if start_loc and end_loc:
                    distance = _calculate_distance(start_loc, end_loc)
                    path = [start, end]
                else:
                    return {"error": f"Cannot calculate distance between {start} and {end}"}
            
            segments.append({
                "from": start,
                "to": end,
                "distance_meters": round(distance, 2),
                "path": path,
            })
            total_distance += distance
        
        return {
            "total_distance_meters": round(total_distance, 2),
            "location_count": len(location_codes),
            "segments": segments,
        }
    finally:
        session.close()
