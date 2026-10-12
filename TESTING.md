# Testing & Demo Checklist

## Startup
- [ ] Install Python dependencies from `requirements.txt`.
- [ ] Run `python app.py`.
- [ ] Open `http://127.0.0.1:5000`.

## Authentication
- [ ] Admin login works.
- [ ] Manager login works.
- [ ] Staff login works.
- [ ] Wrong password is rejected.
- [ ] Profile opens from the top-right avatar.
- [ ] Display name can be changed.
- [ ] Password can be changed.

## Admin / management
- [ ] Employees page opens for Admin.
- [ ] New employee account can be created.
- [ ] New account can log in.
- [ ] Admin cannot delete the currently logged-in account.
- [ ] Supplier can be added.
- [ ] Product can be added.
- [ ] Product rate can be changed.

## Operations
- [ ] Warehouse search works.
- [ ] Empty taxonomy categories are not shown.
- [ ] Stock adjustment works.
- [ ] Return adjustment works.
- [ ] Damage adjustment works.
- [ ] Sale reduces inventory.
- [ ] Insufficient stock blocks a sale.
- [ ] Purchase receiving increases inventory.
- [ ] Stock transfer updates source and destination location quantities.

## Data Science
- [ ] Analytics page shows all EDA charts.
- [ ] Model comparison is visible in System Management.
- [ ] Retrain model action completes.
- [ ] Decision Center lists recommendations.
- [ ] Decision explanation page shows the formula and inputs.
- [ ] Purchase order can be created from a recommendation.
- [ ] CSV recommendation export downloads.

## Assistant
- [ ] Low-stock query works.
- [ ] Top-selling query works.
- [ ] Forecast query works.
- [ ] Supplier query works.
- [ ] Slow-moving stock query works.
- [ ] System/model query works.
- [ ] Question Library buttons populate the input.
