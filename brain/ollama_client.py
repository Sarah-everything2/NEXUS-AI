import httpx
from core.settings import load_settings


class OllamaClient:

    def __init__(self):
        settings = load_settings()
        self.base_url = settings["ollama_url"].rstrip("/")
        self.model = settings["model"]

    async def generate(self, messages):

        if not self.model:
            raise ValueError(
                "No AI model configured. Configure a model first."
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )

            response.raise_for_status()

            result = response.json()

            return result["message"]["content"]
