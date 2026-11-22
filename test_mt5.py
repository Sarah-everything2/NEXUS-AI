import asyncio
from integrations.mt5.client import get_account, get_price, get_positions, get_history, get_strategy_signal

async def main():
    checks = await asyncio.gather(
        get_account(),
        get_price(),
        get_positions(),
        get_history()
    )
    for name, result in zip(["ACCOUNT", "PRICE", "POSITIONS", "HISTORY"], checks):
        print(f"{name}: {result['status']}")
    print("STRATEGY:", get_strategy_signal()["status"])

asyncio.run(main())
