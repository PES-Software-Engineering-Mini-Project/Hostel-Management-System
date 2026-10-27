# Hostel Management System

[![CI](https://github.com/PES-Software-Engineering-Mini-Project/Hostel-Management-System/actions/workflows/ci.yml/badge.svg)](https://github.com/PES-Software-Engineering-Mini-Project/Hostel-Management-System/actions/workflows/ci.yml)

HMS is a server-rendered Django application for college-hostel operations. Existing
requirements, proposal, test-plan, and architecture documents in this repository are
preserved as the project source of truth. Where the implementation differs from them,
the difference and its reason are recorded in [docs/DEVIATIONS.md](docs/DEVIATIONS.md).

## Technology and current scope

The foundation follows the SRS: Python 3.10+, Django 5.x, Django templates, Django
ORM, SQLite for local development, and PostgreSQL for deployment. It currently
contains only the project infrastructure and the custom user-model foundation:

- Django project configuration and a minimal base template/home route.
- Separate `accounts`, `rooms`, `fees`, `complaints`, and `visitors` apps.
- An SRN-based user model with unique SRN and email, contact details, optional branch
  and year of study, and `Student`/`Admin` roles.
- Django's password hashing; plaintext passwords are never stored.

The SCRUM-6 login page authenticates with SRN and password, redirects users according
to their stored Student/Admin role, protects the two post-login landing routes, and
supports POST logout. Registration, room management/allocation, feature dashboards,
fees, complaints, visitors, search, and reports remain separate stories.

## Local setup

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
   ```

3. Install dependencies and apply migrations:

   ```bash
   python -m pip install -r requirements.txt
   python manage.py migrate
   ```

4. Run checks, tests, and the development server:

   ```bash
   python manage.py check
   python manage.py test
   python manage.py runserver
   ```

   Visit `http://127.0.0.1:8000/`. The Django admin is at `/admin/`; create a
   superuser with `python manage.py createsuperuser` when needed.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and on every pull
request to `main`, using Python 3.10 and 3.12. Each run installs the requirements and
executes the same checks you should run locally before pushing:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

A pull request can be merged into `main` only when CI passes and a teammate has
approved it. If a run fails, open it from the Actions tab, reproduce the failing step
locally, and push a fix before continuing other work.

## Configuration

SQLite (`db.sqlite3`) is the default and needs no credentials. Copy `.env.example`
to `.env` as a safe local reference; settings are read from environment variables, so
load that file with your preferred environment tool or export the values in your shell.

To use PostgreSQL, set `DATABASE_ENGINE=django.db.backends.postgresql` together with
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and
`POSTGRES_PORT`. No passwords or other secrets are committed. Set
`DJANGO_SECRET_KEY` before any non-development deployment; production also requires
`DJANGO_DEBUG=False` and an explicit `DJANGO_ALLOWED_HOSTS` list.
