# Job Card & Workshop Management Suite (job_card_management)

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20%7C%2018.0%20%7C%2019.0-714B67?logo=odoo&logoColor=white)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](LICENSE)
[![Category](https://img.shields.io/badge/Category-Services%2FWorkshop-orange.svg)]()
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

> **Comprehensive Automotive, Workshop, Field Service & Heavy Equipment Job Card Lifecycle Management for Odoo.**

---

## 📌 Overview

**Job Card & Workshop Management Suite** is a full-featured enterprise solution designed for service centers, garages, heavy equipment maintenance, and field workshops. It provides end-to-end operational visibility from initial vehicle check-in and digital estimates, through technician task assignment, inventory parts allocation, purchase requisitions, and final customer billing with profitability reporting.

---

## ✨ Key Features

### 1. 🚗 Vehicle Catalog & Asset Management
- Comprehensive vehicle records tracking **VIN / Chassis No**, License Plate, Make, Model, Engine Type, Mileage, and Service History.
- Pre-loaded vehicle catalog seed data for instant setup.

### 2. 📋 Interactive Job Cards & Service Estimates
- **Estimate-to-Job Workflow**: Generate quotation estimates with parts and labor break-downs, customer digital approvals, and 1-click conversion to active Job Cards.
- **Service Stages**: Clear visual stages from Draft ➔ In Progress ➔ Quality Control ➔ Ready for Invoicing ➔ Completed.

### 3. 👨‍🔧 Technician Task Tracking & Labor Allocation
- Assign multiple certified technicians per job line with labor rates and actual hours logged.
- Technician performance and productivity analytics.

### 4. 📦 Inventory Issue & Consumables Allocation
- **Stock Picking Integration**: Direct stock reservations and issues linked specifically to Job Card reference numbers.
- Consumable parts requisition and excess warning wizards preventing budget overruns.

### 5. 🛒 Procurement & Purchase Requisitions
- Direct supplier purchase order generation for spare parts not currently in stock.
- GRV (Goods Received Voucher) tracking against remaining purchase order balances.

### 6. 📊 Real-Time Interactive Dashboard & Profitability Analytics
- Built with modern Odoo OWL components (`static/src/js/job_card_dashboard.js`).
- Key metrics: Active jobs, Overdue repairs, Parts cost vs Labor revenue, Technician utilization, and Gross margin per job.

---

## 🚀 Installation & Setup

1. **Clone or Copy** this repository into your Odoo custom addons directory:
   ```bash
   git clone git@github.com:draftpos/job_card_management.git job_card_management
   ```
2. **Update Addons List**:
   - Enable Developer Mode in Odoo (`Settings` -> `General Settings`).
   - Navigate to `Apps` -> `Update Apps List`.
3. **Install the Module**:
   - Search for **Job Card Management** (`job_card_management`).
   - Click **Install** or **Upgrade**.

---

## 📁 Technical Information

| Attribute | Value |
|---|---|
| **Technical Name** | `job_card_management` |
| **Category** | Services / Workshop |
| **Odoo Compatibility** | Odoo 17.0+ & 18.0+ |
| **Dependencies** | `sale`, `sale_management`, `purchase`, `stock`, `account`, `hr`, `hr_expense`, `mail` |
| **License** | LGPL-3 |
| **Maintainer** | DraftPOS & Havano Solutions |

---

## 📄 License

This module is licensed under the **GNU Lesser General Public License v3.0 (LGPL-3)**. See the [LICENSE](LICENSE) file for details.
