from scheduler import start_scheduler, stop_scheduler
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import time
import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3

from auth import authenticate, create_user, get_current_user, init_auth_db, issue_token

from storage import (init_db, save_market_snapshot, get_database_stats, get_connection, get_collection_runs, get_latest_market_context, save_ai_brief, get_latest_ai_brief)


OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen3:4b"
COINGECKO_URL = "https://api.coingecko.com/api/v3"

market_cache = {}
CACHE_SECONDS = 60

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_auth_db()
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
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    prompt: str


class ChatRequest(BaseModel):
    message: str
    conversation: list[dict] = []


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=24)
    password: str = Field(min_length=1, max_length=128)


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


@app.post("/api/auth/register")
async def auth_register(request: RegisterRequest):
    username = request.username.strip()
    try:
        user = create_user(username, request.password, role="member")
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="用户名已被注册")
    return {"status": "success", "user": user}


@app.post("/api/auth/login")
async def auth_login(request: LoginRequest):
    user = authenticate(request.username.strip(), request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "expires_in": 604800,
        "user": user,
    }


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"user": user}


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



async def call_ollama(prompt: str, timeout: int = 180):
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.2}}
        )
        response.raise_for_status()
        return response.json().get("response", "")


def build_market_prompt(coins):
    if not coins:
        raise HTTPException(status_code=409, detail="数据库暂无行情快照，请等待首次采集完成")
    lines = []
    for coin in coins:
        change = coin.get("price_change_24h")
        change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "N/A"
        lines.append(
            f"{coin.get('market_cap_rank') or '-'}. {str(coin.get('symbol') or '').upper()} "
            f"{coin.get('name')}: price=${coin.get('current_price')}, 24h={change_text}, "
            f"volume=${coin.get('total_volume')}"
        )
    return (
        "你是 Crypto Radar 的加密市场研究助手。请使用以下数据库行情快照生成中文市场简报。"
        "只描述数据支持的结论，不要编造技术指标、支撑阻力或实时新闻。按以下结构输出："
        "【市场概况】【核心资产】【异动观察】【风险提示】【观察清单】。"
        "明确说明数据来自 CoinGecko 快照、涨跌幅为24小时，不构成投资建议。\n\n"
        "行情数据：\n" + "\n".join(lines)
    )


@app.get("/api/ai/brief")
async def ai_latest_brief(user: dict = Depends(get_current_user)):
    return {"brief": get_latest_ai_brief(), "model": OLLAMA_MODEL}


@app.post("/api/ai/brief/generate")
async def ai_generate_brief(user: dict = Depends(get_current_user)):
    coins = get_latest_market_context(250)
    if not coins:
        raise HTTPException(status_code=409, detail="数据库暂无行情快照")
    snapshot_at = max((coin.get("captured_at") or "" for coin in coins), default=None)
    try:
        content = await call_ollama(build_market_prompt(coins), timeout=240)
        saved = save_ai_brief(content, OLLAMA_MODEL, snapshot_at)
        return {"brief": {**saved, "content": content, "source_snapshot_at": snapshot_at}}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama 请求失败：{exc}")


@app.post("/api/ai/chat")
async def ai_chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(message) > 4000:
        raise HTTPException(status_code=413, detail="单条问题最多 4000 字符")

    # 只取市值排名靠前的 30 个币种，减少每轮提示词长度。
    coins = get_latest_market_context(30)
    market_lines = []
    for coin in coins:
        change = coin.get("price_change_24h")
        change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "N/A"
        market_lines.append(
            f"{str(coin.get('symbol') or '').upper()}: "
            f"${coin.get('current_price')} ({change_text}/24h)"
        )

    # 保留最近 4 条消息，并限制单条历史长度。
    history = request.conversation[-4:]
    history_text = "\n".join(
        f"{'用户' if item.get('role') == 'user' else '助手'}：{str(item.get('content', ''))[:800]}"
        for item in history if item.get("role") in ("user", "assistant")
    )
    prompt = (
        "你是 Crypto Radar 内置的 Qwen3 加密市场助手。请用中文简洁回答，优先给结论和关键依据。"
        "结合最新数据库行情；数据未覆盖时坦诚说明。不要编造实时新闻、技术指标或交易所原生K线，"
        "区分事实、推断和风险，不承诺收益。\n\n"
        "最新行情（CoinGecko快照）：\n" + ("\n".join(market_lines) if market_lines else "暂无行情快照") +
        "\n\n最近对话：\n" + history_text + "\n\n用户当前问题：\n" + message
    )

    async def token_stream():
        try:
            timeout = httpx.Timeout(connect=10, read=240, write=30, pool=10)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": True,
                        "keep_alive": "10m",
                        "options": {
                            "temperature": 0.2,
                            "num_ctx": 2048,
                            "num_predict": 512
                        }
                    }
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
        except Exception as exc:
            yield f"\n\n[Qwen3 请求中断：{str(exc)}]"

    return StreamingResponse(
        token_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
