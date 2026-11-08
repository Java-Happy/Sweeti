import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(os.getenv("CRYPTO_RADAR_DB_PATH", r"D:\CryptoRadarAI\database\crypto_radar.db"))


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coins (
                coin_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                market_cap_rank INTEGER,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                currency TEXT NOT NULL,
                current_price REAL,
                market_cap REAL,
                total_volume REAL,
                price_change_24h REAL,
                high_24h REAL,
                low_24h REAL,
                source_updated_at TEXT,
                FOREIGN KEY (coin_id) REFERENCES coins(coin_id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_coin_time
            ON market_snapshots(coin_id, captured_at)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_time
            ON market_snapshots(captured_at)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                source TEXT NOT NULL DEFAULT 'coingecko',
                currency TEXT NOT NULL DEFAULT 'usd',
                fetched_count INTEGER NOT NULL DEFAULT 0,
                saved_count INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL,
                error_message TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_collection_runs_started
            ON collection_runs(started_at)
        """)

    return str(DB_PATH)


def save_market_snapshot(coins, currency="usd"):
    captured_at = now_utc()
    saved_count = 0

    with get_connection() as conn:
        for coin in coins:
            coin_id = coin.get("id")

            if not coin_id:
                continue

            conn.execute("""
                INSERT INTO coins (
                    coin_id, symbol, name, market_cap_rank,
                    first_seen_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(coin_id) DO UPDATE SET
                    symbol = excluded.symbol,
                    name = excluded.name,
                    market_cap_rank = excluded.market_cap_rank,
                    updated_at = excluded.updated_at
            """, (
                coin_id,
                coin.get("symbol") or "",
                coin.get("name") or "",
                coin.get("market_cap_rank"),
                captured_at,
                captured_at
            ))

            conn.execute("""
                INSERT INTO market_snapshots (
                    coin_id, captured_at, currency,
                    current_price, market_cap, total_volume,
                    price_change_24h, high_24h, low_24h,
                    source_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                coin_id,
                captured_at,
                currency,
                coin.get("current_price"),
                coin.get("market_cap"),
                coin.get("total_volume"),
                coin.get("price_change_percentage_24h"),
                coin.get("high_24h"),
                coin.get("low_24h"),
                coin.get("last_updated")
            ))

            saved_count += 1

    return {
        "saved_count": saved_count,
        "captured_at": captured_at,
        "database": str(DB_PATH)
    }


def start_collection_run(source="coingecko", currency="usd"):
    started_at = now_utc()

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO collection_runs (
                started_at, status, source, currency
            )
            VALUES (?, 'running', ?, ?)
        """, (started_at, source, currency))

        run_id = cursor.lastrowid

    return run_id


def finish_collection_run(
    run_id,
    status,
    fetched_count=0,
    saved_count=0,
    duration_seconds=None,
    error_message=None
):
    if status not in ("success", "failed"):
        raise ValueError("status 必须是 success 或 failed")

    finished_at = now_utc()

    with get_connection() as conn:
        conn.execute("""
            UPDATE collection_runs
            SET finished_at = ?,
                status = ?,
                fetched_count = ?,
                saved_count = ?,
                duration_seconds = ?,
                error_message = ?
            WHERE id = ?
        """, (
            finished_at,
            status,
            fetched_count,
            saved_count,
            duration_seconds,
            error_message[:2000] if error_message else None,
            run_id
        ))


def get_collection_runs(limit=20):
    limit = max(1, min(int(limit), 200))

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT *
            FROM collection_runs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def get_database_stats():
    with get_connection() as conn:
        coin_count = conn.execute(
            "SELECT COUNT(*) FROM coins"
        ).fetchone()[0]

        snapshot_count = conn.execute(
            "SELECT COUNT(*) FROM market_snapshots"
        ).fetchone()[0]

        run_count = conn.execute(
            "SELECT COUNT(*) FROM collection_runs"
        ).fetchone()[0]

    return {
        "coins": coin_count,
        "snapshots": snapshot_count,
        "collection_runs": run_count,
        "database": str(DB_PATH)
    }
