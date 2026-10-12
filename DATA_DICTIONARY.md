# Data Dictionary

| Table | Purpose | Important fields |
|---|---|---|
| brands | Brand master | id, name |
| categories | Product taxonomy | id, name, parent_id |
| products | Product master | id, brand_id, category_id, name, sku, base_price |
| variants | Sellable product variants | id, product_id, ram, storage, color, sku_variant |
| inventory | Current stock | variant_id, quantity, low_stock_threshold (expiry_date is a legacy source column and is not used by Shelfie) |
| customers | Customer master | id, name, email, phone |
| suppliers | Supplier master | id, name, contact_name, phone, email |
| sales_orders | Sales header | id, customer_id, status, total_amount, order_date |
| sales_items | Sales transactions | order_id, variant_id, quantity, unit_price |
| checkouts | Payment records | payment_method, amount_paid, paid_at |
| purchase_orders | Purchase header | id, supplier_id, status, order_date |
| purchase_items | Purchase transaction lines | order_id, variant_id, quantity_ordered, quantity_received, unit_cost |
| users | Application accounts | username, name, role, password |
| locations | Operational locations | id, name, type |
| location_inventory | Operational location stock | location_id, variant_id, quantity |
| transfers | Inter-location transfers | from_location, to_location, variant_id, quantity, status |
| inventory_events | Audit trail | variant_id, event_type, quantity_delta, reason, created_at |
