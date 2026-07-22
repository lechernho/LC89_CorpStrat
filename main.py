"""
GartnerVault OAP app: serves Index.html. The frontend fetches notes directly
from PostgREST using the anon key + RLS, rather than via a server-side proxy -
this pod's own outbound egress to platform.atko.ai is broken (platform-side
hairpin routing issue, reported to #okta-app-platform, unresolved).
Access to this page is gated entirely by OAP's gateway-level "Specific users"
access policy (viewer relation on the app) - no app-level login layer, since
that depended on OAuth env vars that aren't injected for UI-created apps and
caused a crash loop on startup.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

INDEX_HTML = (Path(__file__).parent / "Index.html").read_text(encoding="utf-8")

app = FastAPI()


@app.get("/")
async def index():
    return HTMLResponse(INDEX_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
