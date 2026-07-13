"""
GartnerVault OAP app: serves Index.html and proxies /api/notes to Postgres.
Access is gated entirely by OAP's gateway-level "Specific users" access
policy (viewer relation on the app) - no app-level login layer, since that
depended on OAuth env vars that aren't injected for UI-created apps and
caused a crash loop on startup.
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

INDEX_HTML = (Path(__file__).parent / "Index.html").read_text(encoding="utf-8")

app = FastAPI()


@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/api/notes")
async def api_notes():
    resource_key = os.environ["IDDB_RESOURCE_KEY"]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{os.environ['IDDB_API_URL']}/rest/v1/notes",
            headers={"apikey": resource_key, "Authorization": f"Bearer {resource_key}"},
            params={"select": "*", "order": "date.desc"},
        )
        resp.raise_for_status()
        return JSONResponse(resp.json())
