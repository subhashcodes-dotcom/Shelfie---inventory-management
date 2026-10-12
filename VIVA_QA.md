# Viva Preparation — Smart Inventory Intelligence

## 1. Why did you choose this project?
Inventory is a practical business problem where Data Science can directly support decisions such as demand forecasting, stockout prevention and replenishment.

## 2. What is the main objective?
To transform inventory from reactive record keeping into predictive, data-driven decision support.

## 3. What is EDA?
Exploratory Data Analysis is the process of understanding the structure, distribution, trends, relationships and anomalies in data before building the predictive layer.

## 4. Why is EDA important here?
Forecasting is only useful when we understand demand patterns, stock distributions, category behaviour, slow-moving products and unusual observations first.

## 5. Why Pandas?
Pandas provides practical DataFrame operations for cleaning, grouping, joining, date handling and feature preparation.

## 6. Why Random Forest?
It is an ensemble of decision trees, handles nonlinear relationships, requires relatively little preprocessing and is understandable enough for a college project.

## 7. Why not deep learning?
The current dataset is relatively small and sparse for a complex deep-learning system. A simpler explainable model is more appropriate; LSTM/Transformers are future scope.

## 8. What is MAE?
Mean Absolute Error is the average absolute difference between actual and predicted values. Lower is better.

## 9. What is RMSE?
Root Mean Squared Error penalises larger errors more strongly than MAE. Lower is better.

## 10. What is R²?
R² measures how much variation in the target is explained by the model relative to a baseline. Values near zero mean limited explanatory power on this hold-out set.

## 11. Why can R² be negative?
If the model performs worse than the mean-value baseline on the hold-out data, R² becomes negative. Sparse transaction data with many zero-demand observations can produce this behaviour.

## 12. What is Isolation Forest?
It is an unsupervised anomaly-detection algorithm that isolates unusual observations using random partitioning.

## 13. How is stockout risk calculated?
The application combines current stock, recent average demand, predicted demand, threshold and estimated days of stock cover.

## 14. How is reorder quantity calculated?
Forecast + safety stock − current stock − incoming stock, clipped at zero.

## 15. What is safety stock?
A buffer intended to reduce the chance of stockout when demand varies.

## 16. What is slow-moving inventory?
Inventory with low historical sales relative to the stock currently held.

## 17. What is supplier fulfillment?
Received quantity divided by ordered quantity, expressed as a percentage.

## 18. Why is there a location layer?
The supplied historical dataset does not contain store IDs. The project therefore separates the operational transfer layer from historical transaction provenance.

## 19. Why is the assistant rule-based?
It gives deterministic, auditable answers from the application's own database and model calculations without requiring an external generative-AI API.

## 20. Is the assistant actually AI?
The inventory assistant itself is rule-based. The Data Science intelligence comes from the forecasting and anomaly-detection components.

## 21. What happens when a sale is recorded?
The application creates a sales order, line item and checkout record, decreases inventory and writes an inventory event.

## 22. What happens when a purchase is received?
Outstanding purchase quantities are added to inventory and the purchase item/order status is updated.

## 23. What happens when stock is damaged?
Inventory is decreased and an inventory audit event records the reason.

## 24. Why SQLite?
It is lightweight, self-contained and sufficient for a college demonstration. PostgreSQL or another server database would be a future production option.

## 25. What is Flask?
Flask is the Python web framework used to provide routes, sessions, templates and the application interface.

## 26. Why role-based access?
Different users should have different operational permissions. Admin manages users and system controls; Manager handles operational approvals; Staff handles daily transactions.

## 27. What is feature engineering?
Creating useful predictive variables from raw data. This project creates calendar features, lag features and rolling demand features.

## 28. What is a time-based train/test split?
Historical observations are used for training and later observations are kept for testing, which better reflects forecasting than random shuffling.

## 29. What is the continuous cycle?
New transactions enter the database, analytics and forecasting use the updated history, and the decision engine produces new actions.

## 30. What is the future scope?
LSTM/Transformer forecasting, RFID, IoT shelves, computer vision, real-time streaming, autonomous purchase orders, weather/event features, cloud deployment and ERP integration.
