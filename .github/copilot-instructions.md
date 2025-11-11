# GitHub Copilot Instructions for Mboard Optimizador

## Project Overview

**Mboard Optimizador** is a multi-organization material optimization panel built with Django 5.x. The application manages materials (boards and edge banding) with role-based access control, real-time chat functionality, and PDF export capabilities.

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: Django 5.x
- **Database**: SQLite (default), PostgreSQL (production)
- **Linter**: Ruff (configured with minimal rules in `ruff.toml`)
- **Package Manager**: pip
- **Deployment**: Gunicorn, Whitenoise for static files

## Project Structure

```
Mboard_Optimizador/
├── Django/                          # Main Django project
│   ├── manage.py                    # Django management script
│   ├── WowDash/                     # Main Django app
│   │   ├── settings.py              # Django settings
│   │   ├── urls.py                  # URL routing
│   │   ├── *_views.py               # View modules (by feature)
│   │   └── ...
│   ├── core/                        # Core app (models, commands)
│   │   ├── models.py                # Database models
│   │   └── management/commands/     # Custom management commands
│   ├── templates/                   # Django templates
│   └── static/                      # Static files (CSS, JS, images)
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Development dependencies
├── ruff.toml                        # Ruff linter configuration
├── .github/workflows/ci.yml         # CI/CD pipeline
└── README.md                        # Project documentation
```

## Development Workflow

### Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -U pip
pip install -r requirements-dev.txt

# Database setup
cd Django
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Run development server
python manage.py runserver 0.0.0.0:8000
```

### Linting

```bash
# Run ruff linter
ruff check .

# Note: The ruff.toml configuration only checks for critical syntax errors:
# - E9: SyntaxError
# - F63: Missing __future__ annotations
# - F7: Invalid __future__ import
# - F82: Star import used but not defined
```

### Build/Check

```bash
# Django system check
cd Django
python manage.py check

# Collect static files (build sanity check)
python manage.py collectstatic --noinput
```

### Testing

Currently, there is no test suite in this repository. When adding tests:
- Use pytest with pytest-django (already in requirements-dev.txt)
- Follow Django testing conventions
- Place tests in `tests/` directories within Django apps

## Coding Standards

### Language & Style

- **Primary Language**: Spanish is used throughout the codebase (variables, comments, documentation)
- **Code Style**: Follow PEP 8 guidelines
- **Line Length**: 120 characters (configured in ruff.toml)
- **Target Version**: Python 3.11

### Django Conventions

- Use Django's built-in features (ORM, forms, authentication)
- Follow Django project structure conventions
- Keep views organized by feature in separate `*_views.py` files
- Use Django's template language for rendering

### Key Features to Maintain

1. **Multi-Organization Support**: Always consider organization context in queries and views
2. **Role-Based Access Control**: Respect user roles (super_admin, org_admin, agente, subordinador)
3. **Material Management**: Handle both tableros (boards) and tapacantos (edge banding)
4. **Chat System**: Maintain polling-based real-time chat functionality
5. **PDF Export**: Use ReportLab for PDF generation

## Custom Management Commands

The project includes custom management commands in `Django/core/management/commands/`:

```bash
# Example: Migrate materials across organizations
python manage.py migrar_materiales_organizaciones --dry-run --exclude-general
```

## Configuration

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (optional, defaults to SQLite)
- `SECRET_KEY`: Django secret key (required for production)
- `DEBUG`: Set to False in production
- `ALLOWED_HOSTS`: Configure for production deployment

### Static Files

- Static files are served via Whitenoise in production
- Development: Django's built-in static file serving
- Location: `Django/static/`

## Important Notes

- **Spanish Language**: Code, comments, and documentation are primarily in Spanish
- **No Force Push**: Git history cannot be rewritten (no rebase/force push)
- **Minimal Linting**: Ruff configuration only checks critical syntax errors
- **Database**: SQLite by default; configure PostgreSQL for production use
- **Material Import**: CSV import format documented in `Django/static/docs/IMPORTACION_MATERIALES.md`

## CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`):
1. Install dependencies (requirements-dev.txt)
2. Run ruff linter
3. Run Django system check
4. Collect static files (build sanity check)

## Common Tasks

### Adding a New Feature

1. Create or modify views in appropriate `*_views.py` file
2. Update URL routing in `WowDash/urls.py`
3. Create/update templates in `templates/`
4. Add static assets to `static/` if needed
5. Update models in `core/models.py` if needed, then migrate
6. Run linter and Django check before committing

### Database Migrations

```bash
cd Django
python manage.py makemigrations
python manage.py migrate
```

### Material Import/Export

- Import format: CSV with specific columns (see docs)
- Export: PDF generation using ReportLab
- Always scope materials to organization

## Resources

- [Django 5.x Documentation](https://docs.djangoproject.com/en/5.2/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [ReportLab Documentation](https://www.reportlab.com/docs/reportlab-userguide.pdf)
