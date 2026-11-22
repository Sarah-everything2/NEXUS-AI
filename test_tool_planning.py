import asyncio
from brain.ollama_client import OllamaClient

async def main():
    ai = OllamaClient()
    response = await ai.generate([
        {
            "role": "user",
            "content": 'Return only JSON: {"actions":[{"tool":"mt5_get_account","arguments":{}}]}'
        }
    ])
    print("MODEL RESPONSE:")
    print(response)

asyncio.run(main())
