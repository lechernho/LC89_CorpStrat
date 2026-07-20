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
    base_url = f"https://api.platform.atko.ai/{os.environ['IDDB_TENANT']}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{base_url}/rest/v1/notes",
            headers={"apikey": resource_key, "Authorization": f"Bearer {resource_key}"},
            params={"select": "*", "order": "date.desc"},
        )
        if resp.status_code >= 400:
            return JSONResponse(
                {"error": "upstream_error", "status": resp.status_code, "body": resp.text[:1000]},
                status_code=502,
            )
        return JSONResponse(resp.json())


@app.get("/api/debug-egress")
async def debug_egress():
    """Temporary diagnostic route - isolates proxy-env misconfiguration from
    platform-level egress blocking. Remove once the ConnectTimeout issue is resolved."""
    proxy_vars = {
        k: bool(os.environ.get(k))
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                  "http_proxy", "https_proxy", "all_proxy", "no_proxy"]
    }

    async def try_connect(url, trust_env):
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=trust_env) as client:
                resp = await client.get(url)
                return {"ok": True, "status": resp.status_code}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return JSONResponse({
        "proxy_env_vars_set": proxy_vars,
        "unrelated_host_default": await try_connect("https://1.1.1.1", True),
        "unrelated_host_no_proxy_env": await try_connect("https://1.1.1.1", False),
        "platform_host_no_proxy_env": await try_connect("https://api.platform.atko.ai/", False),
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
