# Smart Inventory Intelligence — Easy Code Guide

## 1. What kind of code is this?
This is a **Flask web application written in Python**.

- Python = main programming language
- Flask = connects browser pages to Python functions
- SQLite = database
- Pandas = data cleaning and EDA
- Matplotlib = graphs
- Scikit-learn = machine learning
- HTML/CSS = user interface

The application follows a simple flow:

**Browser → Flask route → Python logic → SQLite / ML → HTML result**

---

## 2. Where to explain each feature
The main `app.py` is arranged feature-wise. Use the numbered headings in the file.

| Section | Feature | Viva explanation |
|---|---|---|
| 1 | Database connection | Opens SQLite so Python can read/write data. |
| 2 | Authentication | Hashes passwords and verifies login. |
| 3 | Database setup | Creates tables and loads initial data. |
| 4 | Sessions & roles | Remembers the logged-in user and checks permissions. |
| 5 | Dashboard | Calculates KPIs such as stock and low-stock count. |
| 6 | EDA | Creates meaningful sales, demand and inventory charts. |
| 7 | Alerts | Converts inventory risks into user alerts. |
| 8 | Login | Accepts username/password and creates a session. |
| 9 | Dashboard | Shows the main operational summary. |
| 10 | Warehouse | Searches products and displays live inventory. |
| 11 | Orders | Records a sale and decreases stock. |
| 12 | Purchases | Records purchase orders and received stock. |
| 13 | Analytics | Displays the EDA results. |
| 14 | Decision Center | Uses forecast + stock data to recommend reorder. |
| 15 | Notifications | Shows low-stock, stockout and slow-moving stock alerts. |
| 16 | Employees | Admin creates and manages user accounts. |
| 17 | Rates/Tables | Manages supporting configuration data. |
| 18 | Transfers | Moves stock between warehouse/store locations. |
| 19 | Assistant | Matches questions to SQL/data-science queries. |
| 20 | Profile | Updates the current user's details/password. |
| 21 | System | Shows model metrics and allows retraining. |
| 22 | Export/API | Exports recommendations and exposes data to the app. |
| 23 | Start app | Runs Flask on localhost. |

---

## 3. Machine-learning code: `model.py`

### Step 1 — Read sales history
`sales_frame()` collects sales by date and product variant.

### Step 2 — Create features
The model uses:
- day of week
- month
- day of month
- week number
- previous-day sales (`lag1`)
- previous-week sales (`lag7`)
- 7-day moving average (`roll7`)

### Step 3 — Train
`train_and_save()` trains a **Random Forest Regressor**.

### Step 4 — Evaluate
It calculates:
- MAE
- RMSE
- R²

### Step 5 — Detect anomalies
Isolation Forest is trained for abnormal demand patterns.

### Step 6 — Make inventory decisions
`get_recommendations()` combines the forecast with current stock and incoming stock.

**Formula:**

`Recommended Order = Forecast + Safety Stock - Current Stock - Incoming Stock`

If the result is negative, it becomes zero.

---

## 4. Easy viva answers

### Why Flask?
"Flask is a lightweight Python web framework. It connects the web interface to our Python, database and machine-learning logic."

### Why SQLite?
"SQLite is simple, local and suitable for a college-scale application."

### Why Pandas?
"Pandas is used for reading, cleaning, grouping and analysing transaction data."

### Why Random Forest?
"It can model non-linear relationships and works well with several engineered features without requiring a very complex model."

### Why Isolation Forest?
"It is used to identify unusual observations that may indicate abnormal inventory behaviour."

### What is EDA?
"Exploratory Data Analysis means understanding the dataset before modelling. We analyse trends, categories, demand, stock and relationships using statistics and visualizations."

### What happens when a sale is made?
"The application checks available stock, creates the order and payment records, decreases inventory and records the transaction. The new transaction can then contribute to future analysis."

### What makes this different from normal inventory software?
"Normal inventory software mainly records current stock. Our application also analyses historical data, predicts demand, detects risk and converts those predictions into reorder decisions."

### Is the Inventory Assistant generative AI?
"No. It is a rule-based operational assistant. It matches common inventory questions to predefined SQL queries and machine-learning calculations. This makes the result predictable and easy to explain."

---

## 5. The most important code to understand

Do not try to memorize all 65,000 lines or every HTML line.

For viva, understand these five flows:

1. **Login** → user/password → database → session
2. **Sale** → select product → check stock → save sale → reduce stock
3. **EDA** → database → Pandas → aggregation → Matplotlib graph
4. **ML** → sales history → features → Random Forest → forecast
5. **Decision** → forecast + stock + incoming → reorder recommendation

Those five flows explain the core of the project.


## 6. Code formatting map

The source files are formatted with clear indentation, blank lines, and numbered feature headings. Formatting is intended to improve readability without changing the application's feature logic.

- `app.py` — Flask routes, permissions, database actions, and application pages.
- `model.py` — sales-data preparation, Random Forest demand prediction, Isolation Forest anomaly detection, and reorder decisions.
- `bootstrap_db.py` — rebuilds the SQLite database from CSV files. Run only when you intentionally want to rebuild/reset the database.
- `generate_eda_assets.py` — generates the static EDA chart images.
- `validate_project.py` — checks Python/Jinja syntax, database tables, model metrics, and chart assets.
- `templates/` — HTML pages, now laid out across multiple lines with indentation.
- `static/style.css` — interface styling, grouped with numbered sections; `static/app.js` — browser interactions grouped by feature.

**Recommended reading order for viva:** `CODE_GUIDE.md` → `app.py` sections 8–14 → `model.py` sections 2–6 → `templates/warehouse.html` → `static/app.js`.
