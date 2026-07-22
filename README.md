# Corp Strategy Knowledge Graph — OAP deployment

FastAPI app hosted on OAP (`lc89-corpstrat` app, tenant `knowledgegraph`),
serving the Gartner/IDC notes knowledge base as a browsable SPA.

Live at: https://lc89-corpstrat.knowledgegraph.platform.atko.ai/

## Architecture

- `main.py` — serves `Index.html` as static HTML at `/`. That's it. It does
  **not** proxy any data calls — see below for why.
- `Index.html` — the frontend SPA. Fetches notes **directly from PostgREST
  in the browser**, using the tenant's `anon` API key:
  ```js
  fetch('https://knowledgegraph.platform.atko.ai/rest/v1/notes?select=*&order=date.desc', {
    headers: { apikey: ANON_KEY, Authorization: `Bearer ${ANON_KEY}` },
  })
  ```
- Access to the page itself is gated by OAP's gateway-level "Specific users"
  access policy — not by any app-level login code.

## Why the browser fetches data directly, not the backend

This pod's own outbound network egress to `platform.atko.ai` is broken —
`httpx.ConnectTimeout` on every call, a hairpin/self-loop routing failure in
OAP's own networking (this pod, running inside OAP's cluster, can't reach
OAP's own public gateway hostname, while it reaches unrelated external hosts
fine). Reported to `#okta-app-platform`, unresolved as of 2026-07-22 despite
multiple follow-ups.

Since external clients — including a normal browser — reach the same host
without any problem, the fix was to move the data fetch out of the pod
entirely and have the frontend call PostgREST directly.

**Deliberate tradeoff:** the gateway access policy still gates who can load
the page at all, but the notes data itself is now protected only by the
`anon` key + Row Level Security, not by that same policy. Anyone who
captures the key could keep reading notes even if their gateway access is
later revoked. This is the standard, intended OAP pattern for public-read
data — acceptable here, but don't copy this pattern for data that needs
per-user access control; that needs a real token-exchange/JWT auth flow
instead.

## Database setup required for this to work

```sql
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "notes_public_read" ON notes FOR SELECT USING (true);
GRANT SELECT ON knowledgegraph.notes TO knowledgegraph_anon;
```

RLS + policy alone is **not** sufficient — PostgREST also requires an
explicit `GRANT` on the tenant's `anon` Postgres role, or every request
403s with `IDDB_GRANT_MISSING` even with a correct policy in place.

## Gotcha: don't trust API key display names

The OAP dashboard's API Keys list can show a key literally named/described
as "anon" whose actual **ROLE column reads `resource`** (wrong Postgres
role entirely). Always check the ROLE badge and key prefix (`iddb_anon_...`
vs `iddb_resourc_...`), never the display name, before embedding a key
client-side.

## Deploying

Push to `main` on `https://github.com/lechernho/LC89_CorpStrat` — OAP is
configured to auto-redeploy on push (~60-90s).

## Data sync

Notes are populated into the `notes` table via `sync_notes_to_oap.py`
(in the parent `GartnerVault` repo, not this one) — run that after adding
new notes to the source markdown.

See the `oap-deploy` skill (`~/.claude/skills/oap-deploy/SKILL.md`) for the
full incident history and platform-level gotchas hit while building this.
