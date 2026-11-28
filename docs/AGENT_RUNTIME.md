# NEXUS AI Agent Runtime

NEXUS uses Ollama by default. OpenAI Agents SDK support is optional.

## Default setup
No additional installation or API key is required.

## Optional OpenAI setup
Install the optional dependency:

    .\.venv\Scripts\python.exe -m pip install -r requirements-agents-openai.txt

Set OPENAI_API_KEY in your environment. Never commit API keys.

Copy config/agent_runtime.example.json to config/agent_runtime.json.
Set provider to openai and openai.enabled to true.

## Safety
- Ollama remains the default provider.
- OpenAI is disabled by default.
- Missing keys or provider failures fall back to Ollama when configured.
- Set fallback_to_ollama to false to fail closed.
- The external agent receives no NEXUS or MCP tools.
- Local runtime configuration must not be committed.
- No trading, publishing, or consequential actions are enabled by this integration.
