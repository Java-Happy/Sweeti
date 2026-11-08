# Crypto Radar AI

A local cryptocurrency market dashboard built with **FastAPI**, **Next.js**, **SQLite**, **CoinGecko**, and a local **Ollama / Qwen3** model.

## Features

- Tracks the top 250 cryptocurrencies by market capitalization through CoinGecko.
- Collects market snapshots every 5 minutes with APScheduler.
- Stores assets, historical snapshots, and collection runs in SQLite.
- Displays live market metrics, a searchable asset watchlist, and aggregated historical candlesticks.
- Shows the status of the FastAPI backend, market feed, and local Ollama service.

> The chart candles are aggregated from periodic CoinGecko price snapshots. They are not exchange-native OHLC candles. Their coverage depends on the snapshots collected so far.

## Project layout

```text
.
├── main.py
├── auth.py
├── scheduler.py
├── storage.py
├── scripts/
│   └── create_svip_accounts.py
├── test_collect.py
├── requirements.txt
└── frontend/
    ├── package.json
    └── src/
```

## Requirements

- Python 3.11 or newer
- Node.js 20.9 or newer
- npm
- Ollama (optional; required for local AI analysis)
- 
## Run locally on Windows

### 1. Backend

From the repository root, create and activate a virtual environment, then install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the three initial SVIP accounts once. The script generates strong random passwords and prints them only in your local terminal:

```powershell
python scripts/create_svip_accounts.py
```

The initial usernames are `svip01`, `svip02`, and `svip03`. Save each generated password in a password manager; the script does not store or print passwords again for accounts that already exist. New registrations receive the standard `member` role.

Start FastAPI:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The backend initializes the SQLite database and starts the five-minute collection scheduler when it starts.

Useful endpoints:

- `GET /` — service information
- `GET /api/health` — health check
- `POST /api/auth/register` / `POST /api/auth/login` — member registration and login
- `GET /api/auth/me` — current authenticated member
- `GET /api/ai/status` — Ollama status
- `GET /api/market/status` — market-data status
- `GET /api/market/coins` — latest coin data
- `GET /api/market/database` — database statistics
- `GET /api/market/history/{coin_id}` — historical snapshots
- `GET /api/market/collection-runs` — collection history

### 2. Frontend

Open a second terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The frontend expects the API at `http://127.0.0.1:8000` by default. Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if the backend runs elsewhere. Restart the Next.js dev server after changing environment variables.

## Configuration

The backend supports these environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `CRYPTO_RADAR_DB_PATH` | SQLite database file path | `D:\CryptoRadarAI\database\crypto_radar.db` |
| `FRONTEND_ORIGINS` | Comma-separated allowed frontend origins for CORS | `http://localhost:3000,http://127.0.0.1:3000` |
| `CRYPTO_RADAR_AUTH_SECRET` | Optional signing secret for login tokens (at least 32 characters); local development creates an ignored `.auth_secret` file automatically | auto-generated locally |

For example, in PowerShell:

```powershell
$env:CRYPTO_RADAR_DB_PATH = "D:\CryptoRadarAI\database\crypto_radar.db"
$env:FRONTEND_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
```

The frontend variable `NEXT_PUBLIC_API_BASE_URL` is documented in `frontend/.env.example`.

## Production notes

- Set `CRYPTO_RADAR_DB_PATH` to a persistent writable volume. The default database path is specific to the original Windows development machine.
- Set `FRONTEND_ORIGINS` to the exact deployed frontend origin(s); do not use a wildcard with credentialed requests.
- Set `NEXT_PUBLIC_API_BASE_URL` to the publicly reachable backend URL before building the frontend.
- Keep API keys and other secrets in environment variables; never commit them.
- Set a unique `CRYPTO_RADAR_AUTH_SECRET` of at least 32 characters in production and persist it securely. The local `.auth_secret` file is ignored by Git.
- User passwords are stored as PBKDF2-HMAC-SHA256 hashes; login tokens expire after seven days.
- Run the backend and frontend as separate services behind HTTPS in production.
- Use a persistent database/volume and a process manager for the backend scheduler.

## Validation

Frontend type-check:

```powershell
cd frontend
npx tsc --noEmit
```

Frontend lint:

```powershell
npm run lint
```
