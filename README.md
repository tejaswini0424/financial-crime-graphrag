# Financial Crime Intelligence & Investigation Platform

Public deployment: **https://financial-crime-graphrag.vercel.app**. Anyone can create an account using their own credentials. Production uses a browser dashboard served by FastAPI and a dedicated Neon Postgres database on the free plan. The Streamlit dashboard remains available locally. Production accounts are separate from local SQLite accounts.

To update the linked Vercel project from this workspace:

```powershell
.venv\Scripts\python.exe scripts\prepare_vercel.py
$env:NODE_USE_SYSTEM_CA='1'
npx.cmd --yes vercel deploy --prod --yes --cwd deploy-output
```

The packaging script excludes local databases, credentials, tests, Streamlit and large scientific dependencies. Cloud passage retrieval uses a lightweight TF-IDF cosine implementation; local installations use scikit-learn. Database credentials are supplied through Vercel environment variables. Never commit `.env` files. The generated package is ignored by Git; its Vercel project link stays in `deploy-output/.vercel` across rebuilds. Public registration, sign-in, graph retrieval, persistent case storage, logout and unauthenticated access protection were verified against production.

Complete local educational demonstration using Streamlit, FastAPI, SQLite/SQLAlchemy, NetworkX, scikit-learn and Plotly. Create your own account; each account receives a private synthetic dataset (256 transactions, 30 accounts) and four educational knowledge passages. No API keys or preset credentials.

## Run on Windows

```powershell
python -m venv .venv
python -m pip --python .venv/Scripts/python.exe install -r requirements.txt
.\start.ps1
```

Open http://localhost:8502. In a second terminal run `./start.ps1 -Api` for the REST service at http://localhost:8010 and interactive API documentation at http://localhost:8010/docs. The dashboard and API share the same service functions and database; the dashboard does not require a separate API process. These ports avoid other applications already using 8000 and 8501 on this machine.

## Demonstration

1. Create any nonempty username and password. No complexity rules apply.
2. Review overview metrics, transaction volume, categories and account risk.
3. Open Detection center. Adjust thresholds and inspect reasons and transaction IDs.
4. Explore ACC-003, ACC-004 and ACC-005 in Network explorer; use directed path search.
5. In GraphRAG engine ask: `Investigate circular transfers and rapid movement involving ACC-003 and ACC-005.`
6. Inspect graph relationships, transaction evidence, retrieved passages and source references. Download Markdown and JSON, save a case, then update its review status.
7. Import the downloadable CSV template after assigning new transaction IDs. Add/delete records or export any filtered selection.

## How GraphRAG works

Transaction edges form a directed multigraph. The knowledge graph adds synthetic individual/organization owners, beneficiary entities, locations, transaction nodes, rule patterns and documents. Explicit account anchors (or category-matched flagged anchors) seed bounded graph traversal. Retrieved neighborhood transactions and rule explanations expand the TF-IDF document query; graph-linked documents receive a ranking boost. A deterministic local generator produces a cited investigation brief with transaction IDs and actions. It does not pretend to be an external LLM. Unknown or unspecified accounts may fall back to top flagged anchors, which are explicitly shown in the result. Owner nodes are synthetic demonstration metadata.

## Detection rules

Only completed/settled/successful flows are analyzed. Configurable rules cover high values, near-threshold splitting, rapid onward movement, daily outgoing volume, common beneficiaries, and directed cycles up to three accounts. Daily windows use UTC. Rapid movement compares outgoing amounts to 80–120% of incoming amounts. Splitting uses 80–100% of an illustrative threshold. Cycles indicate topology; temporal causality is not asserted. Rule scores prioritize leads and are not statistical probabilities. Full formulas and scores appear in the UI.

## REST API

Register with `POST /auth/register`, then `POST /auth/login`; send `Authorization: Bearer <access_token>` for protected routes. Transactions support GET, bulk POST (JSON array), and DELETE by transaction ID. Other routes: `/detections`, `/network`, `/knowledge`, `/investigate`, `/cases`, `/auth/me`, `/auth/logout`. Case status supports PATCH. OpenAPI documents exact payloads.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Passwords use salted scrypt; only hashes of random 12-hour session tokens are stored. Logout revokes the token. All data queries scope to the logged-in user. Browser refresh may require signing in again because tokens stay in Streamlit session state. Database: `data/platform.db` (excluded from Git).

## Deployment and scope

This is a functional research/demo application, not a certified compliance product. Regulatory passages are manually supplied educational paraphrases, with official reference URLs; they are not live legal guidance. Amounts are illustrative currency units. Reports are Markdown/JSON. No external generative model is required. The public Vercel deployment uses HTTPS and persistent Postgres; local SQLite is never deployed. For real operational data, add backups, login/registration rate limiting, monitoring and resource limits. Do not expose the raw SQLite file. Streamlit Community Cloud can run `app.py` with `requirements.txt`, but ephemeral storage may reset accounts/data unless a persistent DATABASE_URL is configured.
