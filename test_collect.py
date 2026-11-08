import asyncio
from main import get_market_data
from storage import init_db, save_market_snapshot, get_database_stats

async def main():
    print("1. 初始化数据库...")
    init_db()

    print("2. 正在从 CoinGecko 获取行情...")
    coins = await get_market_data("usd", 250, 1)

    print(f"3. 获取到 {len(coins)} 个币种")

    print("4. 正在写入 SQLite...")
    result = save_market_snapshot(coins, currency="usd")
    print("写入结果：", result)

    print("5. 数据库统计：")
    print(get_database_stats())

asyncio.run(main())
