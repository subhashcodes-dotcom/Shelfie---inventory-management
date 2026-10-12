import os
import sqlite3
import json
import math
import re
import hashlib
import hmac
import secrets
from datetime import datetime, date, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from model import train_and_save, get_recommendations, get_metrics, compare_models
BASE = Path(__file__).resolve().parent
DB = BASE / 'inventory.db'
DATA = BASE / 'data'
MODELS = BASE / 'models'
app = Flask(__name__)
app.secret_key = os.environ.get('SMART_INVENTORY_SECRET', 'smart-inventory-nmit-2026-submission')
DEMO_USERS = {'admin': {'password': 'admin123', 'role': 'Admin', 'name': 'Marvin McKinney'}, 'manager': {'password': 'manager123',
    'role': 'Manager', 'name': 'Store Manager'}, 'staff': {'password': 'staff123', 'role': 'Staff', 'name': 'Store Staff'}}


# 1. DATABASE CONNECTION
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


# 2. USER AUTHENTICATION & PASSWORD SECURITY
def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 180000)
    return 'pbkdf2$180000$' + salt.hex() + '$' + digest.hex()

def verify_password(password, stored):
    if not stored:
        return False
    if stored.startswith('pbkdf2$'):
        try:
            _, rounds, salt_hex, digest_hex = stored.split('$', 3)
            check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt_hex),
                int(rounds))
            return hmac.compare_digest(check.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(password, stored)


# 3. DATABASE TABLES & INITIAL DATA
def init_db():
    c = db()
    c.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS brands(id TEXT PRIMARY KEY,name TEXT,logo_url TEXT,description TEXT);
    CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY,name TEXT,parent_id TEXT,description TEXT);
    CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,brand_id TEXT,category_id TEXT,name TEXT,sku TEXT,description TEXT,base_price REAL);
    CREATE TABLE IF NOT EXISTS variants(id TEXT PRIMARY KEY,product_id TEXT,ram TEXT,storage TEXT,color TEXT,sku_variant TEXT,price_modifier REAL);
    CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY,variant_id TEXT,quantity INTEGER,low_stock_threshold INTEGER,expiry_date TEXT);
    CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,name TEXT,email TEXT,phone TEXT,address TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS suppliers(id TEXT PRIMARY KEY,name TEXT,contact_name TEXT,phone TEXT,email TEXT,address TEXT);
    CREATE TABLE IF NOT EXISTS sales_orders(id TEXT PRIMARY KEY,customer_id TEXT,created_by INTEGER,status TEXT,total_amount REAL,order_date TEXT);
    CREATE TABLE IF NOT EXISTS sales_items(id TEXT PRIMARY KEY,order_id TEXT,variant_id TEXT,quantity INTEGER,unit_price REAL);
    CREATE TABLE IF NOT EXISTS checkouts(id TEXT PRIMARY KEY,sales_order_item_id TEXT,processed_by INTEGER,payment_method TEXT,amount_paid REAL,discount_type TEXT,discount_amount REAL,paid_at TEXT);
    CREATE TABLE IF NOT EXISTS purchase_orders(id TEXT PRIMARY KEY,supplier_id TEXT,created_by INTEGER,status TEXT,total_amount REAL,order_date TEXT,received_date TEXT);
    CREATE TABLE IF NOT EXISTS purchase_items(id TEXT PRIMARY KEY,order_id TEXT,variant_id TEXT,quantity_ordered INTEGER,quantity_received INTEGER,unit_cost REAL);
    CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,name TEXT,role TEXT,password TEXT);
    CREATE TABLE IF NOT EXISTS locations(id TEXT PRIMARY KEY,name TEXT,type TEXT);
    CREATE TABLE IF NOT EXISTS location_inventory(location_id TEXT,variant_id TEXT,quantity INTEGER,PRIMARY KEY(location_id,variant_id));
    CREATE TABLE IF NOT EXISTS transfers(id TEXT PRIMARY KEY,from_location TEXT,to_location TEXT,variant_id TEXT,quantity INTEGER,status TEXT,created_at TEXT,created_by TEXT);
    CREATE TABLE IF NOT EXISTS inventory_events(id INTEGER PRIMARY KEY AUTOINCREMENT,variant_id TEXT,event_type TEXT,quantity_delta INTEGER,reason TEXT,created_at TEXT,created_by TEXT);
    ''')
    for u, info in DEMO_USERS.items():
        c.execute('INSERT OR IGNORE INTO users(username,name,role,password) VALUES (?,?,?,?)', (u, info['name'],
            info['role'], hash_password(info['password'])))
    for loc in [('LOC001', 'Central Warehouse', 'Warehouse'), ('LOC002', 'Store A', 'Store'), ('LOC003', 'Store B',
        'Store')]:
        c.execute('INSERT OR IGNORE INTO locations VALUES (?,?,?)', loc)
    c.commit()
    return c

def import_csv(c, file, table, cols):
    df = pd.read_csv(DATA / file)
    vals = []
    for _, r in df.iterrows():
        vals.append(tuple((None if pd.isna(r[col]) else r[col] for col in cols)))
    q = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    c.executemany(q, vals)

def seed():
    c = init_db()
    if c.execute('SELECT COUNT(*) FROM products').fetchone()[0] > 0:
        c.close()
        return
    import_csv(c, 'brands.csv', 'brands', ['id', 'name', 'logo_url', 'description'])
    import_csv(c, 'categories.csv', 'categories', ['id', 'name', 'parent_id', 'description'])
    import_csv(c, 'products.csv', 'products', ['id', 'brand_id', 'category_id', 'name', 'sku', 'description',
        'base_price'])
    import_csv(c, 'product_variants.csv', 'variants', ['id', 'product_id', 'ram', 'storage', 'color', 'sku_variant',
        'price_modifier'])
    import_csv(c, 'inventory.csv', 'inventory', ['id', 'variant_id', 'quantity', 'low_stock_threshold', 'expiry_date'])
    import_csv(c, 'customers.csv', 'customers', ['id', 'name', 'email', 'phone', 'address', 'created_at'])
    import_csv(c, 'suppliers.csv', 'suppliers', ['id', 'name', 'contact_name', 'phone', 'email', 'address'])
    import_csv(c, 'sales_orders.csv', 'sales_orders', ['id', 'customer_id', 'created_by', 'status', 'total_amount',
        'order_date'])
    import_csv(c, 'sales_order_items.csv', 'sales_items', ['id', 'order_id', 'variant_id', 'quantity', 'unit_price'])
    import_csv(c, 'checkouts.csv', 'checkouts', ['id', 'sales_order_item_id', 'processed_by', 'payment_method',
        'amount_paid', 'discount_type', 'discount_amount', 'paid_at'])
    import_csv(c, 'purchase_orders.csv', 'purchase_orders', ['id', 'supplier_id', 'created_by', 'status',
        'total_amount', 'order_date', 'received_date'])
    po = pd.read_csv(DATA / 'purchase_order_items.csv')
    po['quantity_received'] = po['quantity_received'].fillna(0)
    vals = [(None if pd.isna(r['id']) else r['id'], None if pd.isna(r['order_id']) else r['order_id'], None if pd.isna(r['variant_id']) else r['variant_id'],
        int(r['quantity_ordered']), int(r['quantity_received']), float(r['unit_cost'])) for _, r in po.iterrows()]
    c.executemany('INSERT INTO purchase_items(id,order_id,variant_id,quantity_ordered,quantity_received,unit_cost) VALUES (?,?,?,?,?,?)',
        vals)
    rows = c.execute('SELECT variant_id,quantity FROM inventory').fetchall()
    for r in rows:
        total = int(r['quantity'])
        a = round(total * 0.25)
        b = round(total * 0.15)
        wh = total - a - b
        c.executemany('INSERT OR REPLACE INTO location_inventory VALUES (?,?,?)', [('LOC001', r['variant_id'],
            wh), ('LOC002', r['variant_id'], a), ('LOC003', r['variant_id'], b)])
    c.commit()
    c.close()
    train_and_save(DB, MODELS)


# 4. LOGIN SESSION & ROLE PERMISSIONS
def current_user():
    return session.get('user')

def login_required(fn):

    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for('login', next=request.path))
        return fn(*a, **kw)
    return wrapper

def role_required(*roles):

    def deco(fn):

        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user():
                return redirect(url_for('login'))
            if current_user()['role'] not in roles:
                flash('Your role does not have permission for that action.', 'error')
                return redirect(request.referrer or url_for('dashboard'))
            return fn(*a, **kw)
        return wrapper
    return deco


# 5. DASHBOARD / KPI CALCULATIONS
def stats():
    c = db()
    low = c.execute('SELECT COUNT(*) n FROM inventory WHERE quantity<=low_stock_threshold').fetchone()['n']
    slow_moving = c.execute((
                                'SELECT COUNT(*) n FROM inventory i WHERE i.quantity>0 AND COALESCE((SELECT '
                                'SUM(si.quantity) FROM sales_items si WHERE si.variant_id=i.variant_id),0)<=2'
                            )).fetchone()['n']
    s = {'products': c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'], 'variants': c.execute('SELECT COUNT(*) n FROM variants').fetchone()['n'],
        'stock': c.execute('SELECT COALESCE(SUM(quantity),0) n FROM inventory').fetchone()['n'], 'sales': c.execute('SELECT COUNT(*) n FROM sales_items').fetchone()['n'],
        'low': low, 'slow_moving': slow_moving, 'suppliers': c.execute('SELECT COUNT(*) n FROM suppliers').fetchone()['n'],
        'orders': c.execute("SELECT COUNT(*) n FROM purchase_orders WHERE status IN ('ordered','processing')").fetchone()['n'],
        'customers': c.execute('SELECT COUNT(*) n FROM customers').fetchone()['n']}
    c.close()
    return s


# 6. EDA & VISUALIZATION
def build_eda_charts(eda, corr):
    out = BASE / 'static' / 'eda'
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'figure.figsize': (9, 4.2), 'axes.titlesize': 12, 'axes.labelsize': 9})

    def save(name, draw):
        fig, ax = plt.subplots()
        draw(fig, ax)
        fig.tight_layout()
        fig.savefig(out / f'{name}.png', dpi=130, bbox_inches='tight')
        plt.close(fig)

    def line_chart(data, title, xlabel='Period', ylabel='Units'):

        def draw(fig, ax):
            labels = [str(x['label']) for x in data]
            values = [x['value'] for x in data]
            ax.plot(range(len(values)), values, marker='o', linewidth=2)
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.2)
            if labels:
                step = max(1, len(labels) // 12)
                ax.set_xticks(range(0, len(labels), step))
                ax.set_xticklabels(labels[::step], rotation=35, ha='right')
        return draw

    def bar_chart(data, title, ylabel='Units', horizontal=False):

        def draw(fig, ax):
            labels = [str(x['label'])[:28] for x in data]
            values = [x['value'] for x in data]
            if horizontal:
                order = np.argsort(values)
                ax.barh(range(len(values)), np.array(values)[order])
                ax.set_yticks(range(len(values)))
                ax.set_yticklabels(np.array(labels)[order])
            else:
                ax.bar(range(len(values)), values)
                ax.set_xticks(range(len(values)))
                ax.set_xticklabels(labels, rotation=35, ha='right')
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            ax.grid(axis='y', alpha=0.2)
        return draw

    def hist_chart(values, title, xlabel):

        def draw(fig, ax):
            if values:
                ax.hist(values, bins=min(12, max(4, len(set(values)))), edgecolor='white')
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel('Variants')
            ax.grid(axis='y', alpha=0.2)
        return draw
    save('daily_sales', line_chart(eda['daily'], 'Daily sales units', 'Date', 'Units sold'))
    save('monthly_demand', line_chart(eda['monthly'], 'Monthly demand', 'Month', 'Units sold'))
    save('weekly_demand', line_chart(eda['weekly'], 'Weekly demand', 'Week', 'Units sold'))
    save('category_sales', bar_chart(eda['category'], 'Units sold by category'))
    save('top_products', bar_chart(eda['top_products'], 'Top 10 products by units', 'Units sold', True))
    save('stock_distribution', hist_chart(eda['stock_hist'], 'Current stock distribution', 'Stock units'))
    save('demand_distribution', hist_chart(eda['demand_hist'], 'Historical demand distribution', 'Units sold'))
    save('supplier_fulfillment', bar_chart(eda['suppliers'], 'Supplier fulfillment', 'Fulfillment %', True))
    save('slow_moving_stock', bar_chart(eda['slow_stock'], 'Slow-moving stock variants', 'Current stock',
        True))
    save('payment_mix', bar_chart(eda['payments'], 'Checkout methods', 'Transactions'))

    def scatter_draw(fig, ax):
        pts = eda.get('scatter', [])
        ax.scatter([p['x'] for p in pts], [p['y'] for p in pts], s=20, alpha=0.65)
        ax.set_title('Current stock vs historical demand')
        ax.set_xlabel('Current stock')
        ax.set_ylabel('Historical units sold')
        ax.grid(alpha=0.2)
    save('stock_vs_demand', scatter_draw)

    def corr_draw(fig, ax):
        keys = ['stock', 'threshold', 'sold', 'price']
        mat = np.array([[corr.get(r, {}).get(c, 0) for c in keys] for r in keys], dtype=float)
        im = ax.imshow(mat, vmin=-1, vmax=1)
        ax.set_xticks(range(4))
        ax.set_yticks(range(4))
        ax.set_xticklabels(keys)
        ax.set_yticklabels(keys)
        ax.set_title('Feature correlation heatmap')
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f'{mat[i, j]:.2f}', ha='center', va='center', fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    save('correlation_heatmap', corr_draw)
    return {name: f'/static/eda/{name}.png' for name in ['daily_sales', 'monthly_demand', 'weekly_demand',
        'category_sales', 'top_products', 'stock_distribution', 'demand_distribution', 'supplier_fulfillment', 'slow_moving_stock',
        'payment_mix', 'stock_vs_demand', 'correlation_heatmap']}


# 7. INTELLIGENT ALERTS
def alert_rows():
    recs = get_recommendations(DB, limit=500)
    out = []
    for r in recs:
        if r['risk'] == 'HIGH':
            out.append({'level': 'critical', 'title': f"Stockout risk: {r['product']}", 'detail': f"{r['stock']} units • recommended order {r['recommended_order']}"})
        elif r['risk'] == 'MEDIUM':
            out.append({'level': 'warning', 'title': f"Low cover: {r['product']}", 'detail': f"{r['days_left']} days of estimated stock cover"})
    c = db()
    late = c.execute("SELECT COUNT(*) n FROM purchase_orders WHERE status IN ('ordered','processing')").fetchone()['n']
    c.close()
    if late:
        out.append({'level': 'warning', 'title': f'{late} purchase orders need attention', 'detail': 'Review open supplier deliveries.'})
    return out[:12]

@app.context_processor
def inject():
    return {'now': datetime.now(), 'user': current_user(), 'global_stats': stats() if DB.exists() else {}}
# 8. AUTHENTICATION PAGES

@app.route('/login', methods=['GET', 'POST'])


def login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        c = db()
        row = c.execute('SELECT username,name,role,password FROM users WHERE lower(username)=lower(?)',
            (u,)).fetchone()
        c.close()
        if row and verify_password(p, row['password']):
            if not str(row['password']).startswith('pbkdf2$'):
                c2 = db()
                c2.execute('UPDATE users SET password=? WHERE username=?', (hash_password(p),
                    row['username']))
                c2.commit()
                c2.close()
            session['user'] = {'username': row['username'], 'name': row['name'], 'role': row['role']}
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Login failed. Check the username and password. Usernames are not case-sensitive; passwords are case-sensitive.',
            'error')
    return render_template('login.html', title='Sign in')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
# 9. DASHBOARD

@app.route('/')
@login_required


def dashboard():
    c = db()
    s = stats()
    recs = get_recommendations(DB, limit=8)
    recent = c.execute((
                           'SELECT so.id,so.order_date,so.status,so.total_amount,COUNT(si.id) lines FROM '
                           'sales_orders so LEFT JOIN sales_items si ON si.order_id=so.id GROUP BY so.id '
                           'ORDER BY so.rowid DESC LIMIT 7'
                       )).fetchall()
    top = c.execute((
                        'SELECT p.name,SUM(si.quantity) qty FROM sales_items si JOIN variants v ON '
                        'v.id=si.variant_id JOIN products p ON p.id=v.product_id GROUP BY p.id ORDER BY '
                        'qty DESC LIMIT 6'
                    )).fetchall()
    c.close()
    return render_template('dashboard.html', title='Dashboard', stats=s, recs=recs, recent=recent, top=top,
        alerts=alert_rows())
# 10. WAREHOUSE & INVENTORY

@app.route('/warehouse')
@login_required


def warehouse():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    page = max(1, int(request.args.get('page', 1) or 1))
    per_page = 50
    c = db()
    base = (
               'FROM variants v JOIN products p ON p.id=v.product_id JOIN inventory i ON '
               'i.variant_id=v.id LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN categories cat '
               'ON cat.id=p.category_id WHERE 1=1'
           )
    args = []
    if q:
        base += ' AND (p.name LIKE ? OR p.sku LIKE ? OR v.sku_variant LIKE ? OR b.name LIKE ?)'
        args += [f'%{q}%'] * 4
    if category:
        base += ' AND cat.id=?'
        args.append(category)
    stock_filter = request.args.get('stock', '').strip().lower()
    if stock_filter == 'low':
        base += ' AND i.quantity<=i.low_stock_threshold AND i.quantity>0'
    elif stock_filter == 'out':
        base += ' AND i.quantity<=0'
    elif stock_filter == 'healthy':
        base += ' AND i.quantity>i.low_stock_threshold'
    brand_filter = request.args.get('brand', '').strip()
    if brand_filter:
        base += ' AND b.id=?'
        args.append(brand_filter)
    color_filter = request.args.get('color', '').strip()
    if color_filter:
        base += ' AND lower(COALESCE(v.color,))=lower(?)'
        args.append(color_filter)
    total = c.execute('SELECT COUNT(*) ' + base, args).fetchone()[0]
    sql = (
              'SELECT v.id variant_id,p.id '
              'product_id,p.name,p.sku,v.ram,v.storage,v.color,v.sku_variant,v.price_modifier,p.b'
              'ase_price,i.quantity,i.low_stock_threshold,b.name brand,cat.name category '
          ) + base + ' ORDER BY i.quantity ASC LIMIT ? OFFSET ?'
    rows = c.execute(sql, args + [per_page, (page - 1) * per_page]).fetchall()
    cats = c.execute('''SELECT cat.id,cat.name,COUNT(DISTINCT p.id) product_count,COUNT(DISTINCT v.id) variant_count
                      FROM categories cat JOIN products p ON p.category_id=cat.id JOIN variants v ON v.product_id=p.id
                      GROUP BY cat.id ORDER BY cat.name''').fetchall()
    brands = c.execute('SELECT id,name FROM brands ORDER BY name').fetchall()
    colors = [r[0] for r in c.execute("SELECT DISTINCT color FROM variants WHERE color IS NOT NULL AND trim(color)<>'' ORDER BY color").fetchall()]
    c.close()
    pages = max(1, math.ceil(total / per_page))
    return render_template('warehouse.html', title='Warehouse', rows=rows, categories=cats, brands=brands,
        colors=colors, q=q, category=category, stock_filter=stock_filter, brand_filter=brand_filter, color_filter=color_filter,
        page=page, pages=pages, total=total)
# 11. SALES / POINT OF SALE

@app.route('/orders')
@login_required


def orders():
    c = db()
    rows = c.execute((
                         'SELECT '
                         'si.id,si.order_id,si.variant_id,si.quantity,si.unit_price,so.order_date,so.status,'
                         'p.name,v.color,v.storage FROM sales_items si JOIN sales_orders so ON '
                         'so.id=si.order_id JOIN variants v ON v.id=si.variant_id JOIN products p ON '
                         'p.id=v.product_id ORDER BY so.rowid DESC LIMIT 250'
                     )).fetchall()
    variants = c.execute((
                             'SELECT '
                             'v.id,p.name,v.color,v.storage,v.ram,i.quantity,v.price_modifier,p.base_price FROM '
                             'variants v JOIN products p ON p.id=v.product_id JOIN inventory i ON '
                             'i.variant_id=v.id ORDER BY p.name'
                         )).fetchall()
    c.close()
    return render_template('orders.html', title='Orders', rows=rows, variants=variants)

@app.post('/orders/sale')
@login_required
@role_required('Admin', 'Manager', 'Staff')
def add_sale():
    variant = request.form['variant_id']
    qty = max(1, int(request.form['quantity']))
    payment = request.form.get('payment_method', 'upi')
    try:
        discount_pct = float(request.form.get('discount_pct', 0) or 0)
    except ValueError:
        discount_pct = 0
    if discount_pct < 0 or discount_pct > 50:
        flash('Discount must be between 0% and 50%.', 'error')
        return redirect(url_for('orders'))
    c = db()
    row = c.execute((
                        'SELECT i.quantity,p.base_price,v.price_modifier,p.name FROM inventory i JOIN '
                        'variants v ON v.id=i.variant_id JOIN products p ON p.id=v.product_id WHERE v.id=?'
                    ),
        (variant,)).fetchone()
    if not row:
        flash('Variant not found.', 'error')
        c.close()
        return redirect(url_for('orders'))
    if row['quantity'] < qty:
        flash(f"Not enough stock. Available: {row['quantity']}", 'error')
        c.close()
        return redirect(url_for('orders'))
    price = float(row['base_price'] + row['price_modifier'])
    gross = price * qty
    discount_amount = round(gross * discount_pct / 100, 2)
    total = round(gross - discount_amount, 2)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stamp = datetime.now().strftime('%y%m%d%H%M%S%f')
    oid = 'SO' + stamp[-10:]
    iid = 'SOI' + stamp[-12:]
    cid = 'CHK' + stamp[-12:]
    c.execute('INSERT INTO sales_orders VALUES (?,?,?,?,?,?)', (oid, None, 1001, 'completed', total, now))
    c.execute('INSERT INTO sales_items VALUES (?,?,?,?,?)', (iid, oid, variant, qty, price))
    c.execute('INSERT INTO checkouts VALUES (?,?,?,?,?,?,?,?)', (cid, iid, 1001, payment, total, 'percentage' if discount_pct else 'none',
        discount_amount, now))
    c.execute('UPDATE inventory SET quantity=quantity-? WHERE variant_id=?', (qty, variant))
    c.execute('INSERT INTO inventory_events(variant_id,event_type,quantity_delta,reason,created_at,created_by) VALUES (?,?,?,?,?,?)',
        (variant, 'SALE', -qty, 'POS sale', now, current_user()['username']))
    c.commit()
    c.close()
    flash(f"Sale recorded: {qty} × {row['name']}. Final bill ₹{total:,.2f} after {discount_pct:g}% discount. Inventory updated.",
        'success')
    return redirect(url_for('orders'))

@app.route('/products/add', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def add_product():
    c = db()
    pid = 'PRDNEW' + datetime.now().strftime('%y%m%d%H%M%S%f')
    vid = 'VARNEW' + datetime.now().strftime('%y%m%d%H%M%S%f')
    iid = 'INVNEW' + datetime.now().strftime('%y%m%d%H%M%S%f')
    name = request.form['name'].strip()
    sku = request.form['sku'].strip()
    price = float(request.form['price'])
    qty = int(request.form.get('quantity', 0))
    threshold = int(request.form.get('threshold', 5))
    cat = request.form.get('category') or None
    brand = request.form.get('brand') or None
    c.execute('INSERT INTO products VALUES (?,?,?,?,?,?,?)', (pid, brand, cat, name, sku, request.form.get('description',
        ''), price))
    c.execute('INSERT INTO variants VALUES (?,?,?,?,?,?,?)', (vid, pid, request.form.get('ram', ''), request.form.get('storage',
        ''), request.form.get('color', ''), sku, 0))
    c.execute('INSERT INTO inventory VALUES (?,?,?,?,?)', (iid, vid, qty, threshold, request.form.get('expiry_date',
        '')))
    c.commit()
    c.close()
    flash(f'{name} added to warehouse.', 'success')
    return redirect(url_for('warehouse'))

@app.post('/inventory/adjust')
@login_required
@role_required('Admin', 'Manager', 'Staff')
def inventory_adjust():
    variant = request.form['variant_id']
    delta = int(request.form['delta'])
    reason = request.form.get('reason', 'manual adjustment')
    c = db()
    row = c.execute('SELECT quantity FROM inventory WHERE variant_id=?', (variant,)).fetchone()
    if not row:
        c.close()
        flash('Inventory item not found.', 'error')
        return redirect(url_for('warehouse'))
    new = row['quantity'] + delta
    if new < 0:
        c.close()
        flash('Adjustment would make stock negative.', 'error')
        return redirect(url_for('warehouse'))
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    et = 'RETURN' if delta > 0 and 'return' in reason.lower() else 'DAMAGE' if delta < 0 and 'damage' in reason.lower() else 'ADJUSTMENT'
    c.execute('UPDATE inventory SET quantity=? WHERE variant_id=?', (new, variant))
    c.execute('INSERT INTO inventory_events(variant_id,event_type,quantity_delta,reason,created_at,created_by) VALUES (?,?,?,?,?,?)',
        (variant, et, delta, reason, now, current_user()['username']))
    c.commit()
    c.close()
    flash(f'Inventory changed by {delta:+d}.', 'success')
    return redirect(url_for('warehouse'))
# 12. PURCHASES & SUPPLIERS

@app.route('/purchases')
@login_required


def purchases():
    c = db()
    rows = c.execute((
                         'SELECT po.*,s.name supplier,SUM(pi.quantity_ordered) '
                         'ordered_qty,SUM(pi.quantity_received) received_qty FROM purchase_orders po JOIN '
                         'suppliers s ON s.id=po.supplier_id LEFT JOIN purchase_items pi ON '
                         'pi.order_id=po.id GROUP BY po.id ORDER BY po.rowid DESC'
                     )).fetchall()
    c.close()
    return render_template('purchases.html', title='Purchases', rows=rows)

@app.post('/purchases/receive/<po_id>')
@login_required
@role_required('Admin', 'Manager')
def receive_purchase(po_id):
    c = db()
    items = c.execute('SELECT variant_id,quantity_ordered,quantity_received FROM purchase_items WHERE order_id=?',
        (po_id,)).fetchall()
    added = 0
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for x in items:
        remaining = max(0, int(x['quantity_ordered']) - int(x['quantity_received'] or 0))
        if remaining:
            c.execute('UPDATE inventory SET quantity=quantity+? WHERE variant_id=?', (remaining, x['variant_id']))
            c.execute('UPDATE purchase_items SET quantity_received=quantity_ordered WHERE order_id=? AND variant_id=?',
                (po_id, x['variant_id']))
            c.execute('INSERT INTO inventory_events(variant_id,event_type,quantity_delta,reason,created_at,created_by) VALUES (?,?,?,?,?,?)',
                (x['variant_id'], 'RECEIPT', remaining, f'Purchase {po_id}', now, current_user()['username']))
            added += remaining
    c.execute("UPDATE purchase_orders SET status='received',received_date=? WHERE id=?", (now, po_id))
    c.commit()
    c.close()
    flash(f'{po_id} received. Inventory increased by {added} units.', 'success')
    return redirect(url_for('purchases'))

@app.route('/suppliers')
@login_required
def suppliers():
    c = db()
    rows = c.execute((
                         'SELECT s.*,COUNT(DISTINCT po.id) orders,COALESCE(SUM(pi.quantity_ordered),0) '
                         'ordered,COALESCE(SUM(pi.quantity_received),0) received,ROUND(CASE WHEN '
                         'SUM(pi.quantity_ordered)>0 THEN '
                         '100.0*SUM(pi.quantity_received)/SUM(pi.quantity_ordered) ELSE 0 END,1) '
                         'fulfillment FROM suppliers s LEFT JOIN purchase_orders po ON po.supplier_id=s.id '
                         'LEFT JOIN purchase_items pi ON pi.order_id=po.id GROUP BY s.id ORDER BY '
                         'fulfillment DESC'
                     )).fetchall()
    c.close()
    return render_template('suppliers.html', title='Supplier Intelligence', rows=rows)

@app.post('/suppliers/add')
@login_required
@role_required('Admin', 'Manager')
def add_supplier():
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()
    if not name:
        flash('Supplier name is required.', 'error')
        return redirect(url_for('suppliers'))
    sid = 'SUPNEW' + datetime.now().strftime('%y%m%d%H%M%S%f')
    c = db()
    c.execute('INSERT INTO suppliers(id,name,contact_name,phone,email,address) VALUES (?,?,?,?,?,?)', (sid,
        name, contact, phone, email, address))
    c.commit()
    c.close()
    flash(f'Supplier {name} added.', 'success')
    return redirect(url_for('suppliers'))
# 13. ANALYTICS & EDA PAGE

@app.route('/analytics')
@login_required


def analytics():
    c = db()
    sales = pd.read_sql_query('''SELECT so.order_date,so.status,si.variant_id,si.quantity,si.unit_price,
                                      p.id product_id,p.name product,p.base_price,v.color,v.storage,v.ram,
                                      COALESCE(cat.name,'Uncategorised') category
                               FROM sales_orders so JOIN sales_items si ON si.order_id=so.id
                               JOIN variants v ON v.id=si.variant_id JOIN products p ON p.id=v.product_id
                               LEFT JOIN categories cat ON cat.id=p.category_id
                               WHERE so.status NOT IN ('cancelled','failed')''',
        c)
    inv = pd.read_sql_query('''SELECT i.variant_id,i.quantity,i.low_stock_threshold,p.name product,p.base_price,
                                    COALESCE(cat.name,'Uncategorised') category,v.color
                             FROM inventory i JOIN variants v ON v.id=i.variant_id JOIN products p ON p.id=v.product_id
                             LEFT JOIN categories cat ON cat.id=p.category_id''',
        c)
    suppliers = pd.read_sql_query('''SELECT s.name supplier,COUNT(DISTINCT po.id) orders,
                                  COALESCE(SUM(pi.quantity_ordered),0) ordered,COALESCE(SUM(pi.quantity_received),0) received
                                  FROM suppliers s LEFT JOIN purchase_orders po ON po.supplier_id=s.id
                                  LEFT JOIN purchase_items pi ON pi.order_id=po.id GROUP BY s.id''',
        c)
    methods = pd.read_sql_query('SELECT payment_method,COUNT(*) transactions,SUM(amount_paid) value FROM checkouts GROUP BY payment_method ORDER BY transactions DESC',
        c)
    c.close()
    if not sales.empty:
        sales['dt'] = pd.to_datetime(sales['order_date'], dayfirst=True, errors='coerce')
        sales = sales.dropna(subset=['dt'])
        sales['day'] = sales['dt'].dt.normalize()
        sales['month'] = sales['dt'].dt.to_period('M').astype(str)
        sales['week'] = sales['dt'].dt.to_period('W').apply(lambda x: str(x.start_time.date()))
    if not sales.empty:
        sales['line_revenue'] = sales['quantity'] * sales['unit_price']
        daily = sales.groupby('day', as_index=False).agg(units=('quantity', 'sum'), revenue=('line_revenue',
            'sum')).sort_values('day')
    else:
        daily = pd.DataFrame()
    monthly = sales.groupby('month', as_index=False).agg(units=('quantity', 'sum')) if not sales.empty else pd.DataFrame()
    weekly = sales.groupby('week', as_index=False).agg(units=('quantity', 'sum')) if not sales.empty else pd.DataFrame()
    cat_sales = sales.groupby('category', as_index=False).agg(units=('quantity', 'sum')).sort_values('units',
        ascending=False) if not sales.empty else pd.DataFrame()
    if not sales.empty:
        top_products = sales.groupby('product', as_index=False).agg(units=('quantity', 'sum'), revenue=('line_revenue',
            'sum')).sort_values('units', ascending=False).head(10)
    else:
        top_products = pd.DataFrame()
    demand = sales.groupby('variant_id', as_index=False).quantity.sum().rename(columns={'quantity': 'sold'}) if not sales.empty else pd.DataFrame(columns=['variant_id',
        'sold'])
    stock_dist = inv['quantity'].tolist() if not inv.empty else []
    demand_dist = demand['sold'].tolist() if not demand.empty else []
    stock_by_cat = inv.groupby('category', as_index=False).quantity.sum().sort_values('quantity', ascending=False) if not inv.empty else pd.DataFrame()
    slow = inv.merge(demand, on='variant_id', how='left').fillna({'sold': 0}).sort_values(['sold', 'quantity'],
        ascending=[True, False]).head(10) if not inv.empty else pd.DataFrame()
    if not suppliers.empty:
        suppliers['fulfillment'] = np.where(suppliers['ordered'] > 0, 100 * suppliers['received'] / suppliers['ordered'],
            0)
        suppliers = suppliers.sort_values('fulfillment', ascending=False)
    slow_stock = slow[slow['sold'] <= 2].sort_values('quantity', ascending=False).head(10) if not slow.empty else pd.DataFrame()
    scatter = []
    if not inv.empty and (not demand.empty):
        ss = inv.merge(demand, on='variant_id', how='left').fillna({'sold': 0}).sort_values('sold', ascending=False).head(150)
        scatter = [{'x': int(r.quantity), 'y': int(r.sold), 'label': r.product} for _, r in ss.iterrows()]
    if not inv.empty:
        corr_data = inv[['variant_id', 'quantity', 'low_stock_threshold', 'base_price']].rename(columns={'quantity': 'stock',
            'low_stock_threshold': 'threshold', 'base_price': 'price'})
        if not demand.empty:
            corr_data = corr_data.merge(demand, on='variant_id', how='left')
        else:
            corr_data['sold'] = 0
    else:
        corr_data = pd.DataFrame(columns=['variant_id', 'stock', 'threshold', 'price', 'sold'])
    corr = corr_data.corr(numeric_only=True).round(2).fillna(0).astype(float).to_dict() if not corr_data.empty else {}

    def series(df, x, y):
        return [{'label': str(a), 'value': float(b or 0)} for a, b in zip(df[x], df[y])] if not df.empty else []
    eda = {'daily': series(daily, 'day', 'units'), 'monthly': series(monthly, 'month', 'units'), 'weekly': series(weekly,
        'week', 'units'), 'category': series(cat_sales.head(10), 'category', 'units'), 'top_products': series(top_products,
        'product', 'units'), 'stock_hist': stock_dist, 'demand_hist': demand_dist, 'stock_category': series(stock_by_cat.head(10),
        'category', 'quantity'), 'suppliers': series(suppliers.head(10), 'supplier', 'fulfillment'), 'payments': series(methods,
        'payment_method', 'transactions'), 'slow_stock': series(slow_stock, 'product', 'quantity'), 'scatter': scatter,
        'corr': corr}
    kpis = {'sales_units': int(sales.quantity.sum()) if not sales.empty else 0, 'revenue': float((sales.quantity * sales.unit_price).sum()) if not sales.empty else 0,
        'avg_daily': round(float(daily.units.mean()), 2) if not daily.empty else 0, 'stock_units': int(inv.quantity.sum()) if not inv.empty else 0,
        'variants': int(len(inv)), 'active_days': int(len(daily))}
    charts = build_eda_charts(eda, corr)
    return render_template('analytics.html', title='Analytics & EDA', eda=eda, kpis=kpis, corr=corr, slow=slow.to_dict('records'),
        metrics=get_metrics(MODELS), charts=charts)
# 14. ML DECISION CENTER

@app.route('/decision-center')
@login_required


def decision_center():
    return render_template('decision.html', title='Decision Center', recs=get_recommendations(DB, limit=250),
        metrics=get_metrics(MODELS))

@app.route('/decision/<variant_id>')
@login_required
def decision_detail(variant_id):
    rec = next((x for x in get_recommendations(DB, limit=1000) if x['variant_id'] == variant_id), None)
    if not rec:
        flash('Decision record not found.', 'error')
        return redirect(url_for('decision_center'))
    c = db()
    suppliers = c.execute((
                              'SELECT s.id,s.name,ROUND(CASE WHEN SUM(pi.quantity_ordered)>0 THEN '
                              '100.0*SUM(pi.quantity_received)/SUM(pi.quantity_ordered) ELSE 0 END,1) '
                              'fulfillment\n        FROM suppliers s LEFT JOIN purchase_orders po ON '
                              'po.supplier_id=s.id LEFT JOIN purchase_items pi ON pi.order_id=po.id GROUP BY '
                              's.id ORDER BY fulfillment DESC,s.name LIMIT 8'
                          )).fetchall()
    c.close()
    return render_template('decision_detail.html', title='Decision Explanation', rec=rec, suppliers=suppliers)

@app.post('/decision/create-po/<variant_id>')
@login_required
@role_required('Admin', 'Manager')
def create_purchase_from_decision(variant_id):
    rec = next((x for x in get_recommendations(DB, limit=1000) if x['variant_id'] == variant_id), None)
    if not rec or rec['recommended_order'] <= 0:
        flash('No purchase order is required for this variant.', 'error')
        return redirect(url_for('decision_center'))
    supplier_id = request.form.get('supplier_id', '')
    c = db()
    if not supplier_id:
        row = c.execute((
                            'SELECT s.id FROM suppliers s LEFT JOIN purchase_orders po ON po.supplier_id=s.id '
                            'LEFT JOIN purchase_items pi ON pi.order_id=po.id GROUP BY s.id ORDER BY CASE WHEN '
                            'SUM(pi.quantity_ordered)>0 THEN '
                            '100.0*SUM(pi.quantity_received)/SUM(pi.quantity_ordered) ELSE 0 END DESC,s.name '
                            'LIMIT 1'
                        )).fetchone()
        supplier_id = row['id'] if row else None
    if not supplier_id:
        c.close()
        flash('No supplier is available.', 'error')
        return redirect(url_for('decision_detail', variant_id=variant_id))
    supplier = c.execute('SELECT id,name FROM suppliers WHERE id=?', (supplier_id,)).fetchone()
    if not supplier:
        c.close()
        flash('Supplier not found.', 'error')
        return redirect(url_for('decision_detail', variant_id=variant_id))
    stamp = datetime.now().strftime('%y%m%d%H%M%S%f')
    poid = 'PO' + stamp[-12:]
    itemid = 'POI' + stamp[-13:]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO purchase_orders(id,supplier_id,created_by,status,total_amount,order_date,received_date) VALUES (?,?,?,?,?,?,?)',
        (poid, supplier_id, 1001, 'ordered', 0, now, None))
    c.execute('INSERT INTO purchase_items(id,order_id,variant_id,quantity_ordered,quantity_received,unit_cost) VALUES (?,?,?,?,?,?)',
        (itemid, poid, variant_id, rec['recommended_order'], 0, 0))
    c.commit()
    c.close()
    flash(f"Purchase order {poid} created for {rec['recommended_order']} units from {supplier['name']}.",
        'success')
    return redirect(url_for('purchases'))
# 15. NOTIFICATIONS / ALERTS

@app.route('/alerts')
@login_required


def alerts():
    kind = request.args.get('type', 'all').lower()
    all_alerts = alert_rows()
    if kind == 'low':
        alerts = [a for a in all_alerts if 'stockout' in a['title'].lower() or 'low cover' in a['title'].lower()]
        heading = 'Low-stock alerts'
        description = 'Products that need replenishment attention based on current stock and forecast cover.'
    elif kind == 'slow':
        c = db()
        rows = c.execute((
                             'SELECT p.name product,v.id variant_id,v.ram,v.storage,v.color,i.quantity '
                             'stock,COALESCE(SUM(si.quantity),0) sold FROM inventory i JOIN variants v ON '
                             'v.id=i.variant_id JOIN products p ON p.id=v.product_id LEFT JOIN sales_items si '
                             'ON si.variant_id=v.id WHERE i.quantity>0 GROUP BY i.variant_id HAVING sold<=2 '
                             'ORDER BY i.quantity DESC LIMIT 100'
                         )).fetchall()
        c.close()
        alerts = [{'level': 'warning', 'title': f"Slow-moving stock: {r['product']}", 'detail': f"{r['ram'] or ''} / {r['storage'] or ''} / {r['color'] or ''} • {r['stock']} units in stock • {r['sold']} historical units sold",
            'url': url_for('decision_detail', variant_id=r['variant_id'])} for r in rows]
        heading = 'Slow-moving stock'
        description = 'Technical-product variants with current stock but very low recorded historical sales. Review demand, age and model lifecycle before replenishing.'
    else:
        alerts = all_alerts
        heading = 'All notifications'
        description = 'Alerts generated from stock levels, forecast risk and purchasing signals.'
    return render_template('alerts.html', title='Notifications', alerts=alerts, heading=heading, description=description,
        kind=kind)
# 16. EMPLOYEE / ROLE MANAGEMENT

@app.route('/employees')
@login_required
@role_required('Admin')


def employees():
    c = db()
    rows = c.execute("SELECT username,name,role FROM users ORDER BY CASE role WHEN 'Admin' THEN 1 WHEN 'Manager' THEN 2 ELSE 3 END,name").fetchall()
    c.close()
    return render_template('employees.html', title='Employees & Roles', rows=rows)

@app.post('/employees/add')
@login_required
@role_required('Admin')
def add_employee():
    username = request.form.get('username', '').strip().lower()
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'Staff').strip().title()
    password = request.form.get('password', '')
    if not re.fullmatch('[a-z0-9._-]{3,30}', username):
        flash('Username must be 3–30 characters using letters, numbers, dot, underscore or hyphen.', 'error')
        return redirect(url_for('employees'))
    if role not in {'Admin', 'Manager', 'Staff'}:
        flash('Invalid role selected.', 'error')
        return redirect(url_for('employees'))
    if len(password) < 6:
        flash('Password must contain at least 6 characters.', 'error')
        return redirect(url_for('employees'))
    if not name:
        flash('Employee name is required.', 'error')
        return redirect(url_for('employees'))
    c = db()
    try:
        c.execute('INSERT INTO users(username,name,role,password) VALUES (?,?,?,?)', (username, name,
            role, hash_password(password)))
        c.commit()
        flash(f'Account {username} created as {role}.', 'success')
    except sqlite3.IntegrityError:
        flash(f'Username {username} already exists.', 'error')
    finally:
        c.close()
    return redirect(url_for('employees'))

@app.post('/employees/delete/<username>')
@login_required
@role_required('Admin')
def delete_employee(username):
    if username == current_user()['username']:
        flash('You cannot delete the account you are currently using.', 'error')
        return redirect(url_for('employees'))
    c = db()
    c.execute('DELETE FROM users WHERE username=?', (username,))
    c.commit()
    c.close()
    flash(f'Account {username} deleted.', 'success')
    return redirect(url_for('employees'))
# 17. RATES & TABLE MANAGEMENT

@app.route('/rates')
@login_required


def rates():
    c = db()
    rows = c.execute((
                         'SELECT p.id,p.name,p.sku,b.name brand,p.base_price,COUNT(v.id) variants FROM '
                         'products p LEFT JOIN brands b ON b.id=p.brand_id LEFT JOIN variants v ON '
                         'v.product_id=p.id GROUP BY p.id ORDER BY p.name LIMIT 250'
                     )).fetchall()
    c.close()
    return render_template('rates.html', title='Rates Management', rows=rows)

@app.post('/rates/update')
@login_required
@role_required('Admin', 'Manager')
def update_rate():
    pid = request.form['product_id']
    price = float(request.form['price'])
    c = db()
    c.execute('UPDATE products SET base_price=? WHERE id=?', (price, pid))
    c.commit()
    c.close()
    flash('Base price updated.', 'success')
    return redirect(url_for('rates'))

@app.route('/tables')
@login_required
def tables():
    c = db()
    cats = c.execute((
                         'SELECT cat.id,cat.name,COUNT(p.id) products FROM categories cat LEFT JOIN '
                         'products p ON p.category_id=cat.id GROUP BY cat.id ORDER BY products DESC'
                     )).fetchall()
    locs = c.execute('SELECT * FROM locations').fetchall()
    c.close()
    return render_template('tables.html', title='Tables Management', cats=cats, locs=locs)
# 18. MULTI-STORE STOCK TRANSFERS

@app.route('/transfers')
@login_required


def transfers():
    c = db()
    locs = c.execute('SELECT * FROM locations').fetchall()
    rows = c.execute((
                         'SELECT t.*,v.sku_variant,p.name,fl.name from_name,tl.name to_name FROM transfers '
                         't JOIN variants v ON v.id=t.variant_id JOIN products p ON p.id=v.product_id JOIN '
                         'locations fl ON fl.id=t.from_location JOIN locations tl ON tl.id=t.to_location '
                         'ORDER BY t.rowid DESC LIMIT 100'
                     )).fetchall()
    variants = c.execute('SELECT v.id,p.name,v.color,v.storage FROM variants v JOIN products p ON p.id=v.product_id ORDER BY p.name LIMIT 500').fetchall()
    c.close()
    return render_template('transfers.html', title='Stock Transfers', locs=locs, rows=rows, variants=variants)

@app.post('/transfers/add')
@login_required
@role_required('Admin', 'Manager')
def add_transfer():
    fr = request.form['from_location']
    to = request.form['to_location']
    vid = request.form['variant_id']
    qty = int(request.form['quantity'])
    c = db()
    if fr == to:
        flash('Choose different locations.', 'error')
        c.close()
        return redirect(url_for('transfers'))
    row = c.execute('SELECT quantity FROM location_inventory WHERE location_id=? AND variant_id=?', (fr, vid)).fetchone()
    available = int(row['quantity']) if row else 0
    if available < qty:
        flash(f'Only {available} units are available at the source location.', 'error')
        c.close()
        return redirect(url_for('transfers'))
    stamp = datetime.now().strftime('%y%m%d%H%M%S%f')
    tid = 'TR' + stamp[-12:]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('UPDATE location_inventory SET quantity=quantity-? WHERE location_id=? AND variant_id=?', (qty,
        fr, vid))
    c.execute('INSERT OR IGNORE INTO location_inventory VALUES (?,?,0)', (to, vid))
    c.execute('UPDATE location_inventory SET quantity=quantity+? WHERE location_id=? AND variant_id=?', (qty,
        to, vid))
    c.execute('INSERT INTO transfers VALUES (?,?,?,?,?,?,?,?)', (tid, fr, to, vid, qty, 'completed', now,
        current_user()['username']))
    c.commit()
    c.close()
    flash(f'Transfer {tid} completed.', 'success')
    return redirect(url_for('transfers'))


# 19. INVENTORY ASSISTANT
def _assistant_table(title, rows, columns):
    return {'title': title, 'rows': [dict(r) if hasattr(r, 'keys') else r for r in rows], 'columns': columns}

def _assistant_help():
    groups = {'Stock & inventory': ['Which products are low stock?', 'Which products are out of stock?', 'What is my total stock?',
        'What is the average stock per variant?', 'Which products are overstocked?', 'Which products are slow moving?',
        'What is the stock by category?', 'What is the stock value?', 'Which products have the highest stock?', 'Which products have the lowest stock?'],
        'Sales & demand': ['What are the top selling products?', 'What are the bottom selling products?', 'Which products generate the most revenue?',
        'What is total sales quantity?', 'What is total sales revenue?', 'What is the average daily sales?', 'What were sales by month?',
        'What were sales by week?', 'What is the best selling category?', 'Which category has the most stock?'], 'Replenishment & risk': ['What should I reorder?',
        'Which products have high stockout risk?', 'Which products have medium risk?', 'Which products have low risk?',
        'What is the 7 day forecast?', 'Which products need the biggest orders?', 'Which products have incoming stock?',
        'Which products have less than 7 days cover?', 'Which products have less than 14 days cover?', 'What is the reorder formula?'],
        'Product lifecycle & anomalies': ['Which products are slow moving?', 'Which variants have stock but very few sales?',
        'Which products have the highest stock?', 'Which variants have unusual demand?', 'Show abnormal inventory behavior.',
        'Show sales anomalies.', 'What does anomaly detection do?', 'Which products should we review before reordering?'],
        'Suppliers & operations': ['Who is the best supplier?', 'Who is the worst supplier?', 'Show supplier fulfillment.',
        'Which purchase orders are open?', 'How much stock is incoming?', 'Which suppliers have the most orders?',
        'Which supplier has the most received units?', 'Show payment methods.', 'What locations exist?', 'How is stock distributed by location?'],
        'System & catalog': ['How many products are there?', 'How many variants are there?', 'How many categories are there?',
        'How many suppliers are there?', 'How many customers are there?', 'How many sales lines are there?', 'What model is used?',
        'What is the model R2?', 'When should I retrain the model?', 'What is the decision engine doing?']}
    return groups

def assistant_query(query):
    q = re.sub('[^a-z0-9? ]+', ' ', query.lower()).strip()
    c = db()
    try:
        if 'low stock' in q or 'stock low' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity stock,i.low_stock_threshold '
                                 'threshold FROM inventory i JOIN variants v ON v.id=i.variant_id JOIN products p '
                                 'ON p.id=v.product_id WHERE i.quantity<=i.low_stock_threshold ORDER BY i.quantity '
                                 'LIMIT 12'
                             )).fetchall()
            return _assistant_table('Low-stock products', rows, ['product', 'variant', 'stock', 'threshold'])
        if 'out of stock' in q or 'zero stock' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity stock FROM inventory i JOIN '
                                 'variants v ON v.id=i.variant_id JOIN products p ON p.id=v.product_id WHERE '
                                 'i.quantity=0 ORDER BY p.name LIMIT 12'
                             )).fetchall()
            return _assistant_table('Out-of-stock products', rows, ['product', 'variant', 'stock'])
        if 'total stock' in q or 'stock units' in q:
            n = c.execute('SELECT COALESCE(SUM(quantity),0) n FROM inventory').fetchone()['n']
            return {'title': 'Total stock', 'text': f'{n:,} sellable units are currently recorded across the catalog.'}
        if 'average stock' in q:
            n = c.execute('SELECT ROUND(AVG(quantity),2) n FROM inventory').fetchone()['n']
            return {'title': 'Average stock per variant', 'text': f'The average current stock is {n or 0} units per variant.'}
        if 'overstock' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity '
                                 'stock,COALESCE(SUM(si.quantity),0) sold FROM inventory i JOIN variants v ON '
                                 'v.id=i.variant_id JOIN products p ON p.id=v.product_id LEFT JOIN sales_items si '
                                 'ON si.variant_id=v.id GROUP BY v.id ORDER BY stock DESC,sold ASC LIMIT 12'
                             )).fetchall()
            return _assistant_table('Potential overstock / dead stock', rows, ['product', 'variant',
                'stock', 'sold'])
        if 'slow moving' in q or 'slow-moving' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,COALESCE(SUM(si.quantity),0) '
                                 'sold,i.quantity stock FROM inventory i JOIN variants v ON v.id=i.variant_id JOIN '
                                 'products p ON p.id=v.product_id LEFT JOIN sales_items si ON si.variant_id=v.id '
                                 'GROUP BY v.id ORDER BY sold ASC,stock DESC LIMIT 12'
                             )).fetchall()
            return _assistant_table('Slow-moving products', rows, ['product', 'variant', 'sold', 'stock'])
        if 'stock by category' in q or 'category stock' in q:
            rows = c.execute((
                                 "SELECT COALESCE(cat.name,'Uncategorised') category,SUM(i.quantity) stock FROM "
                                 'inventory i JOIN variants v ON v.id=i.variant_id JOIN products p ON '
                                 'p.id=v.product_id LEFT JOIN categories cat ON cat.id=p.category_id GROUP BY '
                                 'category ORDER BY stock DESC'
                             )).fetchall()
            return _assistant_table('Stock by category', rows, ['category', 'stock'])
        if 'stock value' in q:
            n = c.execute((
                              'SELECT COALESCE(SUM(i.quantity*(p.base_price+v.price_modifier)),0) value FROM '
                              'inventory i JOIN variants v ON v.id=i.variant_id JOIN products p ON '
                              'p.id=v.product_id'
                          )).fetchone()['value']
            return {'title': 'Current inventory value', 'text': f'Estimated catalog value at listed prices: ₹{n:,.0f}.'}
        if 'highest stock' in q or 'most stock' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity stock FROM inventory i JOIN '
                                 'variants v ON v.id=i.variant_id JOIN products p ON p.id=v.product_id ORDER BY '
                                 'i.quantity DESC LIMIT 10'
                             )).fetchall()
            return _assistant_table('Highest-stock variants', rows, ['product', 'variant', 'stock'])
        if 'lowest stock' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity stock FROM inventory i JOIN '
                                 'variants v ON v.id=i.variant_id JOIN products p ON p.id=v.product_id ORDER BY '
                                 'i.quantity ASC LIMIT 10'
                             )).fetchall()
            return _assistant_table('Lowest-stock variants', rows, ['product', 'variant', 'stock'])
        if 'top selling' in q or 'best selling' in q or 'top products' in q:
            rows = c.execute((
                                 'SELECT p.name product,SUM(si.quantity) units FROM sales_items si JOIN variants v '
                                 'ON v.id=si.variant_id JOIN products p ON p.id=v.product_id GROUP BY p.id ORDER BY '
                                 'units DESC LIMIT 10'
                             )).fetchall()
            return _assistant_table('Top-selling products', rows, ['product', 'units'])
        if 'bottom selling' in q or 'worst selling' in q:
            rows = c.execute((
                                 'SELECT p.name product,COALESCE(SUM(si.quantity),0) units FROM products p JOIN '
                                 'variants v ON v.product_id=p.id LEFT JOIN sales_items si ON si.variant_id=v.id '
                                 'GROUP BY p.id ORDER BY units ASC,p.name LIMIT 10'
                             )).fetchall()
            return _assistant_table('Bottom-selling products', rows, ['product', 'units'])
        if 'most revenue' in q or 'highest revenue' in q:
            rows = c.execute((
                                 'SELECT p.name product,ROUND(SUM(si.quantity*si.unit_price),0) revenue FROM '
                                 'sales_items si JOIN variants v ON v.id=si.variant_id JOIN products p ON '
                                 'p.id=v.product_id GROUP BY p.id ORDER BY revenue DESC LIMIT 10'
                             )).fetchall()
            return _assistant_table('Highest-revenue products', rows, ['product', 'revenue'])
        if 'total sales quantity' in q or 'total sales units' in q:
            n = c.execute('SELECT COALESCE(SUM(quantity),0) n FROM sales_items').fetchone()['n']
            return {'title': 'Total historical sales units', 'text': f'{n:,} units have been recorded in sales line items.'}
        if 'total sales revenue' in q or 'sales revenue' in q:
            n = c.execute('SELECT COALESCE(SUM(quantity*unit_price),0) n FROM sales_items').fetchone()['n']
            return {'title': 'Historical sales revenue', 'text': f'Recorded line-item revenue is ₹{n:,.0f}.'}
        if 'average daily sales' in q:
            n = c.execute((
                              "SELECT AVG(units) FROM (SELECT CASE WHEN substr(so.order_date,3,1)='-' THEN "
                              "substr(so.order_date,7,4)||'-'||substr(so.order_date,4,2)||'-'||substr(so.order_da"
                              'te,1,2) ELSE substr(so.order_date,1,10) END d,SUM(si.quantity) units FROM '
                              'sales_orders so JOIN sales_items si ON si.order_id=so.id GROUP BY d)'
                          )).fetchone()[0] or 0
            return {'title': 'Average daily sales', 'text': f'The average recorded daily volume is about {n:.1f} units.'}
        if 'sales by month' in q or 'monthly sales' in q:
            rows = c.execute((
                                 'SELECT substr(d,1,7) month,SUM(units) units FROM (SELECT CASE WHEN '
                                 "substr(so.order_date,3,1)='-' THEN "
                                 "substr(so.order_date,7,4)||'-'||substr(so.order_date,4,2)||'-'||substr(so.order_da"
                                 'te,1,2) ELSE substr(so.order_date,1,10) END d,si.quantity units FROM sales_orders '
                                 'so JOIN sales_items si ON si.order_id=so.id) GROUP BY month ORDER BY month DESC '
                                 'LIMIT 12'
                             )).fetchall()
            return _assistant_table('Monthly sales', rows, ['month', 'units'])
        if 'sales by week' in q or 'weekly sales' in q:
            rows = c.execute((
                                 "SELECT strftime('%Y-W%W',date(d)) week,SUM(units) units FROM (SELECT CASE WHEN "
                                 "substr(so.order_date,3,1)='-' THEN "
                                 "substr(so.order_date,7,4)||'-'||substr(so.order_date,4,2)||'-'||substr(so.order_da"
                                 'te,1,2) ELSE substr(so.order_date,1,10) END d,si.quantity units FROM sales_orders '
                                 'so JOIN sales_items si ON si.order_id=so.id) GROUP BY week ORDER BY week DESC '
                                 'LIMIT 12'
                             )).fetchall()
            return _assistant_table('Recent sales periods', rows, ['week', 'units'])
        if 'best selling category' in q or 'category sales' in q:
            rows = c.execute((
                                 "SELECT COALESCE(cat.name,'Uncategorised') category,SUM(si.quantity) units FROM "
                                 'sales_items si JOIN variants v ON v.id=si.variant_id JOIN products p ON '
                                 'p.id=v.product_id LEFT JOIN categories cat ON cat.id=p.category_id GROUP BY '
                                 'category ORDER BY units DESC'
                             )).fetchall()
            return _assistant_table('Sales by category', rows, ['category', 'units'])
        if 'most stock category' in q:
            rows = c.execute((
                                 "SELECT COALESCE(cat.name,'Uncategorised') category,SUM(i.quantity) stock FROM "
                                 'inventory i JOIN variants v ON v.id=i.variant_id JOIN products p ON '
                                 'p.id=v.product_id LEFT JOIN categories cat ON cat.id=p.category_id GROUP BY '
                                 'category ORDER BY stock DESC'
                             )).fetchall()
            return _assistant_table('Stock by category', rows, ['category', 'stock'])
        if 'reorder formula' in q:
            return {'title': 'Decision engine formula', 'text': 'Suggested order = predicted demand + safety stock − current stock − incoming stock. Negative results are clipped to zero.'}
        if 'what should i reorder' in q or 'reorder' in q or 'purchase recommendation' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'forecast_7d': r['predicted_7d'],
                'incoming': r['incoming'], 'order': r['recommended_order']} for r in get_recommendations(DB, limit=20) if r['recommended_order'] > 0][:12]
            return _assistant_table('Priority reorder recommendations', rows, ['product', 'stock',
                'forecast_7d', 'incoming', 'order'])
        if 'high stockout' in q or 'high risk' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'days_cover': r['days_left'], 'order': r['recommended_order']} for r in get_recommendations(DB,
                limit=250) if r['risk'] == 'HIGH'][:12]
            return _assistant_table('High-risk variants', rows, ['product', 'stock', 'days_cover', 'order'])
        if 'medium risk' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'days_cover': r['days_left'], 'order': r['recommended_order']} for r in get_recommendations(DB,
                limit=250) if r['risk'] == 'MEDIUM'][:12]
            return _assistant_table('Medium-risk variants', rows, ['product', 'stock', 'days_cover',
                'order'])
        if 'low risk' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'days_cover': r['days_left'], 'order': r['recommended_order']} for r in get_recommendations(DB,
                limit=250) if r['risk'] == 'LOW'][:12]
            return _assistant_table('Low-risk variants', rows, ['product', 'stock', 'days_cover', 'order'])
        if '7 day forecast' in q or 'forecast' in q:
            rows = [{'product': r['product'], 'avg_daily': r['avg_daily'], 'forecast_7d': r['predicted_7d']} for r in get_recommendations(DB,
                limit=250) if r['predicted_7d'] > 0][:12]
            return _assistant_table('7-day demand forecast', rows, ['product', 'avg_daily', 'forecast_7d'])
        if 'biggest orders' in q or 'largest orders' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'order': r['recommended_order']} for r in sorted([x for x in get_recommendations(DB,
                limit=250) if x['recommended_order'] > 0], key=lambda x: x['recommended_order'], reverse=True)[:12]]
            return _assistant_table('Largest recommended replenishments', rows, ['product', 'stock',
                'order'])
        if 'incoming stock' in q or 'incoming' in q:
            rows = [{'product': r['product'], 'incoming': r['incoming'], 'stock': r['stock']} for r in get_recommendations(DB,
                limit=250) if r['incoming'] > 0][:12]
            return _assistant_table('Incoming stock', rows, ['product', 'incoming', 'stock'])
        if 'less than 7 days' in q or 'under 7 days' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'days_cover': r['days_left']} for r in get_recommendations(DB,
                limit=250) if r['days_left'] is not None and r['days_left'] < 7][:12]
            return _assistant_table('Variants with less than 7 days cover', rows, ['product', 'stock',
                'days_cover'])
        if 'less than 14 days' in q or 'under 14 days' in q:
            rows = [{'product': r['product'], 'stock': r['stock'], 'days_cover': r['days_left']} for r in get_recommendations(DB,
                limit=250) if r['days_left'] is not None and r['days_left'] < 14][:12]
            return _assistant_table('Variants with less than 14 days cover', rows, ['product', 'stock',
                'days_cover'])
        if 'reorder formula' in q:
            return {'title': 'Decision engine formula', 'text': 'Suggested order = predicted demand + safety stock − current stock − incoming stock. Negative results are clipped to zero.'}
        if 'stock but very few sales' in q or 'slow moving' in q or 'slow-moving' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,i.quantity '
                                 'stock,COALESCE(SUM(si.quantity),0) sold FROM inventory i JOIN variants v ON '
                                 'v.id=i.variant_id JOIN products p ON p.id=v.product_id LEFT JOIN sales_items si '
                                 'ON si.variant_id=v.id WHERE i.quantity>0 GROUP BY i.variant_id HAVING sold<=2 '
                                 'ORDER BY i.quantity DESC LIMIT 12'
                             )).fetchall()
            return _assistant_table('Slow-moving stock', rows, ['product', 'variant', 'stock', 'sold'])
        if 'what does anomaly' in q:
            return {'title': 'Isolation Forest anomaly detection', 'text': 'The application uses Isolation Forest to flag observations that are easier to isolate than normal observations. It is used as a practical abnormal-pattern detector, not as a diagnosis.'}
        if 'abnormal' in q or 'anomal' in q or 'unusual demand' in q:
            rows = c.execute((
                                 'SELECT p.name product,v.color variant,COALESCE(SUM(si.quantity),0) '
                                 'sold,i.quantity stock FROM inventory i JOIN variants v ON v.id=i.variant_id JOIN '
                                 'products p ON p.id=v.product_id LEFT JOIN sales_items si ON si.variant_id=v.id '
                                 'GROUP BY v.id ORDER BY sold DESC LIMIT 12'
                             )).fetchall()
            return _assistant_table('High-demand patterns for anomaly review', rows, ['product', 'variant',
                'sold', 'stock'])
        supplier_sql = (
                           'SELECT s.name supplier,COUNT(DISTINCT po.id) '
                           'orders,COALESCE(SUM(pi.quantity_ordered),0) '
                           'ordered,COALESCE(SUM(pi.quantity_received),0) received,ROUND(CASE WHEN '
                           'SUM(pi.quantity_ordered)>0 THEN '
                           '100.0*SUM(pi.quantity_received)/SUM(pi.quantity_ordered) ELSE 0 END,1) '
                           'fulfillment FROM suppliers s LEFT JOIN purchase_orders po ON po.supplier_id=s.id '
                           'LEFT JOIN purchase_items pi ON pi.order_id=po.id GROUP BY s.id'
                       )
        if 'best supplier' in q:
            rows = c.execute(supplier_sql + ' ORDER BY fulfillment DESC,received DESC LIMIT 10').fetchall()
            return _assistant_table('Best supplier by fulfillment', rows, ['supplier', 'orders', 'ordered',
                'received', 'fulfillment'])
        if 'worst supplier' in q:
            rows = c.execute(supplier_sql + ' ORDER BY fulfillment ASC,ordered DESC LIMIT 10').fetchall()
            return _assistant_table('Lowest supplier fulfillment', rows, ['supplier', 'orders', 'ordered',
                'received', 'fulfillment'])
        if 'supplier fulfillment' in q or 'show supplier' in q:
            rows = c.execute(supplier_sql + ' ORDER BY fulfillment DESC LIMIT 15').fetchall()
            return _assistant_table('Supplier fulfillment', rows, ['supplier', 'orders', 'ordered',
                'received', 'fulfillment'])
        if 'most orders' in q:
            rows = c.execute(supplier_sql + ' ORDER BY orders DESC LIMIT 10').fetchall()
            return _assistant_table('Suppliers with most purchase orders', rows, ['supplier', 'orders',
                'ordered', 'received', 'fulfillment'])
        if 'most received' in q or 'received units' in q:
            rows = c.execute(supplier_sql + ' ORDER BY received DESC LIMIT 10').fetchall()
            return _assistant_table('Suppliers with most received units', rows, ['supplier', 'orders',
                'ordered', 'received', 'fulfillment'])
        if 'open purchase' in q or 'pending purchase' in q:
            rows = c.execute((
                                 'SELECT po.id,s.name supplier,po.status,po.order_date FROM purchase_orders po JOIN '
                                 'suppliers s ON s.id=po.supplier_id WHERE po.status IN '
                                 "('ordered','processing','partially_received') ORDER BY po.rowid DESC LIMIT 15"
                             )).fetchall()
            return _assistant_table('Open purchase orders', rows, ['id', 'supplier', 'status', 'order_date'])
        if 'payment' in q:
            rows = c.execute((
                                 'SELECT payment_method,COUNT(*) transactions,ROUND(SUM(amount_paid),0) value FROM '
                                 'checkouts GROUP BY payment_method ORDER BY transactions DESC'
                             )).fetchall()
            return _assistant_table('Checkout / payment methods', rows, ['payment_method', 'transactions',
                'value'])
        if 'locations' in q or 'stores' in q:
            rows = c.execute((
                                 'SELECT l.name location,l.type,COALESCE(SUM(li.quantity),0) '
                                 'units,COUNT(li.variant_id) variants FROM locations l LEFT JOIN location_inventory '
                                 'li ON li.location_id=l.id GROUP BY l.id ORDER BY units DESC'
                             )).fetchall()
            return _assistant_table('Operational locations', rows, ['location', 'type', 'units', 'variants'])
        if 'how many products' in q:
            n = c.execute('SELECT COUNT(*) n FROM products').fetchone()['n']
            return {'title': 'Product count', 'text': f'{n:,} products are in the catalog.'}
        if 'how many variants' in q:
            n = c.execute('SELECT COUNT(*) n FROM variants').fetchone()['n']
            return {'title': 'Variant count', 'text': f'{n:,} sellable variants are in the catalog.'}
        if 'how many categories' in q:
            n = c.execute('SELECT COUNT(*) n FROM categories WHERE id IN (SELECT DISTINCT category_id FROM products)').fetchone()['n']
            return {'title': 'Active category count', 'text': f'{n:,} categories are currently represented by products in the supplied dataset.'}
        if 'how many suppliers' in q:
            n = c.execute('SELECT COUNT(*) n FROM suppliers').fetchone()['n']
            return {'title': 'Supplier count', 'text': f'{n:,} suppliers are recorded.'}
        if 'how many customers' in q:
            n = c.execute('SELECT COUNT(*) n FROM customers').fetchone()['n']
            return {'title': 'Customer count', 'text': f'{n:,} customers are recorded.'}
        if 'sales lines' in q:
            n = c.execute('SELECT COUNT(*) n FROM sales_items').fetchone()['n']
            return {'title': 'Sales line count', 'text': f'{n:,} sales line items are recorded.'}
        if 'what model' in q:
            return {'title': 'Current Data Science models', 'text': 'Random Forest regression is used for demand forecasting, and Isolation Forest is used for abnormal-pattern detection. The decision engine converts predictions into reorder actions.'}
        if 'model r2' in q or 'model r²' in q:
            m = get_metrics(MODELS)
            return {'title': 'Model evaluation', 'text': f"Hold-out R²: {m.get('R2', '—')}, MAE: {m.get('MAE',
                '—')}, RMSE: {m.get('RMSE', '—')}."}
        if 'retrain' in q:
            return {'title': 'When to retrain', 'text': 'Retrain after adding a meaningful amount of new transaction history or when demand patterns change. Admins and Managers can use the Retrain model action.'}
        if 'decision engine' in q:
            return {'title': 'Decision engine', 'text': 'It combines forecast demand, safety stock, current stock and incoming purchase quantities to recommend reorder quantities and flag stockout risk and slow-moving inventory.'}
        return {'title': 'I can answer 50+ inventory questions', 'text': 'Try one of the grouped questions below. The assistant is rule-based and runs SQL/data-science calculations against this application database.'}
    finally:
        c.close()

@app.route('/assistant', methods=['GET', 'POST'])
@login_required
def assistant():
    answer = None
    query = request.args.get('q', '').strip()
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
    if query:
        answer = assistant_query(query)
    return render_template('assistant.html', title='Inventory Assistant', answer=answer, query=query, question_groups=_assistant_help())
# 20. USER PROFILE

@app.route('/profile', methods=['GET', 'POST'])
@login_required


def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        new_password = request.form.get('new_password', '')
        if not name:
            flash('Name cannot be empty.', 'error')
            return redirect(url_for('profile'))
        c = db()
        if new_password:
            if len(new_password) < 6:
                c.close()
                flash('New password must contain at least 6 characters.', 'error')
                return redirect(url_for('profile'))
            c.execute('UPDATE users SET name=?,password=? WHERE username=?', (name, hash_password(new_password),
                current_user()['username']))
        else:
            c.execute('UPDATE users SET name=? WHERE username=?', (name, current_user()['username']))
        c.commit()
        c.close()
        session['user']['name'] = name
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))
    cu = current_user() or {}
    username = str(cu.get('username', '')).strip()
    c = db()
    row = c.execute('SELECT username,name,role FROM users WHERE lower(username)=lower(?)', (username,)).fetchone()
    c.close()
    if row is None:
        row = {'username': username, 'name': cu.get('name') or username, 'role': cu.get('role') or 'Staff'}
    return render_template('profile.html', title='My Profile', profile=row)
# 21. SYSTEM / MODEL MANAGEMENT

@app.route('/system')
@login_required
@role_required('Admin', 'Manager')


def system():
    return render_template('system.html', title='System Management', metrics=get_metrics(MODELS), stats=stats(),
        model_comparison=compare_models(DB, MODELS))

@app.post('/train')
@login_required
@role_required('Admin', 'Manager')
def retrain():
    metrics = train_and_save(DB, MODELS)
    flash('Demand model retrained using the current transaction history.', 'success')
    return redirect(request.referrer or url_for('decision_center'))
# 22. EXPORT / API

@app.route('/export/recommendations.csv')
@login_required


def export_recs():
    df = pd.DataFrame(get_recommendations(DB, limit=500))
    return Response(df.to_csv(index=False), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=inventory_recommendations.csv'})

@app.route('/api/recommendations')
@login_required
def api_recommendations():
    return jsonify(get_recommendations(DB, limit=250))


# 23. START APPLICATION
if __name__ == '__main__':
    seed()
    app.run(debug=True)
