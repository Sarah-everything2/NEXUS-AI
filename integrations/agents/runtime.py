import inspect
import json
import os
from pathlib import Path


class AgentRuntime:
    def __init__(self, config_path=None, environ=None):
        self.environ = os.environ if environ is None else environ
        self.config_path = Path(config_path) if config_path else (
            Path(__file__).resolve().parents[2] / "config" / "agent_runtime.json"
        )
        self.config = {
            "provider": "ollama",
            "fallback_to_ollama": True,
            "openai": {
                "enabled": False,
                "model": "gpt-5-mini",
                "max_turns": 2
            }
        }
        if self.config_path.exists():
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Agent Runtime config must be an object.")
            self.config.update({k:v for k,v in loaded.items() if k != "openai"})
            if isinstance(loaded.get("openai"), dict):
                self.config["openai"].update(loaded["openai"])

        if self.config["provider"] not in ("ollama", "openai"):
            raise ValueError("Unsupported Agent Runtime provider.")
        openai = self.config["openai"]
        if not isinstance(openai.get("enabled"), bool):
            raise ValueError("openai.enabled must be true or false.")
        if not isinstance(self.config.get("fallback_to_ollama"), bool):
            raise ValueError("fallback_to_ollama must be true or false.")
        if not isinstance(openai.get("model"), str) or not openai["model"].strip():
            raise ValueError("openai.model must be a non-empty string.")
        turns = openai["max_turns"]
        if not isinstance(turns, int) or isinstance(turns, bool) or not 1 <= turns <= 10:
            raise ValueError("max_turns must be between 1 and 10.")

    async def generate(self, ollama_generate, messages):
        cfg = self.config
        if cfg["provider"] != "openai" or not cfg["openai"]["enabled"]:
            return await self._ollama(ollama_generate, messages)

        if not self.environ.get("OPENAI_API_KEY"):
            return await self._fallback(
                ollama_generate, messages, "OPENAI_API_KEY is missing."
            )

        try:
            return await self._openai(messages)
        except Exception as exc:
            return await self._fallback(
                ollama_generate, messages,
                f"OpenAI runtime failed: {type(exc).__name__}: {exc}"
            )

    async def _fallback(self, callback, messages, reason):
        if self.config.get("fallback_to_ollama", True):
            return await self._ollama(callback, messages)
        raise RuntimeError(reason)

    @staticmethod
    async def _ollama(callback, messages):
        result = callback(messages)
        return await result if inspect.isawaitable(result) else result

    async def _openai(self, messages):
        from agents import Agent, Runner

        system = []
        history = []
        if isinstance(messages, dict):
            message_items = [messages]
        elif isinstance(messages, list):
            message_items = messages
        else:
            message_items = [{"role": "user", "content": str(messages)}]

        for item in message_items:
            if not isinstance(item, dict):
                continue
            role = item.get("role", "user")
            content = item.get("content", "")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            if role in ("system", "developer"):
                system.append(content)
            elif role in ("user", "assistant"):
                history.append({"role": role, "content": content})

        agent = Agent(
            name="NEXUS Assistant",
            instructions="\n\n".join(system) or "You are a helpful assistant.",
            model=self.config["openai"]["model"],
            tools=[]
        )
        result = await Runner.run(
            agent,
            input=history or "Hello.",
            max_turns=self.config["openai"]["max_turns"]
        )
        return str(result.final_output)
