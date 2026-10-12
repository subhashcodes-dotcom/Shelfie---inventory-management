"""Offline validation for the submission package (does not require Flask)."""
from pathlib import Path
import ast
import sqlite3
import json
from jinja2 import Environment, FileSystemLoader
from model import get_metrics, compare_models


# 1. CHECK REQUIRED FILES AND PYTHON SYNTAX
BASE = Path(__file__).resolve().parent
assert (BASE / 'app.py').exists() and (BASE / 'model.py').exists()
ast.parse((BASE / 'app.py').read_text())
ast.parse((BASE / 'model.py').read_text())


# 2. CHECK TEMPLATE SYNTAX
E = Environment(loader=FileSystemLoader(BASE / 'templates'))
for name in E.list_templates(filter_func=lambda n: n.endswith('.html')):
    E.parse(E.loader.get_source(E, name)[0])
assert len(list((BASE / 'static' / 'eda').glob('*.png'))) >= 11
c = sqlite3.connect(BASE / 'inventory.db')
for t in ['products', 'variants', 'inventory', 'sales_orders', 'sales_items', 'purchase_orders', 'purchase_items',
    'suppliers', 'customers', 'users', 'locations', 'location_inventory', 'inventory_events']:
    assert c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] >= 0
assert c.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 825
assert c.execute('SELECT COUNT(*) FROM variants').fetchone()[0] == 2475
assert c.execute('SELECT COUNT(*) FROM suppliers').fetchone()[0] == 100
c.close()


# 3. CHECK MODEL METRICS AND MODEL COMPARISON
metrics = get_metrics(BASE / 'models')
assert 'MAE' in metrics and 'RMSE' in metrics and ('R2' in metrics)
comparison = compare_models(BASE / 'inventory.db', BASE / 'models')
assert len(comparison) == 4
print('PASS: Python syntax')
print('PASS: Jinja templates')
print('PASS: database seed')
print('PASS: EDA assets')
print('PASS: model artifacts and comparison')
print(json.dumps({'metrics': metrics, 'model_comparison': comparison}, indent=2))
