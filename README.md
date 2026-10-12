# Smart Inventory Intelligence — Submission-Ready Project

**Course:** 22CSE554 — Data Science Using Python  
**Institution:** Nitte Meenakshi Institute of Technology (NMIT)  
**Academic Year:** 2026–27

## 1. Project purpose

Smart Inventory Intelligence is a complete Flask + SQLite inventory application in which Data Science is used to move inventory management from recording stock to **monitoring → analysing → predicting → deciding → acting**.

It is designed around the project objectives and workflow in the submitted presentation:

- product and stock management
- purchases, sales, returns and damaged-stock adjustments
- operational stock transfers
- transaction cleaning and feature engineering
- demand analysis and forecasting
- stockout/replenishment risk
- anomaly detection
- slow-moving inventory
- slow-moving stock analysis
- supplier intelligence
- intelligent notifications
- rule-based inventory assistant
- role-based access

## 2. What is actually implemented

### Operations
- Dashboard with live KPIs and priority actions
- Warehouse catalog with active-category filtering, search and pagination
- Add product and opening stock
- POS/order workflow
- Stock adjustment, customer return and damage adjustment
- Purchase-order list and receiving workflow
- Supplier performance and supplier creation
- Inter-store stock transfer

### Data Science
- Pandas-based transaction loading and cleaning
- Daily/weekly/monthly demand aggregation
- Calendar and lag features
- 7-day demand forecasting using Random Forest regression
- Model comparison: Linear Regression, Decision Tree, Random Forest and Gradient Boosting
- MAE, RMSE and R² evaluation
- Isolation Forest anomaly model
- Feature correlation analysis
- Decision engine for reorder quantity and stockout risk

### EDA
The Analytics & EDA module contains Python-generated charts for:

1. Daily sales trend
2. Monthly demand
3. Weekly demand
4. Category-wise sales
5. Top products
6. Stock distribution histogram
7. Historical demand distribution histogram
8. Supplier fulfillment
9. Slow-moving stock analysis
10. Payment-method mix
11. Stock vs historical demand scatter plot
12. Feature correlation heatmap
13. Slow-moving product table
14. Model evaluation table

Charts are generated with Matplotlib on the server, so the EDA page does not depend on an external chart CDN.

### Decision Center
For every analysed variant the system calculates:

`Suggested order = 7-day forecast + safety stock − current stock − incoming stock`

The user can open a **Decision Explanation** page and create a purchase order directly from a recommendation.

### Inventory Assistant
The assistant contains **50+ supported operational questions** across:

- stock
- sales
- demand
- replenishment
- slow-moving stock
- anomalies
- suppliers
- locations
- catalog/system information

It is intentionally rule-based: natural-language phrases are mapped to SQL queries and existing Data Science calculations. It is not presented as a generative-AI service.

### Access control
- **Admin:** employees, suppliers, products, model/system management and approvals
- **Manager:** stock, purchasing, suppliers, decisions and reports
- **Staff:** sales, stock updates, scans and operational views

Passwords are stored using salted PBKDF2-HMAC-SHA256 rather than plain text.

## 3. Dataset used

The supplied dataset is used as the historical foundation. The included database contains:

- 825 products
- 2,475 variants
- 2,475 inventory records
- 200 sales orders
- 579 sales line items
- 100 purchase orders
- 353 purchase-order line items
- 100 suppliers
- 200 customers
- 52 brands
- 25 category records

Only **3 categories are represented by products** in the supplied catalog. The Warehouse page therefore shows active categories rather than displaying a long list of empty taxonomy categories.

The historical dataset does not contain store/location IDs. The project therefore maintains a clearly separated operational location layer for the promised transfer feature: Central Warehouse, Store A and Store B. It does not claim that the historical sales records originated from those locations.

## 4. Demo accounts

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Manager | `manager` | `manager123` |
| Staff | `staff` | `staff123` |

Change the password from **My Profile** after first login if required.

## 5. Run the application

### Windows

```text
run.bat
```

or:

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

### Linux / WSL

```bash
chmod +x run.sh
./run.sh
```

The application automatically creates/initialises the SQLite database when started through `python app.py`.

If the database needs to be reset to the supplied dataset:

```bash
python bootstrap_db.py
python app.py
```

## 6. Important submission note

The model evaluation is reported from the actual supplied transaction history. Do **not** replace the displayed metrics with invented scores. The dataset is sparse, so R² can be close to zero even when absolute forecast error is small. This is discussed transparently in the project report.

## 7. Project structure

```text
Smart_Inventory_Submission/
├── app.py
├── model.py
├── inventory.db
├── bootstrap_db.py
├── generate_eda_assets.py
├── requirements.txt
├── run.bat
├── run.sh
├── README.md
├── PROJECT_REPORT.md
├── DATA_DICTIONARY.md
├── VIVA_QA.md
├── TESTING.md
├── data/
├── models/
├── templates/
└── static/
```


### Product branding
The application UI uses the supplied **Shelfie** logo and name. `static/shelfie_brand.png` is used for navigation branding and `static/shelfie_full.png` is used for the login screen and subtle page watermark.


## Source code map (for study and viva)

The code has been laid out with consistent indentation, numbered section comments, and readable SQL strings. Start with `CODE_GUIDE.md` for the feature map.

- `app.py`: Flask routes and application features.
- `model.py`: demand forecasting, anomaly detection, and reorder recommendations.
- `bootstrap_db.py`: rebuilds the local SQLite database from CSV data.
- `generate_eda_assets.py`: creates the exploratory-analysis charts.
- `templates/`: page markup.
- `static/style.css`: styles, including dark mode.
- `static/app.js`: theme, modal, assistant, row actions, and scanner behavior.

Formatting is intended to make the existing implementation easier to read; it is not a redesign of the app's features.
