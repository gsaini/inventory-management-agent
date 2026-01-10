"""
Sensor Tools

Tools for IoT sensor integration and environmental monitoring.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from langchain_core.tools import tool
from sqlalchemy import select, func

from src.config import get_settings
from src.db import get_sync_session
from src.models.inventory import (
    Location,
    SensorReading,
    Alert,
    AlertType,
    AlertSeverity,
)


settings = get_settings()


@tool
def get_sensor_readings(
    sensor_id: Optional[str] = None,
    location_code: Optional[str] = None,
    hours: int = 24,
) -> dict:
    """
    Get recent sensor readings for a sensor or location.
    
    Args:
        sensor_id: Optional specific sensor ID
        location_code: Optional location code to filter by
        hours: Number of hours of history to retrieve
        
    Returns:
        Dictionary with sensor readings
    """
    session = get_sync_session()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(SensorReading).where(
            SensorReading.reading_timestamp >= since
        )
        
        if sensor_id:
            query = query.where(SensorReading.sensor_id == sensor_id)
        
        if location_code:
            location = session.execute(
                select(Location).where(Location.code == location_code)
            ).scalar_one_or_none()
            
            if not location:
                return {"error": f"Location '{location_code}' not found"}
            
            query = query.where(SensorReading.location_id == location.id)
        
        query = query.order_by(SensorReading.reading_timestamp.desc()).limit(100)
        
        readings = session.execute(query).scalars().all()
        
        reading_list = []
        for r in readings:
            reading_list.append({
                "sensor_id": r.sensor_id,
                "timestamp": r.reading_timestamp.isoformat(),
                "temperature_celsius": r.temperature_celsius,
                "humidity_percent": r.humidity_percent,
                "shock_detected": r.shock_detected,
                "battery_level": r.battery_level,
            })
        
        # Calculate statistics if we have readings
        stats = {}
        if readings:
            temps = [r.temperature_celsius for r in readings if r.temperature_celsius is not None]
            humidities = [r.humidity_percent for r in readings if r.humidity_percent is not None]
            
            if temps:
                stats["temperature"] = {
                    "min": round(min(temps), 2),
                    "max": round(max(temps), 2),
                    "avg": round(sum(temps) / len(temps), 2),
                }
            
            if humidities:
                stats["humidity"] = {
                    "min": round(min(humidities), 2),
                    "max": round(max(humidities), 2),
                    "avg": round(sum(humidities) / len(humidities), 2),
                }
            
            shock_count = sum(1 for r in readings if r.shock_detected)
            stats["shock_events"] = shock_count
        
        return {
            "sensor_id": sensor_id,
            "location_code": location_code,
            "hours_requested": hours,
            "reading_count": len(reading_list),
            "statistics": stats,
            "readings": reading_list[:20],  # Return latest 20 for brevity
        }
    finally:
        session.close()


@tool
def check_environmental_alerts() -> dict:
    """
    Check for environmental conditions that are outside acceptable thresholds.
    
    Checks temperature and humidity against configured thresholds and
    creates/returns alerts for any violations.
    
    Returns:
        Dictionary with current environmental alerts
    """
    session = get_sync_session()
    try:
        # Get the most recent reading for each sensor
        subquery = (
            select(
                SensorReading.sensor_id,
                func.max(SensorReading.reading_timestamp).label("max_timestamp"),
            )
            .group_by(SensorReading.sensor_id)
            .subquery()
        )
        
        latest_readings = session.execute(
            select(SensorReading)
            .join(
                subquery,
                (SensorReading.sensor_id == subquery.c.sensor_id)
                & (SensorReading.reading_timestamp == subquery.c.max_timestamp),
            )
        ).scalars().all()
        
        alerts_created = []
        issues = []
        
        for reading in latest_readings:
            # Check temperature
            if reading.temperature_celsius is not None:
                if reading.temperature_celsius < settings.temp_min_celsius:
                    severity = AlertSeverity.CRITICAL if reading.temperature_celsius < settings.temp_min_celsius - 2 else AlertSeverity.WARNING
                    issue = {
                        "sensor_id": reading.sensor_id,
                        "type": "temperature_low",
                        "value": reading.temperature_celsius,
                        "threshold": settings.temp_min_celsius,
                        "severity": severity.value,
                    }
                    issues.append(issue)
                    
                    # Create alert if not exists
                    alert = Alert(
                        id=str(uuid4()),
                        alert_type=AlertType.TEMPERATURE,
                        severity=severity,
                        title=f"Low Temperature Alert - Sensor {reading.sensor_id}",
                        message=f"Temperature {reading.temperature_celsius}°C is below threshold {settings.temp_min_celsius}°C",
                        entity_type="sensor",
                        entity_id=reading.sensor_id,
                    )
                    session.add(alert)
                    alerts_created.append(alert.id)
                
                elif reading.temperature_celsius > settings.temp_max_celsius:
                    severity = AlertSeverity.CRITICAL if reading.temperature_celsius > settings.temp_max_celsius + 2 else AlertSeverity.WARNING
                    issue = {
                        "sensor_id": reading.sensor_id,
                        "type": "temperature_high",
                        "value": reading.temperature_celsius,
                        "threshold": settings.temp_max_celsius,
                        "severity": severity.value,
                    }
                    issues.append(issue)
                    
                    alert = Alert(
                        id=str(uuid4()),
                        alert_type=AlertType.TEMPERATURE,
                        severity=severity,
                        title=f"High Temperature Alert - Sensor {reading.sensor_id}",
                        message=f"Temperature {reading.temperature_celsius}°C exceeds threshold {settings.temp_max_celsius}°C",
                        entity_type="sensor",
                        entity_id=reading.sensor_id,
                    )
                    session.add(alert)
                    alerts_created.append(alert.id)
            
            # Check humidity
            if reading.humidity_percent is not None:
                if reading.humidity_percent < settings.humidity_min_percent:
                    issue = {
                        "sensor_id": reading.sensor_id,
                        "type": "humidity_low",
                        "value": reading.humidity_percent,
                        "threshold": settings.humidity_min_percent,
                        "severity": "warning",
                    }
                    issues.append(issue)
                    
                    alert = Alert(
                        id=str(uuid4()),
                        alert_type=AlertType.HUMIDITY,
                        severity=AlertSeverity.WARNING,
                        title=f"Low Humidity Alert - Sensor {reading.sensor_id}",
                        message=f"Humidity {reading.humidity_percent}% is below threshold {settings.humidity_min_percent}%",
                        entity_type="sensor",
                        entity_id=reading.sensor_id,
                    )
                    session.add(alert)
                    alerts_created.append(alert.id)
                
                elif reading.humidity_percent > settings.humidity_max_percent:
                    issue = {
                        "sensor_id": reading.sensor_id,
                        "type": "humidity_high",
                        "value": reading.humidity_percent,
                        "threshold": settings.humidity_max_percent,
                        "severity": "warning",
                    }
                    issues.append(issue)
                    
                    alert = Alert(
                        id=str(uuid4()),
                        alert_type=AlertType.HUMIDITY,
                        severity=AlertSeverity.WARNING,
                        title=f"High Humidity Alert - Sensor {reading.sensor_id}",
                        message=f"Humidity {reading.humidity_percent}% exceeds threshold {settings.humidity_max_percent}%",
                        entity_type="sensor",
                        entity_id=reading.sensor_id,
                    )
                    session.add(alert)
                    alerts_created.append(alert.id)
            
            # Check for shock events
            if reading.shock_detected:
                issue = {
                    "sensor_id": reading.sensor_id,
                    "type": "shock_detected",
                    "severity": "warning",
                }
                issues.append(issue)
            
            # Check battery level
            if reading.battery_level is not None and reading.battery_level < 20:
                issue = {
                    "sensor_id": reading.sensor_id,
                    "type": "low_battery",
                    "value": reading.battery_level,
                    "severity": "info",
                }
                issues.append(issue)
        
        session.commit()
        
        return {
            "sensors_checked": len(latest_readings),
            "issues_found": len(issues),
            "alerts_created": len(alerts_created),
            "thresholds": {
                "temperature_min": settings.temp_min_celsius,
                "temperature_max": settings.temp_max_celsius,
                "humidity_min": settings.humidity_min_percent,
                "humidity_max": settings.humidity_max_percent,
            },
            "issues": issues,
        }
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@tool
def get_location_conditions(location_code: str) -> dict:
    """
    Get the current environmental conditions for a specific location.
    
    Args:
        location_code: The location code to check
        
    Returns:
        Dictionary with location environmental data
    """
    session = get_sync_session()
    try:
        location = session.execute(
            select(Location).where(Location.code == location_code)
        ).scalar_one_or_none()
        
        if not location:
            return {"error": f"Location '{location_code}' not found"}
        
        # Get the most recent sensor reading for this location
        latest_reading = session.execute(
            select(SensorReading)
            .where(SensorReading.location_id == location.id)
            .order_by(SensorReading.reading_timestamp.desc())
            .limit(1)
        ).scalar_one_or_none()
        
        # Get 24-hour history for statistics
        since = datetime.utcnow() - timedelta(hours=24)
        readings = session.execute(
            select(SensorReading)
            .where(
                SensorReading.location_id == location.id,
                SensorReading.reading_timestamp >= since,
            )
        ).scalars().all()
        
        result = {
            "location_code": location_code,
            "zone": location.zone,
            "location_type": location.location_type.value,
            "has_temperature_control": location.has_temperature_control,
            "current_reading": None,
            "last_24h_stats": None,
            "status": "no_data",
        }
        
        if latest_reading:
            age_minutes = (datetime.utcnow() - latest_reading.reading_timestamp).total_seconds() / 60
            
            current = {
                "sensor_id": latest_reading.sensor_id,
                "timestamp": latest_reading.reading_timestamp.isoformat(),
                "age_minutes": round(age_minutes, 1),
                "temperature_celsius": latest_reading.temperature_celsius,
                "humidity_percent": latest_reading.humidity_percent,
                "shock_detected": latest_reading.shock_detected,
                "battery_level": latest_reading.battery_level,
            }
            result["current_reading"] = current
            
            # Determine status
            if age_minutes > 60:
                result["status"] = "stale_data"
            elif latest_reading.temperature_celsius is not None:
                if (latest_reading.temperature_celsius < settings.temp_min_celsius or
                    latest_reading.temperature_celsius > settings.temp_max_celsius):
                    result["status"] = "alert"
                else:
                    result["status"] = "normal"
            else:
                result["status"] = "normal"
        
        if readings:
            temps = [r.temperature_celsius for r in readings if r.temperature_celsius is not None]
            humidities = [r.humidity_percent for r in readings if r.humidity_percent is not None]
            
            stats = {
                "reading_count": len(readings),
            }
            
            if temps:
                stats["temperature"] = {
                    "min": round(min(temps), 2),
                    "max": round(max(temps), 2),
                    "avg": round(sum(temps) / len(temps), 2),
                }
            
            if humidities:
                stats["humidity"] = {
                    "min": round(min(humidities), 2),
                    "max": round(max(humidities), 2),
                    "avg": round(sum(humidities) / len(humidities), 2),
                }
            
            result["last_24h_stats"] = stats
        
        return result
    finally:
        session.close()
