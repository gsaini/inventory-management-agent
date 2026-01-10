"""
Database Seeder

Seeds the database with sample data for development and testing.
"""

import asyncio
import random
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db import AsyncSessionLocal, init_db
from src.models.inventory import (
    Product,
    Location,
    InventoryItem,
    Vendor,
    SensorReading,
    LocationType,
)


# Sample product data
SAMPLE_PRODUCTS = [
    {
        "sku": "ELEC-LAPTOP-001",
        "name": "Business Laptop 15-inch",
        "category": "Electronics",
        "subcategory": "Computers",
        "unit_of_measure": "EACH",
        "weight_kg": 2.1,
        "is_fragile": True,
        "shelf_life_days": None,
        "reorder_point": 20,
        "reorder_quantity": 50,
        "velocity_class": "A",
        "unit_cost": 899.99,
    },
    {
        "sku": "ELEC-PHONE-001",
        "name": "Smartphone Pro Max",
        "category": "Electronics",
        "subcategory": "Mobile",
        "unit_of_measure": "EACH",
        "weight_kg": 0.2,
        "is_fragile": True,
        "shelf_life_days": None,
        "reorder_point": 50,
        "reorder_quantity": 100,
        "velocity_class": "A",
        "unit_cost": 1099.99,
    },
    {
        "sku": "FOOD-DAIRY-001",
        "name": "Organic Milk 1L",
        "category": "Food",
        "subcategory": "Dairy",
        "unit_of_measure": "EACH",
        "weight_kg": 1.0,
        "requires_cold_storage": True,
        "shelf_life_days": 14,
        "reorder_point": 100,
        "reorder_quantity": 200,
        "velocity_class": "A",
        "unit_cost": 3.99,
    },
    {
        "sku": "FOOD-FROZEN-001",
        "name": "Frozen Pizza",
        "category": "Food",
        "subcategory": "Frozen",
        "unit_of_measure": "EACH",
        "weight_kg": 0.5,
        "requires_cold_storage": True,
        "shelf_life_days": 180,
        "reorder_point": 80,
        "reorder_quantity": 150,
        "velocity_class": "B",
        "unit_cost": 6.99,
    },
    {
        "sku": "OFFICE-PAPER-001",
        "name": "A4 Copy Paper 500 Sheets",
        "category": "Office Supplies",
        "subcategory": "Paper",
        "unit_of_measure": "PACK",
        "weight_kg": 2.5,
        "shelf_life_days": None,
        "reorder_point": 200,
        "reorder_quantity": 500,
        "velocity_class": "B",
        "unit_cost": 8.99,
    },
    {
        "sku": "OFFICE-PEN-001",
        "name": "Ballpoint Pen Blue 12-Pack",
        "category": "Office Supplies",
        "subcategory": "Writing",
        "unit_of_measure": "PACK",
        "weight_kg": 0.1,
        "shelf_life_days": None,
        "reorder_point": 100,
        "reorder_quantity": 200,
        "velocity_class": "C",
        "unit_cost": 5.99,
    },
    {
        "sku": "CLEAN-SPRAY-001",
        "name": "All-Purpose Cleaner 1L",
        "category": "Cleaning",
        "subcategory": "Sprays",
        "unit_of_measure": "EACH",
        "weight_kg": 1.1,
        "is_hazmat": False,
        "shelf_life_days": 730,
        "reorder_point": 50,
        "reorder_quantity": 100,
        "velocity_class": "C",
        "unit_cost": 4.99,
    },
    {
        "sku": "PHARMA-VITAMIN-001",
        "name": "Vitamin C 1000mg 100 Tablets",
        "category": "Pharmacy",
        "subcategory": "Vitamins",
        "unit_of_measure": "BOTTLE",
        "weight_kg": 0.15,
        "shelf_life_days": 365,
        "reorder_point": 30,
        "reorder_quantity": 60,
        "velocity_class": "B",
        "unit_cost": 12.99,
    },
]

# Sample vendors
SAMPLE_VENDORS = [
    {
        "code": "VEND-TECH-01",
        "name": "TechSource Electronics",
        "contact_name": "John Smith",
        "email": "orders@techsource.com",
        "phone": "+1-555-0100",
        "lead_time_days": 5,
        "min_order_value": 1000.0,
        "payment_terms": "NET30",
        "quality_rating": 4.8,
        "delivery_rating": 4.5,
    },
    {
        "code": "VEND-FOOD-01",
        "name": "Fresh Foods Distribution",
        "contact_name": "Maria Garcia",
        "email": "orders@freshfoods.com",
        "phone": "+1-555-0200",
        "lead_time_days": 2,
        "min_order_value": 500.0,
        "payment_terms": "NET15",
        "quality_rating": 4.9,
        "delivery_rating": 4.7,
    },
    {
        "code": "VEND-OFFICE-01",
        "name": "Office Essentials Inc",
        "contact_name": "David Lee",
        "email": "sales@officeessentials.com",
        "phone": "+1-555-0300",
        "lead_time_days": 7,
        "min_order_value": 200.0,
        "payment_terms": "NET30",
        "quality_rating": 4.5,
        "delivery_rating": 4.6,
    },
]


async def seed_locations(session: AsyncSession) -> list[Location]:
    """Create sample warehouse locations."""
    locations = []
    
    # Zone A - High velocity / Shipping area
    for aisle in range(1, 4):
        for rack in range(1, 5):
            for shelf in range(1, 4):
                for bin_num in range(1, 3):
                    location = Location(
                        id=str(uuid4()),
                        code=f"A-{aisle:02d}-{rack:02d}-{shelf:02d}-{bin_num:02d}",
                        zone="A",
                        aisle=f"{aisle:02d}",
                        rack=f"{rack:02d}",
                        shelf=f"{shelf:02d}",
                        bin=f"{bin_num:02d}",
                        location_type=LocationType.STORAGE,
                        capacity_units=50,
                        x_coordinate=aisle * 10.0,
                        y_coordinate=rack * 5.0,
                        z_coordinate=shelf * 2.0,
                    )
                    locations.append(location)
                    session.add(location)
    
    # Zone B - Medium velocity
    for aisle in range(1, 3):
        for rack in range(1, 4):
            for shelf in range(1, 3):
                location = Location(
                    id=str(uuid4()),
                    code=f"B-{aisle:02d}-{rack:02d}-{shelf:02d}-01",
                    zone="B",
                    aisle=f"{aisle:02d}",
                    rack=f"{rack:02d}",
                    shelf=f"{shelf:02d}",
                    bin="01",
                    location_type=LocationType.STORAGE,
                    capacity_units=100,
                    x_coordinate=30 + aisle * 10.0,
                    y_coordinate=rack * 5.0,
                    z_coordinate=shelf * 2.0,
                )
                locations.append(location)
                session.add(location)
    
    # Zone C - Cold Storage
    for aisle in range(1, 3):
        for rack in range(1, 3):
            location = Location(
                id=str(uuid4()),
                code=f"C-{aisle:02d}-{rack:02d}-01-01",
                zone="C",
                aisle=f"{aisle:02d}",
                rack=f"{rack:02d}",
                shelf="01",
                bin="01",
                location_type=LocationType.COLD_STORAGE,
                capacity_units=75,
                has_temperature_control=True,
                x_coordinate=50 + aisle * 8.0,
                y_coordinate=rack * 5.0,
                z_coordinate=1.0,
            )
            locations.append(location)
            session.add(location)
    
    # Shipping dock
    shipping = Location(
        id=str(uuid4()),
        code="SHIP-01-01-01-01",
        zone="SHIP",
        aisle="01",
        rack="01",
        shelf="01",
        bin="01",
        location_type=LocationType.SHIPPING,
        capacity_units=500,
        x_coordinate=0.0,
        y_coordinate=0.0,
        z_coordinate=0.0,
    )
    locations.append(shipping)
    session.add(shipping)
    
    # Receiving dock
    receiving = Location(
        id=str(uuid4()),
        code="RECV-01-01-01-01",
        zone="RECV",
        aisle="01",
        rack="01",
        shelf="01",
        bin="01",
        location_type=LocationType.RECEIVING,
        capacity_units=500,
        x_coordinate=70.0,
        y_coordinate=0.0,
        z_coordinate=0.0,
    )
    locations.append(receiving)
    session.add(receiving)
    
    await session.commit()
    return locations


async def seed_products(session: AsyncSession) -> list[Product]:
    """Create sample products."""
    products = []
    
    for prod_data in SAMPLE_PRODUCTS:
        product = Product(
            id=str(uuid4()),
            barcode=f"BAR{random.randint(1000000000, 9999999999)}",
            **prod_data,
        )
        products.append(product)
        session.add(product)
    
    await session.commit()
    return products


async def seed_vendors(session: AsyncSession) -> list[Vendor]:
    """Create sample vendors."""
    vendors = []
    
    for vendor_data in SAMPLE_VENDORS:
        vendor = Vendor(
            id=str(uuid4()),
            **vendor_data,
        )
        vendors.append(vendor)
        session.add(vendor)
    
    await session.commit()
    return vendors


async def seed_inventory(
    session: AsyncSession,
    products: list[Product],
    locations: list[Location],
) -> list[InventoryItem]:
    """Create sample inventory items."""
    inventory_items = []
    
    # Filter to storage locations only
    storage_locations = [
        loc for loc in locations
        if loc.location_type in [LocationType.STORAGE, LocationType.COLD_STORAGE]
    ]
    
    for product in products:
        # Determine appropriate locations
        if product.requires_cold_storage:
            eligible_locations = [
                loc for loc in storage_locations
                if loc.location_type == LocationType.COLD_STORAGE
            ]
        else:
            eligible_locations = [
                loc for loc in storage_locations
                if loc.location_type == LocationType.STORAGE
            ]
        
        if not eligible_locations:
            continue
        
        # Create 1-3 inventory items per product
        num_locations = random.randint(1, min(3, len(eligible_locations)))
        selected_locations = random.sample(eligible_locations, num_locations)
        
        for loc in selected_locations:
            quantity = random.randint(10, 100)
            
            # Set expiry date for perishables
            expiry_date = None
            if product.shelf_life_days:
                days_remaining = random.randint(5, product.shelf_life_days)
                expiry_date = datetime.utcnow() + timedelta(days=days_remaining)
            
            inventory_item = InventoryItem(
                id=str(uuid4()),
                product_id=product.id,
                location_id=loc.id,
                quantity_on_hand=quantity,
                quantity_allocated=0,
                quantity_available=quantity,
                lot_number=f"LOT-{random.randint(100000, 999999)}",
                expiry_date=expiry_date,
                received_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            )
            inventory_items.append(inventory_item)
            session.add(inventory_item)
            
            # Update location usage
            loc.current_units += quantity
    
    await session.commit()
    return inventory_items


async def seed_sensor_readings(
    session: AsyncSession,
    locations: list[Location],
) -> list[SensorReading]:
    """Create sample sensor readings for cold storage locations."""
    readings = []
    
    cold_storage_locations = [
        loc for loc in locations
        if loc.has_temperature_control
    ]
    
    for loc in cold_storage_locations:
        sensor_id = f"SENSOR-{loc.code}"
        
        # Create readings for the last 24 hours
        for hours_ago in range(24):
            reading = SensorReading(
                id=str(uuid4()),
                sensor_id=sensor_id,
                location_id=loc.id,
                temperature_celsius=random.uniform(2.0, 6.0),
                humidity_percent=random.uniform(40.0, 55.0),
                shock_detected=random.random() < 0.02,  # 2% chance
                battery_level=random.uniform(70.0, 100.0),
                reading_timestamp=datetime.utcnow() - timedelta(hours=hours_ago),
            )
            readings.append(reading)
            session.add(reading)
    
    await session.commit()
    return readings


async def seed_database():
    """Main function to seed the database."""
    print("Initializing database...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        print("Seeding locations...")
        locations = await seed_locations(session)
        print(f"  Created {len(locations)} locations")
        
        print("Seeding products...")
        products = await seed_products(session)
        print(f"  Created {len(products)} products")
        
        print("Seeding vendors...")
        vendors = await seed_vendors(session)
        print(f"  Created {len(vendors)} vendors")
        
        print("Seeding inventory...")
        inventory = await seed_inventory(session, products, locations)
        print(f"  Created {len(inventory)} inventory items")
        
        print("Seeding sensor readings...")
        readings = await seed_sensor_readings(session, locations)
        print(f"  Created {len(readings)} sensor readings")
    
    print("\nDatabase seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_database())
