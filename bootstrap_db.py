"""Create the included SQLite database from the supplied CSV dataset.
Run this only if inventory.db is deleted or you want a clean reset.
"""
import sqlite3
import hashlib
import secrets
from pathlib import Path
import pandas as pd
from model import train_and_save
BASE = Path(__file__).resolve().parent
DB = BASE / 'inventory.db'
DATA = BASE / 'data'
MODELS = BASE / 'models'


# 1. PASSWORD HASHING FOR SEEDED USERS
def hp(p):
    salt = secrets.token_bytes(16)
    d = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, 180000)
    return 'pbkdf2$180000$' + salt.hex() + '$' + d.hex()


# 2. IMPORT CSV DATA INTO SQLITE
def imp(c, file, table, cols):
    df = pd.read_csv(DATA / file)
    vals = []
    for _, r in df.iterrows():
        vals.append(tuple((None if pd.isna(r[col]) else r[col] for col in cols)))
    c.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


# 3. CREATE AND POPULATE THE DATABASE
if DB.exists():
    DB.unlink()
c = sqlite3.connect(DB)
c.executescript('''
CREATE TABLE brands(id TEXT PRIMARY KEY,name TEXT,logo_url TEXT,description TEXT);
CREATE TABLE categories(id TEXT PRIMARY KEY,name TEXT,parent_id TEXT,description TEXT);
CREATE TABLE products(id TEXT PRIMARY KEY,brand_id TEXT,category_id TEXT,name TEXT,sku TEXT,description TEXT,base_price REAL);
CREATE TABLE variants(id TEXT PRIMARY KEY,product_id TEXT,ram TEXT,storage TEXT,color TEXT,sku_variant TEXT,price_modifier REAL);
CREATE TABLE inventory(id TEXT PRIMARY KEY,variant_id TEXT,quantity INTEGER,low_stock_threshold INTEGER,expiry_date TEXT);
CREATE TABLE customers(id TEXT PRIMARY KEY,name TEXT,email TEXT,phone TEXT,address TEXT,created_at TEXT);
CREATE TABLE suppliers(id TEXT PRIMARY KEY,name TEXT,contact_name TEXT,phone TEXT,email TEXT,address TEXT);
CREATE TABLE sales_orders(id TEXT PRIMARY KEY,customer_id TEXT,created_by INTEGER,status TEXT,total_amount REAL,order_date TEXT);
CREATE TABLE sales_items(id TEXT PRIMARY KEY,order_id TEXT,variant_id TEXT,quantity INTEGER,unit_price REAL);
CREATE TABLE checkouts(id TEXT PRIMARY KEY,sales_order_item_id TEXT,processed_by INTEGER,payment_method TEXT,amount_paid REAL,discount_type TEXT,discount_amount REAL,paid_at TEXT);
CREATE TABLE purchase_orders(id TEXT PRIMARY KEY,supplier_id TEXT,created_by INTEGER,status TEXT,total_amount REAL,order_date TEXT,received_date TEXT);
CREATE TABLE purchase_items(id TEXT PRIMARY KEY,order_id TEXT,variant_id TEXT,quantity_ordered INTEGER,quantity_received INTEGER,unit_cost REAL);
CREATE TABLE users(username TEXT PRIMARY KEY,name TEXT,role TEXT,password TEXT);
CREATE TABLE locations(id TEXT PRIMARY KEY,name TEXT,type TEXT);
CREATE TABLE location_inventory(location_id TEXT,variant_id TEXT,quantity INTEGER,PRIMARY KEY(location_id,variant_id));
CREATE TABLE transfers(id TEXT PRIMARY KEY,from_location TEXT,to_location TEXT,variant_id TEXT,quantity INTEGER,status TEXT,created_at TEXT,created_by TEXT);
CREATE TABLE inventory_events(id INTEGER PRIMARY KEY AUTOINCREMENT,variant_id TEXT,event_type TEXT,quantity_delta INTEGER,reason TEXT,created_at TEXT,created_by TEXT);
''')
for f, t, cols in [('brands.csv', 'brands', ['id', 'name', 'logo_url', 'description']), ('categories.csv', 'categories',
    ['id', 'name', 'parent_id', 'description']), ('products.csv', 'products', ['id', 'brand_id', 'category_id', 'name',
    'sku', 'description', 'base_price']), ('product_variants.csv', 'variants', ['id', 'product_id', 'ram', 'storage',
    'color', 'sku_variant', 'price_modifier']), ('inventory.csv', 'inventory', ['id', 'variant_id', 'quantity', 'low_stock_threshold',
    'expiry_date']), ('customers.csv', 'customers', ['id', 'name', 'email', 'phone', 'address', 'created_at']), ('suppliers.csv',
    'suppliers', ['id', 'name', 'contact_name', 'phone', 'email', 'address']), ('sales_orders.csv', 'sales_orders',
    ['id', 'customer_id', 'created_by', 'status', 'total_amount', 'order_date']), ('sales_order_items.csv', 'sales_items',
    ['id', 'order_id', 'variant_id', 'quantity', 'unit_price']), ('checkouts.csv', 'checkouts', ['id', 'sales_order_item_id',
    'processed_by', 'payment_method', 'amount_paid', 'discount_type', 'discount_amount', 'paid_at']), ('purchase_orders.csv',
    'purchase_orders', ['id', 'supplier_id', 'created_by', 'status', 'total_amount', 'order_date', 'received_date'])]:
    imp(c, f, t, cols)
po = pd.read_csv(DATA / 'purchase_order_items.csv')
po['quantity_received'] = po['quantity_received'].fillna(0)
for _, r in po.iterrows():
    c.execute('INSERT INTO purchase_items VALUES (?,?,?,?,?,?)', (r['id'], r['order_id'], r['variant_id'],
        int(r['quantity_ordered']), int(r['quantity_received']), float(r['unit_cost'])))
for u, n, r, p in [('admin', 'Marvin McKinney', 'Admin', 'admin123'), ('manager', 'Store Manager', 'Manager',
    'manager123'), ('staff', 'Store Staff', 'Staff', 'staff123')]:
    c.execute('INSERT INTO users VALUES (?,?,?,?)', (u, n, r, hp(p)))
for loc in [('LOC001', 'Central Warehouse', 'Warehouse'), ('LOC002', 'Store A', 'Store'), ('LOC003', 'Store B',
    'Store')]:
    c.execute('INSERT INTO locations VALUES (?,?,?)', loc)
for vid, q in c.execute('SELECT variant_id,quantity FROM inventory').fetchall():
    a = round(int(q) * 0.25)
    b = round(int(q) * 0.15)
    w = int(q) - a - b
    for loc, n in [('LOC001', w), ('LOC002', a), ('LOC003', b)]:
        c.execute('INSERT INTO location_inventory VALUES (?,?,?)', (loc, vid, n))
c.commit()
c.close()
print('Database seeded:', DB)
print('Training models...')
print(train_and_save(DB, MODELS))
