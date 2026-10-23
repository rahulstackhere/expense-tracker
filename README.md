# Ledger — Expense Tracker

A responsive expense tracker built with Next.js App Router, TypeScript, FastAPI, SQLAlchemy, and SQLite. Categories and expenses are saved in the backend database and loaded again when the dashboard refreshes.

## Run locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## FastAPI backend

The FastAPI backend is in [`backend/`](./backend/). Follow [`backend/README.md`](./backend/README.md) to install and run it. The frontend defaults to `http://localhost:8000`; set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` to override it.

Start both servers in separate terminals:

```powershell
# Terminal 1
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --env-file .env

# Terminal 2, from the project root
npm run dev
```

The SQLite database file is `backend/expense_tracker.db`. It and its tables are created when the backend starts. The frontend calls the backend endpoints to load categories, expenses, and summary statistics, and to save newly created categories and expenses.

## Useful commands

```bash
npm run lint
npm run typecheck
npm run build
```
