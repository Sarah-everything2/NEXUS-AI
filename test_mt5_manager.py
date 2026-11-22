import asyncio
from tools.manager import execute_tool

async def main():
    tests = [
        ("mt5_get_account", {}),
        ("mt5_get_price", {"symbol": "XAUUSD"}),
        ("mt5_get_positions", {}),
        ("mt5_get_history", {}),
        ("mt5_get_strategy_signal", {})
    ]

    for name, arguments in tests:
        result = await execute_tool(name, **arguments)
        print(f"{name}: {result.get('status')}")

asyncio.run(main())
