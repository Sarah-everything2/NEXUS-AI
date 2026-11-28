import json
import tempfile
import unittest
from pathlib import Path

from integrations.agents import AgentRuntime


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "agent_runtime.json"

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def ollama(self, messages):
        return "ollama-response"

    async def test_default_uses_ollama(self):
        runtime = AgentRuntime(self.path, environ={})
        result = await runtime.generate(self.ollama, [{"role": "user", "content": "Hi"}])
        self.assertEqual(result, "ollama-response")

    async def test_openai_without_key_falls_back(self):
        self.path.write_text(json.dumps({
            "provider": "openai",
            "fallback_to_ollama": True,
            "openai": {"enabled": True, "max_turns": 2}
        }), encoding="utf-8")
        runtime = AgentRuntime(self.path, environ={})
        result = await runtime.generate(self.ollama, "Hi")
        self.assertEqual(result, "ollama-response")

    async def test_openai_without_key_can_fail_closed(self):
        self.path.write_text(json.dumps({
            "provider": "openai",
            "fallback_to_ollama": False,
            "openai": {"enabled": True, "max_turns": 2}
        }), encoding="utf-8")
        runtime = AgentRuntime(self.path, environ={})
        with self.assertRaises(RuntimeError):
            await runtime.generate(self.ollama, "Hi")


if __name__ == "__main__":
    unittest.main()
