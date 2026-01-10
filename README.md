# 📦 Inventory Management Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)
![LangChain](https://img.shields.io/badge/LangChain-0.1.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-Concept-orange.svg)

**An autonomous AI system for real-time warehouse logistics, predictive replenishment, and spatial optimization.**

[Features](#-features) • [Architecture](#-architecture) • [Case Study](#-case-study-details) • [Agent Capabilities](#-agent-capabilities) • [API Reference](#-api-reference)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Case Study Details](#-case-study-details)
- [Features](#-features)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [Agent Capabilities](#-agent-capabilities)
- [Warehouse Lifecycle](#-warehouse-lifecycle)
- [API Reference](#-api-reference)

---

## 🎯 Overview

The **Inventory Management Agent** is a sophisticated intelligence layer designed for modern warehouses and fulfillment centers. It bridges the gap between physical stock and digital records by coordinating specialized agents that handle everything from real-time tracking (via IoT/RFID) to predictive demand planning and automated vendor procurement.

- 📏 **Precision Tracking**: 100% digital-to-physical stock reconciliation.
- ⚡ **JIT Replenishment**: Autonomous purchase orders based on sales velocity and lead times.
- 📐 **Spatial Intelligence**: Optimizes picking routes and warehouse layout.
- 🛡️ **Risk Mitigation**: Continuous monitoring for shrinkage, expiration, and environmental risks.

---

## 📚 Case Study Details

| Attribute      | Description                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------- |
| **Objective**  | Eliminate stockouts and overstocking while maximizing warehouse throughput via autonomous agent coordination. |
| **Domain**     | Warehouse Management, Manufacturing, E-commerce Logistics                                                     |
| **Skills**     | IoT Integration, Predictive Analytics, Operations Research, Graph Theory, Multi-Agent Coordination            |
| **Complexity** | Advanced                                                                                                      |
| **Duration**   | 6-8 weeks implementation                                                                                      |

### Problem Statement

Warehouse operations are plagued by:

- **Phantom Inventory**: Discrepancies between what's on the shelf and what's in the computer.
- **Stock Bloat**: Over-ordering due to "fear of running out," tying up capital.
- **Inefficient Picking**: Workers traveling redundant paths in a poorly laid out warehouse.
- **High Wastage**: Items expiring or getting damaged due to poor rotation/monitoring.

### Solution

This agentic system provides:

1. **Real-time Reconciliation**: Constant audits via synchronized scanning and IoT data.
2. **Predictive ROP**: Reorder points that adjust daily based on live market demand.
3. **Pick-Route Optimization**: Dynamic mapping of the shortest path for every fulfillment order.
4. **Environment Monitoring**: Cold-chain and fragile-item alerts via edge sensor integration.

---

## ✨ Features

### Core Capabilities

| Feature                     | Description                                         |
| --------------------------- | --------------------------------------------------- |
| 📊 **Predictive Replenish** | ML-driven "Best-Time-To-Order" logic                |
| 📍 **Spatial Optimization** | Layout re-balancing for high-velocity items         |
| 🔗 **ERP Sync**             | Bi-directional integration with SAP/Oracle/Netsuite |
| 🚨 **Anomaly Detection**    | Identifying theft, damage, or data errors           |
| 📦 **Batch Fulfillment**    | Multi-order picking logic to save movement          |
| 🌡️ **IoT Watchdog**         | Temperature, Humidity, and Shock monitoring         |

### Agent Types

1. **Tracking Agent**: Manages the "Digital Twin" of physical stock.
2. **Replenishment Agent**: The decision-maker for procurement and vendor POs.
3. **Operations Agent**: Optimizes the "Workflows" (Picking, Packing, Receiving).
4. **Audit Agent**: Handles periodic cycle counts and discrepancy resolution.
5. **Quality Agent**: Monitors expiration dates and environmental sensor data.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INVENTORY MANAGEMENT AGENT                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      ORCHESTRATOR AGENT                          │   │
│  │  • Global Warehouse State                                         │   │
│  │  • Priority Task Queue                                            │   │
│  │  • System Reconciliation                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                    ┌───────────────┼───────────────┐                    │
│                    │               │               │                    │
│  ┌─────────────────▼──┐  ┌────────▼────────┐  ┌──▼─────────────────┐  │
│  │ TRACKING AGENT     │  │ REPLENISH AGENT │  │ OPERATIONS AGENT   │  │
│  │                    │  │                 │  │                    │  │
│  │ • RFID/Barcode Sync│  │ • Demand Curve  │  │ • Pick-Path Opt    │  │
│  │ • Bin Mapping      │  │ • Vendor Lead   │  │ • Batch Logic      │  │
│  │ • Unit of Measure  │  │ • Auto-PO Gen   │  │ • Labeling Autom.  │  │
│  └────────────────────┘  └─────────────────┘  └────────────────────┘  │
│                                                                          │
│  ┌────────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │ AUDIT AGENT        │  │ QUALITY AGENT   │  │ LOGISTICS AGENT    │  │
│  │                    │  │                 │  │                    │  │
│  │ • Cycle Count      │  │ • Expiry Track  │  │ • Dock Scheduling  │  │
│  │ • Shrinkage Detect │  │ • IoT Sens Check│  │ • Receiving Logic  │  │
│  │ • Error Correction │  │ • Fragile Alerts│  │ • Cross-Docking    │  │
│  └────────────────────┘  └─────────────────┘  └────────────────────┘  │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                              DATA LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ ERP System   │  │ Edge Sensors │  │ Warehouse DB │  │ Scanner API│ │
│  │ (SAP/Oracle) │  │ (MQTT/IoT)   │  │ (Postgres)   │  │ (RFID/USB) │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component        | Technology                          |
| ---------------- | ----------------------------------- |
| **AI Framework** | LangChain, LangGraph                |
| **LLM**          | GPT-4o (Reasoning), GPT-4o-mini     |
| **Database**     | PostgreSQL (GIS extension for maps) |
| **Edge Comm.**   | MQTT, AWS IoT Core / Azure IoT      |
| **Backend**      | FastAPI, Python 3.14+               |
| **Analytics**    | Scikit-learn, Pandas, SciPy         |
| **Integration**  | SAP RFC, OData, REST APIs           |

---

## 🤖 Agent Capabilities

### 1. Operations Agent (Pathfinding)

- **Graph Optimization**: Models the warehouse as a weighted graph to find the "Traveling Salesman" route for picking orders.
- **A/B/C Priority**: Recommends moving high-frequency items (Group A) closer to the docks.
- **Congestion Monitoring**: Re-routes pickers if one aisle is currently blocked or crowded.

### 2. Replenishment Agent (Procurement)

- **JIT Logic**: Calculates "Days of Cover" and triggers POs exactly when needed.
- **Vendor Scorecarding**: Automatically switches vendors if Lead Time or Quality drops.
- **Economic Order Quantity (EOQ)**: Balances shipping costs vs storage costs for the perfect batch size.

### 3. Tracking Agent (Digital Twin)

- **Sub-Location Mapping**: Tracks items down to the specific shelf, bin, and slot.
- **Lot/Serial Tracking**: Essential for medical and high-value electronics.
- **Virtual Inventory**: Manages stock committed to pending orders vs available for sale.

---

## 🔄 Warehouse Lifecycle

1. **Receiving**: Logistics Agent schedules a dock; Tracking Agent logs incoming pallets via RFID.
2. **Put-away**: Operations Agent suggests the optimal bin location based on item weight and velocity.
3. **Monitoring**: Quality Agent checks temperature via IoT; Audit Agent performs random cycle counts.
4. **Picking**: Customer order arrives; Operations Agent generates the most efficient route for the picker.
5. **Replenishing**: Stock hits ROP; Replenish Agent sends an automated PO to the vendor.

---

## 🔧 API Reference

### Endpoints

| Method  | Endpoint                    | Description               |
| ------- | --------------------------- | ------------------------- |
| `GET`   | `/api/v1/stock/{sku}`       | Get real-time stock count |
| `POST`  | `/api/v1/pick/generate`     | Generate optimized route  |
| `PATCH` | `/api/v1/stock/reconcile`   | Manual/Audit update       |
| `GET`   | `/api/v1/alerts/iot`        | Current sensor warnings   |
| `POST`  | `/api/v1/replenish/approve` | Approve pending POs       |

---

<div align="center">

**Author: Gopal Saini**
_Part of the AI Agents Case Studies Collection_

</div>
