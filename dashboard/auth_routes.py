import hmac
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from dashboard.auth import (
    authenticate_user,
    create_session,
    get_session_user,
    register_user,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEXUS AI - Sign in</title>
<style>
body{font-family:Arial,sans-serif;background:#101827;color:#f3f4f6;
display:grid;place-items:center;min-height:100vh;margin:0}
main{width:min(380px,88vw);background:#1f2937;padding:28px;
border-radius:14px}
h1{margin-top:0}input,button{box-sizing:border-box;width:100%;
padding:12px;margin:8px 0;border-radius:7px;border:1px solid #475569}
input{background:#111827;color:white}button{cursor:pointer;
background:#2563eb;color:white;border:0;font-weight:bold}
#message{min-height:24px;color:#fca5a5}
</style>
</head>
<body>
<main>
<h1>NEXUS AI</h1>
<p>Sign in or create your account.</p>
<form id="authForm">
<input id="email" type="email" placeholder="Email address"
required maxlength="254">
<input id="password" type="password" placeholder="Password"
required minlength="12" maxlength="1024">
<button type="submit">Sign in</button>
<button type="button" id="register">Create account</button>
</form>
<p id="message" role="status"></p>
</main>
<script>
const email = document.getElementById("email");
const password = document.getElementById("password");
const message = document.getElementById("message");

async function submitAuth(path) {
    message.textContent = "Please wait...";
    try {
        const response = await fetch(path, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                email: email.value,
                password: password.value
            })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed.");
        }
        window.location.href = "/";
    } catch (error) {
        message.textContent = error.message;
    }
}

document.getElementById("authForm").addEventListener("submit", event => {
    event.preventDefault();
    submitAuth("/auth/login");
});
document.getElementById("register").addEventListener("click", () => {
    submitAuth("/auth/register");
});
</script>
</body>
</html>""")


SESSION_COOKIE = "nexus_session"
CSRF_COOKIE = "nexus_csrf"

IS_PRODUCTION = os.environ.get("NEXUS_ENV", "").lower() == "production"
COOKIE_SECURE = IS_PRODUCTION or (
    os.environ.get("NEXUS_COOKIE_SECURE", "").lower() == "true"
)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)


def current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    user = get_session_user(token)

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    return user


def verify_csrf(request: Request):
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get("X-CSRF-Token")

    if (
        not cookie_token
        or not header_token
        or not hmac.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")


def set_auth_cookies(response: Response, user_id: int):
    token = create_session(user_id)
    csrf = secrets.token_urlsafe(32)

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )

    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=60 * 60 * 24 * 7,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


@router.post("/register")
def register(credentials: Credentials, response: Response):
    try:
        user = register_user(credentials.email, credentials.password)
        set_auth_cookies(response, user["id"])
        return {"status": "REGISTERED", "user": user}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/login")
def login(credentials: Credentials, response: Response):
    user = authenticate_user(credentials.email, credentials.password)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    set_auth_cookies(response, user["id"])
    return {"status": "AUTHENTICATED", "user": user}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"user": user}


@router.post("/logout")
def logout(request: Request, response: Response):
    verify_csrf(request)

    token = request.cookies.get(SESSION_COOKIE)
    revoke_session(token)

    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        secure=COOKIE_SECURE,
        samesite="strict",
    )

    return {"status": "LOGGED_OUT"}
