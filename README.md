# Data Central (Demo)

A **demo** Django web app that shows how a kitchen & bath contractor might manage products, customers, quotes, jobs, and billing in one place.

This is a portfolio / learning showcase—not a production deployment guide. Screens and workflows are representative of real shop operations (jobs, sales orders, change orders, contracts, accounting).

## What you can explore

- **Jobs** — sold jobs, quotes, schedules, contracts, and print/PDF previews  
- **Sales & billing** — sales orders report, payments, change orders, SLW billing milestones  
- **CRM** — customers and related contact info  
- **Products** — catalog, quotes, and line items  
- **Sitework** — sitework quotes and progress  
- **Admin** — Django admin for supporting data  

## Tech stack (demo environment)

- Python / Django  
- PostgreSQL (local demo may also use SQLite for quick tryouts)  
- HTMX + Bootstrap  
- ReportLab for PDF contracts and sales-order reports  
- Optional Celery worker in fuller setups  

## Quick start (local demo)

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open `http://127.0.0.1:8000/` and sign in with the superuser you created.

> Tip: For a fast local demo without Postgres, some environments use `allenkit1.settings_sqlite`—use whatever settings your machine already has working.

## Project layout

| Path | Role |
|------|------|
| `allenkit1/` | Django project settings |
| `job/` | Jobs, sales, accounting, PDFs |
| `crm/` | Customers |
| `product/` | Products & quotes |
| `sitework/` | Sitework quotes |
| `accounts/` | Auth |
| `templates/` / `static/` | Shared UI |

## Notes

- Data and branding are for **demonstration** of features and UX.  
- Do not treat this README as production ops docs (secrets, scaling, backups, etc.).  
- Sample data may be incomplete or reset between demos.

## License

Demo / portfolio use. Not offered as a commercial product.
