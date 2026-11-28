from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from core.settings import load_settings
from core.agent import NexusAgent
from agents.manager import list_agents
from skills.manager import list_skills
from tools.manager import get_available_tools

app = FastAPI(title="NEXUS AI Control Centre")

# Dashboard authentication gate.
from dashboard.auth import get_session_user

_PUBLIC_PATHS = {
    "/auth/login",
    "/auth/register",
    "/manifest.webmanifest",
    "/service-worker.js",
    "/pwa-icon.svg",
}

@app.middleware("http")
async def require_dashboard_session(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    token = request.cookies.get("nexus_session")
    user = get_session_user(token)

    if user is None:
        path = request.url.path

        if path.startswith("/api/") or path.startswith("/auth/"):
            return JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
            )

        return RedirectResponse("/auth/login", status_code=303)

    request.state.current_user = user

    return await call_next(request)


# NEXUS PWA PATCH: explicit dashboard-shell assets only.
from pathlib import Path
_PWA_STATIC = Path(__file__).resolve().parent / "static"

@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest():
    return FileResponse(
        _PWA_STATIC / "manifest.webmanifest",
        media_type="application/manifest+json"
    )

@app.get("/service-worker.js", include_in_schema=False)
def pwa_service_worker():
    return FileResponse(
        _PWA_STATIC / "service-worker.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )

@app.get("/pwa-icon.svg", include_in_schema=False)
def pwa_icon():
    return FileResponse(
        _PWA_STATIC / "pwa-icon.svg",
        media_type="image/svg+xml"
    )


class ChatRequest(BaseModel):
    message: str


@app.get("/api/status")
def status():
    settings = load_settings()

    return {
        "name": "NEXUS AI",
        "version": settings["version"],
        "model_configured": bool(settings["model"]),
        "memory": settings["memory_enabled"],
        "agents": len(list_agents()),
        "skills": len(list_skills()),
        "tools": len(get_available_tools()),
        "approval_required": settings["require_approval"]
    }


@app.get("/api/skills")
def skills():
    return {"skills": list_skills()}


@app.get("/api/agents")
def agents():
    return {"agents": list_agents()}


@app.get("/api/tools")
def tools():
    return {"tools": get_available_tools()}


@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):

    if not request.message.strip():
        raise HTTPException(400, "Message cannot be empty.")

    try:
        user = http_request.state.current_user
        agent = NexusAgent(user_id=user["id"], user_role=user["role"])
        answer = await agent.ask(request.message)

        return {"reply": answer}

    except Exception as error:
        raise HTTPException(500, str(error))
class SpecialistRequest(BaseModel):
    skill_name: str
    message: str


@app.post("/api/specialist")
async def specialist(request: SpecialistRequest, http_request: Request):
    if request.skill_name not in list_skills():
        raise HTTPException(404, "Unknown skill.")

    try:
        user = http_request.state.current_user
        agent = NexusAgent(user_id=user["id"], user_role=user["role"])
        reply = await agent.ask_specialist(
            request.skill_name,
            request.message
        )
        return {"reply": reply}
    except Exception as error:
        raise HTTPException(500, str(error))


@app.get("/", response_class=HTMLResponse)
def dashboard():

    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0b1020">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="NEXUS AI">
<link rel="apple-touch-icon" href="/pwa-icon.svg">

<title>NEXUS AI Control Centre</title>

<style>
body {
    background: #0b1020;
    color: #e5e7eb;
    font-family: Arial;
    margin: 0;
}

header {
    background: #111a30;
    padding: 25px;
}

h1, h3 {
    color: #38bdf8;
}

main {
    padding: 25px;
    max-width: 1100px;
    margin: auto;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(220px,1fr));
    gap: 15px;
}

.card {
    background: #151f35;
    border: 1px solid #263653;
    border-radius: 10px;
    padding: 20px;
}

li {
    padding: 7px;
}

#chatbox {
    height: 300px;
    overflow-y: auto;
    background: #080e1c;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 15px;
}

.message {
    padding: 10px;
    margin: 8px 0;
    border-radius: 8px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}

.user {
    background: #164e63;
}

.assistant {
    background: #263653;
}

input {
    width: 75%;
    padding: 13px;
    background: #111a30;
    color: white;
    border: 1px solid #38bdf8;
    border-radius: 6px;
}

button {
    padding: 13px 20px;
    background: #0284c7;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
}

button:disabled {
    opacity: 0.5;
}

footer {
    margin: 40px;
    text-align: center;
    color: #64748b;
}
</style>
</head>

<body>

<header>
<h1>NEXUS AI</h1>
<p>Personal AI Agent â€” Central Control Centre</p>
<span>â— DASHBOARD ONLINE</span>
</header>

<main>

<h2>System Overview</h2>
<div class="grid" id="overview">Loading...</div>

<h2>Specialist Agents</h2>
<div class="grid" id="agents"></div>

<h2>Skills Engine</h2>
<div class="card"><ul id="skills"></ul></div>

<h2>Web Research</h2>
<div class="card">
    <input id="researchQuery" placeholder="What should NEXUS research?" style="width:75%">
    <button id="researchButton" type="button">SEARCH</button>
    <p id="researchStatus">Ready</p>
    <div id="researchResults"></div>
</div>
<h2>Available Tools</h2>
<div class="card"><ul id="tools"></ul></div>

<h2>NEXUS AI Chat</h2>

<div class="card">

    <div id="chatbox">
        <div class="message assistant">
            NEXUS AI: Welcome! How can I help you?
        </div>
    </div>

    <form id="chatform">
        <input
            id="message"
            type="text"
            placeholder="Ask NEXUS AI something..."
            autocomplete="off"
            required
        >
        <button id="send" type="submit">SEND</button>
    </form>

    <p id="chatstatus">Ready</p>

</div>

</main>

<footer>
NEXUS AI | Local Control Centre
</footer>

<script>

async function loadDashboard() {

    try {

        const s = await (await fetch("/api/status")).json();

        document.getElementById("overview").innerHTML = `
        <div class="card"><h3>Skills</h3><h2>${s.skills}</h2></div>
        <div class="card"><h3>Agents</h3><h2>${s.agents}</h2></div>
        <div class="card"><h3>Tools</h3><h2>${s.tools}</h2></div>
        <div class="card"><h3>AI Model</h3>${s.model_configured ? "Configured" : "Not configured"}</div>
        <div class="card"><h3>Memory</h3>${s.memory ? "Enabled" : "Disabled"}</div>
        <div class="card"><h3>Safety</h3>${s.approval_required ? "Approval required" : "Approval disabled"}</div>`;

        const a = await (await fetch("/api/agents")).json();

        document.getElementById("agents").innerHTML =
            Object.entries(a.agents).map(([id, agent]) =>
                `<div class="card">
                <h3>${agent.name}</h3>
                <p>${id}</p>
                <p>${agent.skills.join(", ")}</p>
                </div>`
            ).join("");

        const sk = await (await fetch("/api/skills")).json();

        document.getElementById("skills").innerHTML =
            sk.skills.map(x => `<li>${x}</li>`).join("");

        const t = await (await fetch("/api/tools")).json();

        document.getElementById("tools").innerHTML =
            t.tools.map(x => `<li>${x}</li>`).join("");

    } catch (error) {
        console.error(error);
    }
}


function addMessage(text, role) {

    const box = document.getElementById("chatbox");
    const message = document.createElement("div");

    message.className = "message " + role;
    message.textContent = text;

    box.appendChild(message);
    box.scrollTop = box.scrollHeight;
}


document.getElementById("chatform").addEventListener(
    "submit",
    async function(event) {

        event.preventDefault();

        const input = document.getElementById("message");
        const button = document.getElementById("send");
        const status = document.getElementById("chatstatus");

        const message = input.value.trim();

        if (!message) return;

        addMessage("YOU: " + message, "user");

        input.value = "";
        button.disabled = true;
        status.textContent = "NEXUS AI is thinking...";

        try {

            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: message
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Chat request failed.");
            }

            addMessage("NEXUS AI: " + data.reply, "assistant");

            status.textContent = "Response received.";

        } catch (error) {

            addMessage("ERROR: " + error.message, "assistant");
            status.textContent = "Connection or AI error.";

        } finally {

            button.disabled = false;
            input.focus();

        }
    }
);

document.getElementById("researchButton").addEventListener("click", async () => {
    const query = document.getElementById("researchQuery").value.trim();
    const status = document.getElementById("researchStatus");
    const results = document.getElementById("researchResults");
    if (!query) return;
    status.textContent = "Researching...";
    try {
        const r = await fetch("/api/research/search", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({query: query, count: 5})
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || "Search failed");
        results.innerHTML = data.results.map(x =>
            `<p><a href="${x.url}" target="_blank" rel="noopener">${x.title}</a><br>${x.snippet || ""}</p>`
        ).join("");
        status.textContent = "Found " + data.results.length + " results.";
    } catch (e) {
        status.textContent = e.message;
    }
});
loadDashboard();

</script>

<script>
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/service-worker.js")
            .catch(error => console.warn(
                "NEXUS service worker registration failed:", error
            ));
    });
}
</script>
</body>
</html>
""")


from dashboard.workspace import router as workspace_router
app.include_router(workspace_router)
from dashboard.research import router as research_router
app.include_router(research_router)


from dashboard.auth_routes import router as auth_router
app.include_router(auth_router)
