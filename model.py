"""
SMART INVENTORY - MACHINE LEARNING MODULE

This file is intentionally divided into four simple stages:
1. Read sales history
2. Train and evaluate demand model
3. Generate inventory recommendations
4. Compare simple ML models
"""
from pathlib import Path
import sqlite3
import json
import math
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
FEATURES = ['dow', 'month', 'dayofmonth', 'weekofyear', 'lag1', 'lag7', 'roll7']


# 1. DATABASE / DATA ACCESS
def conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


# 2. PREPARE DAILY SALES DATA
def sales_frame(db):
    c = conn(db)
    q = '''SELECT so.order_date day, si.variant_id, SUM(si.quantity) qty
         FROM sales_orders so JOIN sales_items si ON si.order_id=so.id
         WHERE so.status NOT IN ('cancelled','failed')
         GROUP BY so.order_date, si.variant_id ORDER BY so.order_date'''
    df = pd.read_sql_query(q, c)
    c.close()
    if df.empty:
        return df
    df['day'] = pd.to_datetime(df['day'], dayfirst=True, errors='coerce').dt.normalize()
    df = df.dropna(subset=['day']).groupby(['day', 'variant_id'], as_index=False)['qty'].sum()
    return df


# 3. TRAIN RANDOM FOREST + ANOMALY MODEL
def train_and_save(db, model_dir):
    model_dir = Path(model_dir)
    model_dir.mkdir(exist_ok=True)
    df = sales_frame(db)
    if df.empty:
        return {}
    frames = []
    for vid, g in df.groupby('variant_id'):
        g = g.set_index('day')[['qty']].asfreq('D', fill_value=0).reset_index()
        g['variant_id'] = vid
        g['dow'] = g.day.dt.dayofweek
        g['month'] = g.day.dt.month
        g['dayofmonth'] = g.day.dt.day
        g['weekofyear'] = g.day.dt.isocalendar().week.astype(int)
        g['lag1'] = g.qty.shift(1)
        g['lag7'] = g.qty.shift(7)
        g['roll7'] = g.qty.shift(1).rolling(7, min_periods=2).mean()
        frames.append(g)
    d = pd.concat(frames, ignore_index=True).dropna().sort_values('day')
    if len(d) < 30:
        return {}
    cut = max(1, int(len(d) * 0.8))
    train = d.iloc[:cut]
    test = d.iloc[cut:]
    model = RandomForestRegressor(n_estimators=160, max_depth=10, random_state=42, min_samples_leaf=2, n_jobs=-1)
    model.fit(train[FEATURES], train.qty)
    pred = model.predict(test[FEATURES])
    metrics = {'MAE': round(float(mean_absolute_error(test.qty, pred)), 3), 'RMSE': round(float(np.sqrt(mean_squared_error(test.qty,
        pred))), 3), 'R2': round(float(r2_score(test.qty, pred)), 3), 'training_rows': int(len(train)), 'test_rows': int(len(test))}
    joblib.dump(model, model_dir / 'demand_model.joblib')
    (model_dir / 'metrics.json').write_text(json.dumps(metrics, indent=2))
    iso = IsolationForest(contamination=0.05, random_state=42)
    iso.fit(d[['qty']])
    joblib.dump(iso, model_dir / 'anomaly_model.joblib')
    return metrics


# 4. READ MODEL METRICS
def get_metrics(model_dir):
    p = Path(model_dir) / 'metrics.json'
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except:
        return {}


# 5. LOAD TRAINED MODEL
def get_model(db, model_dir):
    p = Path(model_dir) / 'demand_model.joblib'
    if p.exists():
        return joblib.load(p)
    train_and_save(db, model_dir)
    return joblib.load(p) if p.exists() else None


# 6. DECISION ENGINE: FORECAST → REORDER → RISK
def get_recommendations(db, limit=100):
    c = conn(db)
    model = get_model(db, Path(db).parent / 'models')
    sales = sales_frame(db)
    if sales.empty:
        c.close()
        return []
    inv = pd.read_sql_query((
                                'SELECT '
                                'i.variant_id,i.quantity,i.low_stock_threshold,p.name,p.sku,v.color,v.storage,v.ram'
                                ',p.base_price,v.price_modifier FROM inventory i JOIN variants v ON '
                                'v.id=i.variant_id JOIN products p ON p.id=v.product_id'
                            ),
        c)
    incoming = pd.read_sql_query((
                                     "SELECT pi.variant_id,SUM(CASE WHEN po.status IN ('ordered','processing') THEN "
                                     'MAX(pi.quantity_ordered-pi.quantity_received,0) ELSE 0 END) incoming FROM '
                                     'purchase_items pi JOIN purchase_orders po ON po.id=pi.order_id GROUP BY '
                                     'pi.variant_id'
                                 ),
        c)
    incoming = dict(zip(incoming.variant_id, incoming.incoming.fillna(0)))
    today = pd.Timestamp.today().normalize()
    rec = []
    for _, r in inv.iterrows():
        vid = r.variant_id
        g = sales[sales.variant_id == vid].sort_values('day')
        avg = float(g.tail(30).qty.mean()) if not g.empty else 0
        pred = max(0, avg * 7)
        if model is not None and len(g) >= 8:
            series = g.set_index('day').qty.asfreq('D', fill_value=0)
            last = series.index.max()
            x = pd.DataFrame([{'dow': last.dayofweek, 'month': last.month, 'dayofmonth': last.day,
                'weekofyear': int(last.isocalendar().week), 'lag1': series.iloc[-1], 'lag7': series.iloc[-7] if len(series) >= 7 else series.iloc[0],
                'roll7': series.iloc[-7:].mean()}])
            try:
                pred = max(0, float(model.predict(x[FEATURES])[0]) * 7)
            except Exception:
                pass
        incoming_qty = float(incoming.get(vid, 0) or 0)
        stock = float(r.quantity)
        safety = max(1, round(avg * 2))
        reorder = max(0, math.ceil(pred + safety - stock - incoming_qty))
        days = stock / avg if avg > 0 else 999
        risk = 'LOW'
        if stock <= r.low_stock_threshold or days < 7 or reorder > 0.5 * max(stock, 1):
            risk = 'HIGH'
        elif days < 14:
            risk = 'MEDIUM'
        status = 'REORDER' if reorder > 0 else 'OK'
        rec.append({'variant_id': vid, 'product': r['name'], 'sku': r['sku'], 'variant': ' / '.join([x for x in [r['ram'],
            r['storage'], r['color']] if str(x) != 'nan' and str(x)]), 'stock': int(stock), 'threshold': int(r.low_stock_threshold),
            'avg_daily': round(avg, 2), 'predicted_7d': round(pred, 1), 'incoming': int(incoming_qty), 'days_left': round(days,
            1) if days < 999 else None, 'risk': risk, 'recommended_order': int(reorder), 'status': status})
    order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    rec.sort(key=lambda x: (order[x['risk']], -x['recommended_order']))
    c.close()
    return rec[:limit]


# 7. COMPARE MODELS FOR THE REPORT
def compare_models(db, model_dir):
    """Train several explainable regressors on the same hold-out split for the report."""
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeRegressor
    from sklearn.ensemble import GradientBoostingRegressor
    df = sales_frame(db)
    if df.empty:
        return []
    frames = []
    for vid, g in df.groupby('variant_id'):
        g = g.set_index('day')[['qty']].asfreq('D', fill_value=0).reset_index()
        g['variant_id'] = vid
        g['dow'] = g.day.dt.dayofweek
        g['month'] = g.day.dt.month
        g['dayofmonth'] = g.day.dt.day
        g['weekofyear'] = g.day.dt.isocalendar().week.astype(int)
        g['lag1'] = g.qty.shift(1)
        g['lag7'] = g.qty.shift(7)
        g['roll7'] = g.qty.shift(1).rolling(7, min_periods=2).mean()
        frames.append(g)
    d = pd.concat(frames, ignore_index=True).dropna().sort_values('day')
    if len(d) < 30:
        return []
    cut = max(1, int(len(d) * 0.8))
    train, test = (d.iloc[:cut], d.iloc[cut:])
    models = [('Linear Regression', LinearRegression()), ('Decision Tree', DecisionTreeRegressor(max_depth=10,
        random_state=42, min_samples_leaf=2)), ('Random Forest', RandomForestRegressor(n_estimators=160, max_depth=10,
        random_state=42, min_samples_leaf=2, n_jobs=-1)), ('Gradient Boosting', GradientBoostingRegressor(n_estimators=150,
        max_depth=3, random_state=42, loss='huber'))]
    out = []
    for name, m in models:
        m.fit(train[FEATURES], train.qty)
        pred = m.predict(test[FEATURES])
        out.append({'model': name, 'MAE': round(float(mean_absolute_error(test.qty, pred)), 3), 'RMSE': round(float(np.sqrt(mean_squared_error(test.qty,
            pred))), 3), 'R2': round(float(r2_score(test.qty, pred)), 3)})
    return out
