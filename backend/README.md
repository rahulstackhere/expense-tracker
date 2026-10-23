# Expense Tracker API

FastAPI backend for the expense tracker. It uses SQLite and SQLAlchemy and provides the five endpoints used by the Next.js frontend.

## Setup

From the `backend` directory, create and activate a virtual environment, then install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`DATABASE_URL` defaults to `sqlite:///./expense_tracker.db`; relative SQLite paths are resolved against the `backend` directory, regardless of the shell's current directory. Set `DATABASE_URL` and `CORS_ORIGINS` in the environment before starting the server to override the defaults. `CORS_ORIGINS` accepts comma-separated origins and defaults to localhost and 127.0.0.1 on port 3000.

On startup, the API creates missing tables and installs SQLite validation triggers and a Unicode case-insensitive unique category index. These are additive and do not delete existing records. If existing category names collide under Unicode case folding, startup fails with an actionable error rather than removing or renaming user data.

## Start

```powershell
python -m uvicorn main:app --reload --env-file .env
```

The API is available at `http://127.0.0.1:8000`. Interactive documentation is at `/docs`, alternative documentation at `/redoc`, and the OpenAPI schema at `/openapi.json`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/categories` | Create a trimmed, case-insensitively unique category (`201`; duplicate names return `409`) |
| `GET` | `/categories` | List all categories with `total_expenses`, including zero-count categories |
| `POST` | `/expenses` | Create a positive-amount expense (`201`; unknown category returns `404`) |
| `GET` | `/expenses` | List newest expenses with their category name |
| `GET` | `/summary` | Return `total`, `count`, and `average` |

Request validation rejects blank names and titles, non-positive or invalid monetary values, and invalid category IDs. The database also enforces nonblank text and maximum character lengths, positive monetary values with at most two decimal places and a maximum amount of 9,999,999,999.99, Unicode case-insensitive category-name uniqueness, and category foreign keys. SQLite foreign-key enforcement is enabled for each connection. Monetary values are stored to two decimal places.

## Tests

```powershell
python -m pytest
```

The API tests use a temporary SQLite database and do not read or modify the development database.
