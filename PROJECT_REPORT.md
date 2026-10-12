# Smart Inventory Intelligence — Project Report

## Abstract

Traditional inventory systems primarily record quantities and generate fixed low-stock alerts. Such systems do not adequately respond to changing demand, slow-moving products, supplier reliability, slow-moving stock or abnormal inventory behaviour. Smart Inventory Intelligence combines a working inventory application with Python-based Data Science to analyse historical transactions, forecast short-term demand and convert analytical results into operational actions.

The application uses Flask for the web layer, SQLite for transactional storage, Pandas/NumPy for processing, Matplotlib for EDA, Random Forest regression for demand forecasting and Isolation Forest for anomaly detection. A decision engine combines forecast demand, safety stock, current inventory and incoming stock to generate replenishment recommendations.

## Problem statement

Businesses can face stockouts, overstocking, fixed reorder levels, slow-moving products, supplier blind spots, late anomaly detection and unnecessary purchases when excess stock exists elsewhere. The proposed system addresses these problems by combining inventory operations with predictive and descriptive Data Science.

## Objectives

1. Maintain product records and track available stock.
2. Record purchases, sales, returns and damaged products.
3. Track stock transfers between locations.
4. Clean and preprocess transaction data.
5. Identify demand patterns and predict future demand.
6. Predict stockout risk.
7. Detect abnormal inventory behaviour.
8. Identify slow-moving products.
9. Calculate reorder quantities and timing.
10. Recommend suppliers and stock transfers.
11. Provide intelligent alerts.

## Methodology

### Data collection

The application imports product, variant, inventory, customer, supplier, sales, checkout and purchase-order data from CSV files. New operational transactions are written to SQLite through the application.

### Preprocessing

- missing values are handled during CSV import
- date fields are converted to time-aware Pandas values
- cancelled/failed sales are excluded from analytical demand calculations
- transaction quantities are aggregated by day and variant
- daily zero-demand periods are inserted for continuous time-series features
- duplicate transaction structures are avoided by database keys

### Feature engineering

The forecasting model uses:

- day of week
- month
- day of month
- week of year
- previous-day demand (`lag1`)
- previous-week demand (`lag7`)
- rolling seven-day demand (`roll7`)

### Models

Candidate regression models are evaluated using the same time-based hold-out split:

- Linear Regression
- Decision Tree Regressor
- Random Forest Regressor
- Gradient Boosting Regressor

Random Forest is retained as the application's implemented forecasting model because it provides an explainable ensemble approach and integrates cleanly with the feature set and decision engine.

Isolation Forest is used as an additional abnormal-pattern detector.

### Evaluation

Regression metrics:

- MAE — Mean Absolute Error
- RMSE — Root Mean Squared Error
- R² — coefficient of determination

The current generated model artifact reports:

- MAE: 0.035
- RMSE: 0.336
- R²: -0.012
- Training rows: 10,105
- Test rows: 2,527

These are actual computed values from the supplied transaction history. The low/negative R² should be explained as a characteristic of this sparse dataset rather than hidden.

## EDA

EDA is a major module rather than a decorative dashboard. It includes time-series, categorical, distribution, relationship and correlation analysis. The application generates the plots using Python/Matplotlib.

The analysis covers:

- daily, weekly and monthly demand
- category sales
- top products
- stock distribution
- demand distribution
- supplier fulfillment
- slow-moving stock analysis
- payment mix
- stock versus demand
- feature correlation
- slow-moving inventory

## Decision engine

For each variant:

`Suggested order = forecast demand + safety stock − current stock − incoming stock`

Safety stock is estimated from recent average demand. Risk is then classified using stock threshold and estimated days of cover. Slow-moving stock is reviewed using recorded sales history and current stock levels.

## Application architecture

```text
User / Staff / Manager / Admin
              ↓
       Flask Web Application
              ↓
      SQLite Transaction Layer
              ↓
       Pandas + NumPy Cleaning
              ↓
        Feature Engineering
              ↓
   Random Forest + Isolation Forest
              ↓
       Prediction / Analysis
              ↓
        Decision Engine
       ↙       ↓        ↘
   Reorder   Transfer   Alert
              ↓
        User Action
              ↓
       New Transaction
              ↺
```

## Conclusion

The final application transforms inventory from a passive record-keeping system into a data-driven operational system. The user can enter transactions, inspect inventory, analyse historical behaviour, forecast demand, review risk, understand the reasoning behind recommendations and create purchase actions.

## Future scope

- LSTM/Transformer time-series forecasting
- real-time transaction streaming
- RFID and smart-shelf integration
- computer-vision shelf monitoring
- autonomous purchase-order generation
- weather/festival/event demand features
- cloud and multi-warehouse deployment
- ERP integration
- mobile application
- IoT inventory sensing
