# Shelfie---inventory-management
Shelfie is a smart inventory management app built with Python, Flask, and machine learning. It features inventory tracking, sales and purchases, demand forecasting, anomaly detection, slow-moving stock analysis, and intelligent reorder recommendations to support data-driven inventory decisions.

Shelfie --- Smart Inventory Management
Shelfie is a Python-based inventory management web application that
combines everyday stock operations with data analysis and
machine-learning-assisted decision support. It is designed as a college
Data Science using Python project.
The application helps users manage product stock and transactions,
review sales patterns, identify possible slow-moving inventory, forecast
demand, and calculate suggested reorder quantities.
Features
Inventory operations
View and search product variants.
Track available stock and product details.
Record sales and purchases.
Manage suppliers.
Support stock transfers between operational locations.
Use role-based access for Admin, Manager, and Staff accounts.
Data science and decision support
Explore historical sales and inventory data with EDA charts.
Forecast demand using a Random Forest regression model.
Identify unusual inventory behaviour using an Isolation Forest
model.
Flag possible slow-moving stock by comparing current stock with
recorded historical sales.
Calculate suggested order quantities using forecast demand, safety
stock, current stock, and incoming stock.
Review notifications and decision recommendations.
Interface
Shelfie branding and watermark.
Light and dark themes.
Warehouse search and filters.
Barcode/scanner interface with manual SKU entry fallback.
Inventory assistant for supported inventory questions.
> **Note:** Features depend on the included code and available data. The
> scanner's camera support can vary by browser and device.
Technology stack
Python --- application logic and data processing
Flask --- web application and routes
SQLite --- local prototype database
Pandas / NumPy --- data preparation and analysis
scikit-learn --- demand forecasting and anomaly detection
HTML / CSS / JavaScript --- user interface
Matplotlib --- exploratory data analysis charts
Project structure
``` text
Shelfie/
├── app.py                    # Flask application and page routes
├── model.py                  # Forecasting, anomaly detection, decision logic
├── bootstrap_db.py            # Database setup and data import
├── generate_eda_assets.py     # EDA chart generation
├── requirements.txt           # Python dependencies
├── CODE_GUIDE.md              # Feature-wise code guide
├── README.md                  # Project overview and setup
├── data/                      # Project dataset files, if included
├── templates/                 # HTML/Jinja templates
└── static/                    # CSS, JavaScript, branding, charts
```
The exact files and folders may vary slightly by project package
version.
Getting started
1. Requirements
Python 3.10 or later is recommended.
`pip`
A modern web browser
2. Download the project
Clone the repository:
``` bash
git clone https://github.com/YOUR-USERNAME/shelfie-inventory-management.git
cd shelfie-inventory-management
```
Or download the repository as a ZIP from GitHub and extract it.
3. Create and activate a virtual environment
Windows (PowerShell or Command Prompt):
``` bash
python -m venv .venv
.venv\Scripts\activate
```
macOS / Linux:
``` bash
python3 -m venv .venv
source .venv/bin/activate
```
4. Install dependencies
``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```
5. Initialize the database
If the project package includes the database bootstrap script, run:
``` bash
python bootstrap_db.py
```
This step depends on the dataset files being present in the expected
`data/` location. Follow any additional setup instructions in
`CODE_GUIDE.md` if the package version uses a different initialization
flow.
6. Start Shelfie
``` bash
python app.py
```
Open the local address printed by Flask in your terminal. In many
configurations, this is:
``` text
http://127.0.0.1:5000
```
Stop the server with `Ctrl+C`.
How the reorder recommendation works
Shelfie uses the following inventory calculation:
``` text
Suggested order = Forecast demand + Safety stock
                  - Current stock - Incoming stock
```
For example:
Forecast demand: 100 units
Safety stock: 20 units
Current stock: 35 units
Incoming stock: 10 units
``` text
Suggested order = 100 + 20 - 35 - 10
                = 75 units
```
The suggested quantity should be treated as a decision-support
recommendation. It assumes the counted stock is usable and incoming
stock will arrive in time. In practice, the result should be checked
against supplier lead time, pack sizes, and business rules.
Dataset and project scope
The application uses product and transaction data for technical products
such as smartphones and their variants. The operational location layer
used for stock-transfer demonstrations is separate from historical
source data when the source dataset does not provide store identifiers.
The slow-moving-stock view is intended to flag products that have
current inventory but comparatively low recorded historical sales. A
flag is a prompt for review, not proof that a product is obsolete:
interpretation depends on the sales period, stock age, and recent
demand.
The project focuses on technical-product inventory. Perishable-goods
expiry management is not a core feature.
Machine-learning notes
Random Forest Regressor: used for demand forecasting.
Isolation Forest: used to flag potential anomalies.
Model results depend on the amount, quality, and distribution of the
available transaction data. Do not interpret evaluation metrics as
evidence of production-level accuracy. Retraining and validation should
be performed when the dataset changes.
Security and data handling
Do not commit passwords, API keys, `.env` files, personal
information, or a live database containing private records.
Review `.gitignore` before publishing the repository.
Change any demo credentials and secret-key settings before public
deployment.
The included SQLite setup is intended for a local academic
prototype. A production deployment would need stronger
configuration, access controls, backups, and an appropriately
managed database.
Limitations
Forecast quality is constrained by the available historical data.
Historical sales may be sparse for individual variants.
Slow-moving-stock alerts require business review before taking
action.
Operational store/location data may be demonstration data rather
than fields from the original historical dataset.
The local Flask/SQLite setup is not a production deployment
configuration.
Future improvements
More robust time-series forecasting and model evaluation.
Improved supplier lead-time and purchase-order recommendations.
More complete stock-age and product-lifecycle analysis.
Stronger automated testing and deployment configuration.
Integration with external barcode scanners, ERP systems, or
multi-warehouse services.
Academic project
Project: Shelfie --- Smart Inventory Management  
Domain: Data Science using Python  
Application type: Inventory management web application with data
analysis and ML-assisted decision support
Update this section with your course, institution, team members, and
academic year if required by your submission guidelines.
License
No license is specified by default. Add a license file only after
deciding how you want others to use, modify, and distribute the project.
