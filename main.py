"""
GartnerVault OAP app: serves Index.html and proxies /api/notes to Postgres.
Gated behind OAP's native OIDC login (public/PKCE client — no client secret
is provisioned via env, so authorize_redirect uses code_challenge_method=S256).
"""

import os
from pathlib import Path

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

INDEX_HTML = (Path(__file__).parent / "Index.html").read_text(encoding="utf-8")

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET_KEY", os.urandom(32).hex()),
)

oauth = OAuth()
oauth.register(
    name="oap",
    client_id=os.environ["IDDB_OAUTH_CLIENT_ID"],
    server_metadata_url=os.environ["IDDB_OIDC_DISCOVERY_URL"],
    client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
)


def logged_in(request: Request) -> bool:
    return "user" in request.session


@app.get("/login")
async def login(request: Request):
    return await oauth.oap.authorize_redirect(request, os.environ["IDDB_OAUTH_REDIRECT_URI"])


@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.oap.authorize_access_token(request)
    request.session["user"] = token.get("userinfo") or {}
    return RedirectResponse(request.session.pop("next", "/"))


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


@app.get("/")
async def index(request: Request):
    if not logged_in(request):
        request.session["next"] = "/"
        return RedirectResponse("/login")
    return HTMLResponse(INDEX_HTML)


@app.get("/api/notes")
async def api_notes(request: Request):
    if not logged_in(request):
        return JSONResponse({"error": "not authenticated"}, status_code=401)

    resource_key = os.environ["IDDB_RESOURCE_KEY"]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{os.environ['IDDB_API_URL']}/rest/v1/notes",
            headers={"apikey": resource_key, "Authorization": f"Bearer {resource_key}"},
            params={"select": "*", "order": "date.desc"},
        )
        resp.raise_for_status()
        return JSONResponse(resp.json())
