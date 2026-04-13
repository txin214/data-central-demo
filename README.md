# Allen Kitchen & Bath Data Central

A Django-based web application for managing kitchen and bath products, customer relationships, site work, and job management.
MARCH 2026 Changed to use PostgreSQL instead of SQLite.

## Features

- Product Management
- Customer Relationship Management (CRM)
- Site Work Management
- Job Management
- Dynamic Product Categories
- Image Management
- Quote Generation

## Tech Stack

- Django 4.2.3
- SQLite Database
- HTMX for dynamic interactions
- Bootstrap for UI
- Dynamic Breadcrumbs
- Import/Export functionality

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/allenkit.git
cd allenkit
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Deployment

See deployment documentation in `docs/deployment.md` for detailed instructions on deploying to a production server.

## Project Structure

- `allenkit1/` - Main project configuration
- `crm/` - Customer Relationship Management app
- `job/` - Job Management app
- `product/` - Product Management app
- `sitework/` - Site Work Management app
- `templates/` - Global templates
- `static/` - Static files
- `media/` - User-uploaded files

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is proprietary and confidential. All rights reserved.
