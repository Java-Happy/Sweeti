from scheduler import start_scheduler, stop_scheduler
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from storage import init_db, save_market_snapshot, get_database_stats, get_connection, get_collection_runs


OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3:4b"
COINGECKO_URL = "https://api.coingecko.com/api/v3"

market_cache = {}
CACHE_SECONDS = 60

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()

    try:
        yield
    finally:
        stop_scheduler()

app = FastAPI(
    title="Crypto Radar AI",
    description="AI-powered cryptocurrency market intelligence platform",
    version="0.3.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    prompt: str


async def get_market_data(vs_currency: str, per_page: int, page: int):
    cache_key = f"{vs_currency}:{per_page}:{page}"
    now = time.time()

    cached = market_cache.get(cache_key)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["data"]

    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": page,
        "price_change_percentage": "24h"
    }

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(
                f"{COINGECKO_URL}/coins/markets",
                params=params
            )
            response.raise_for_status()
            raw_data = response.json()

        data = [
            {
                "id": coin.get("id"),
                "symbol": coin.get("symbol"),
                "name": coin.get("name"),
                "current_price": coin.get("current_price"),
                "market_cap": coin.get("market_cap"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "total_volume": coin.get("total_volume"),
                "price_change_percentage_24h": coin.get(
                    "price_change_percentage_24h"
                ),
                "high_24h": coin.get("high_24h"),
                "low_24h": coin.get("low_24h"),
                "last_updated": coin.get("last_updated")
            }
            for coin in raw_data
        ]

        market_cache[cache_key] = {
            "time": now,
            "data": data
        }
        return data

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"CoinGecko returned HTTP {e.response.status_code}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"CoinGecko connection failed: {str(e)}"
        )


@app.get("/")
async def root():
    return {
        "name": "Crypto Radar AI",
        "version": "0.3.0",
        "status": "running"
    }


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "service": "Crypto Radar AI"
    }


@app.get("/api/ai/status")
async def ai_status():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            data = response.json()

        models = [
            model["name"]
            for model in data.get("models", [])
        ]

        return {
            "ollama": "connected",
            "model": OLLAMA_MODEL,
            "available_models": models
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama connection failed: {str(e)}"
        )


@app.post("/api/ai/analyze")
async def ai_analyze(request: AnalyzeRequest):
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": request.prompt,
                    "stream": False,
                    "options": {"temperature": 0.2}
                }
            )
            response.raise_for_status()
            result = response.json()

        return {
            "model": OLLAMA_MODEL,
            "analysis": result.get("response", ""),
            "done": result.get("done", False)
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI analysis failed: {str(e)}"
        )


@app.get("/api/market/status")
async def market_status():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{COINGECKO_URL}/ping")
            response.raise_for_status()

        return {
            "data_source": "CoinGecko",
            "status": "connected",
            "message": response.json()
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"CoinGecko connection failed: {str(e)}"
        )


@app.get("/api/market/coins")
async def market_coins(
    vs_currency: str = "usd",
    per_page: int = Query(default=100, ge=1, le=250),
    page: int = Query(default=1, ge=1)
):
    data = await get_market_data(vs_currency, per_page, page)

    return {
        "data_source": "CoinGecko",
        "currency": vs_currency,
        "page": page,
        "count": len(data),
        "data": data
    }


@app.get("/api/market/top-movers")
async def market_top_movers(
    limit: int = Query(default=10, ge=1, le=50)
):
    data = await get_market_data("usd", 250, 1)

    valid = [
        coin for coin in data
        if coin["price_change_percentage_24h"] is not None
    ]

    gainers = sorted(
        valid,
        key=lambda x: x["price_change_percentage_24h"],
        reverse=True
    )[:limit]

    losers = sorted(
        valid,
        key=lambda x: x["price_change_percentage_24h"]
    )[:limit]

    volume_leaders = sorted(
        valid,
        key=lambda x: x["total_volume"] or 0,
        reverse=True
    )[:limit]

    return {
        "data_source": "CoinGecko",
        "scope": "Top 250 coins by market capitalization",
        "top_gainers": gainers,
        "top_losers": losers,
        "top_volume": volume_leaders
    }


# 新增：手动采集行情并保存到数据库
@app.post("/api/market/collect")
async def market_collect(
    vs_currency: str = "usd",
    per_page: int = Query(default=250, ge=1, le=250),
    page: int = Query(default=1, ge=1, le=10)
):
    data = await get_market_data(vs_currency, per_page, page)

    if not data:
        raise HTTPException(
            status_code=502,
            detail="CoinGecko returned no market data"
        )

    result = save_market_snapshot(data, currency=vs_currency)

    return {
        "status": "success",
        "data_source": "CoinGecko",
        "currency": vs_currency,
        "page": page,
        **result
    }


# 新增：数据库统计
@app.get("/api/market/database")
async def market_database():
    return {
        "status": "success",
        **get_database_stats()
    }


# 新增：指定币种历史快照
@app.get("/api/market/history/{coin_id}")
async def market_history(
    coin_id: str,
    limit: int = Query(default=100, ge=1, le=1000)
):
    with get_connection() as conn:
        coin = conn.execute(
            "SELECT coin_id, symbol, name FROM coins WHERE coin_id = ?",
            (coin_id,)
        ).fetchone()

        if coin is None:
            raise HTTPException(
                status_code=404,
                detail=f"Coin not found: {coin_id}"
            )

        rows = conn.execute(
            """
            SELECT
                captured_at,
                currency,
                current_price,
                market_cap,
                total_volume,
                price_change_24h,
                high_24h,
                low_24h,
                source_updated_at
            FROM market_snapshots
            WHERE coin_id = ?
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            (coin_id, limit)
        ).fetchall()

    return {
        "coin": dict(coin),
        "count": len(rows),
        "history": [dict(row) for row in rows]
    }


# ??????????
@app.get("/api/market/collection-runs")
async def market_collection_runs(
    limit: int = Query(default=20, ge=1, le=200)
):
    runs = get_collection_runs(limit)
    return {
        "status": "success",
        "count": len(runs),
        "runs": runs
    }

