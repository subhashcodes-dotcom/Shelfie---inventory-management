"""Generate the EDA image assets used by Shelfie Inventory."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BASE = Path(__file__).resolve().parent
DB = BASE / 'inventory.db'
OUT = BASE / 'static' / 'eda'
OUT.mkdir(parents=True, exist_ok=True)
c = sqlite3.connect(DB)
sales = pd.read_sql_query(
    """SELECT
        so.order_date,
        si.variant_id,
        si.quantity,
        si.unit_price,
        p.name AS product,
        COALESCE(cat.name, 'Uncategorised') AS category
    FROM sales_orders so
    JOIN sales_items si ON si.order_id = so.id
    JOIN variants v ON v.id = si.variant_id
    JOIN products p ON p.id = v.product_id
    LEFT JOIN categories cat ON cat.id = p.category_id
    WHERE so.status NOT IN ('cancelled', 'failed')""",
    c,
)
inv = pd.read_sql_query(
    """SELECT
        i.variant_id,
        i.quantity,
        i.low_stock_threshold,
        p.name AS product,
        p.base_price,
        COALESCE(cat.name, 'Uncategorised') AS category
    FROM inventory i
    JOIN variants v ON v.id = i.variant_id
    JOIN products p ON p.id = v.product_id
    LEFT JOIN categories cat ON cat.id = p.category_id""",
    c,
)
sup = pd.read_sql_query(
    """SELECT
        s.name AS supplier,
        COALESCE(SUM(pi.quantity_ordered), 0) AS ordered,
        COALESCE(SUM(pi.quantity_received), 0) AS received
    FROM suppliers s
    LEFT JOIN purchase_orders po ON po.supplier_id = s.id
    LEFT JOIN purchase_items pi ON pi.order_id = po.id
    GROUP BY s.id""",
    c,
)
pay = pd.read_sql_query(
    """SELECT payment_method, COUNT(*) AS transactions
    FROM checkouts
    GROUP BY payment_method
    ORDER BY transactions DESC""",
    c,
)
demand = pd.read_sql_query('SELECT variant_id,SUM(quantity) sold FROM sales_items GROUP BY variant_id', c)
c.close()
plt.rcParams.update({'figure.figsize': (9, 4.2), 'axes.titlesize': 12, 'axes.labelsize': 9})


# 1. REUSABLE CHART-SAVING FUNCTION
def save(name, title, draw):
    fig, ax = plt.subplots()
    draw(ax)
    ax.set_title(title)
    ax.grid(axis='y', alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / f'{name}.png', dpi=130, bbox_inches='tight')
    plt.close(fig)
sales['dt'] = pd.to_datetime(sales.order_date, dayfirst=True, errors='coerce')
sales = sales.dropna(subset=['dt'])


# 2. SALES TRENDS AND CATEGORY CHARTS
if not sales.empty:
    sales['day'] = sales.dt.dt.normalize()
    sales['month'] = sales.dt.dt.to_period('M').astype(str)
    sales['week'] = sales.dt.dt.to_period('W').apply(lambda x: str(x.start_time.date()))

    def line(name, title, group_col):
        values = sales.groupby(group_col).quantity.sum().sort_index()
        save(name, title, lambda ax: (ax.plot(range(len(values)), values.values, marker='o'), ax.set_xticks(range(0,
            len(values), max(1, len(values) // 12))), ax.set_xticklabels(values.index[::max(1, len(values) // 12)],
            rotation=35, ha='right'), ax.set_ylabel('Units sold')))
    line('daily_sales', 'Daily sales units', 'day')
    line('monthly_demand', 'Monthly demand', 'month')
    line('weekly_demand', 'Weekly demand', 'week')
    cat = sales.groupby('category').quantity.sum().sort_values(ascending=False).head(10)
    save('category_sales', 'Units sold by category', lambda ax: (ax.bar(cat.index.astype(str), cat.values),
        ax.tick_params(axis='x', rotation=35), ax.set_ylabel('Units sold')))
    top = sales.groupby('product').quantity.sum().sort_values(ascending=True).tail(10)
    save('top_products', 'Top 10 products by units', lambda ax: (ax.barh(top.index.astype(str), top.values),
        ax.set_xlabel('Units sold')))
stock = inv.quantity.tolist()
save('stock_distribution', 'Current stock distribution', lambda ax: (ax.hist(stock, bins=12, edgecolor='white'),
    ax.set_xlabel('Stock units'), ax.set_ylabel('Variants')))
sup['fulfillment'] = np.where(sup.ordered > 0, 100 * sup.received / sup.ordered, 0)
sup = sup.sort_values('fulfillment', ascending=False).head(10)
save('supplier_fulfillment', 'Supplier fulfillment', lambda ax: (ax.barh(sup.supplier.astype(str), sup.fulfillment),
    ax.set_xlabel('Fulfillment %')))
slow = inv.merge(demand, on='variant_id', how='left').fillna({'sold': 0})
slow = slow[(slow.quantity > 0) & (slow.sold <= 2)].sort_values('quantity', ascending=True).tail(10)
save('slow_moving_stock', 'Slow-moving stock variants', lambda ax: (ax.barh(slow.product.astype(str).str[:24],
    slow.quantity), ax.set_xlabel('Current stock')))
save('payment_mix', 'Checkout methods', lambda ax: (ax.bar(pay.payment_method.astype(str), pay.transactions),
    ax.tick_params(axis='x', rotation=30), ax.set_ylabel('Transactions')))
scatter = inv.merge(demand, on='variant_id', how='left').fillna({'sold': 0}).sort_values('sold', ascending=False).head(150)
save('stock_vs_demand', 'Current stock vs historical demand', lambda ax: (ax.scatter(scatter.quantity, scatter.sold,
    s=18, alpha=0.65), ax.set_xlabel('Current stock'), ax.set_ylabel('Historical units sold')))
frame = inv[['variant_id', 'quantity', 'low_stock_threshold', 'base_price']].rename(columns={'quantity': 'stock',
    'low_stock_threshold': 'threshold', 'base_price': 'price'}).merge(demand, on='variant_id', how='left').fillna({'sold': 0})
corr = frame[['stock', 'threshold', 'sold', 'price']].corr().fillna(0)


# 4. FEATURE CORRELATION HEATMAP
def heat(ax):
    im = ax.imshow(corr.values, vmin=-1, vmax=1)
    ax.set_xticks(range(4))
    ax.set_yticks(range(4))
    ax.set_xticklabels(corr.columns)
    ax.set_yticklabels(corr.columns)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center', fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
save('correlation_heatmap', 'Feature correlation heatmap', heat)
print('Generated EDA charts in', OUT)
