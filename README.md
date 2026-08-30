# Epsilon (ε)

A purposefully vulnerable AI web application for teaching AI application
defense. Epsilon covers the OWASP Top 10 for LLM Applications (2026
edition): every vulnerability is exploitable — students see exactly how
an attack succeeds against the vulnerable state, then toggle to the
fixed state and see the same attack stopped by real framework controls.

Named after the differential privacy parameter ε — the mathematical
quantity that measures how much an AI system leaks. "Every epsilon of
defense matters."

> **This application is deliberately insecure by default.** The
> "vulnerable" state of each exercise contains real, exploitable
> weaknesses (prompt injection succeeds, secrets leak, agents burn
> unbounded resources). Run it locally, on loopback, for education
> only. Do not expose it to a network.

## Prerequisites

- **Docker** (Docker Desktop, or Docker Engine + Compose v2) — ~4 GB
  RAM available for containers.
- **Ollama** running on the host — Epsilon performs all model
  inference locally. Install from https://ollama.com then pull the two
  required models:

```bash
ollama pull nemotron-3-nano:4b      # chat model (~2.5 GB)
ollama pull embeddinggemma:latest   # embedding model (~300 MB)
```

Skipping the pulls is the #1 cause of failed first runs — the backend
will start, but every exercise will error with a model-not-found.

## Quick Start

```bash
# 1. Pull the required models (see Prerequisites)

# 2. Clone and start
git clone https://github.com/qfunction-ai/epsilon-release.git
cd epsilon-release
docker compose up -d --build

# 3. Open http://localhost:5173

# 4. Register a username and password.
#    The FIRST registered user becomes the admin.
#    Registration closes after the first user.
```

First build takes a few minutes (backend + frontend images). Subsequent
starts are fast. The first message you send to an exercise may take
30-60 seconds while the local model warms up.

## Architecture

Seven containers, all ports bound to `127.0.0.1` (loopback only):

| Service | Image | Port | What it does |
|---|---|---|---|
| frontend | built from `frontend/` | 5173 | React + Vite + TypeScript UI |
| backend | built from `backend/` | 8000 | FastAPI app: auth, sessions, vuln catalog, chat proxy |
| letta-local | `ghcr.io/qfunction-ai/letta-local:0.16.30` | 8283 | Agent platform fork with security controls (policy engine, canary filter, content validator) |
| postgres | `pgvector/pgvector:pg16` | 5432 | Users, sessions, events (+ vector storage) |
| redis | `redis:7-alpine` | 6379 | Cache |
| otel-collector | `otel/opentelemetry-collector-contrib` | 4317/4318 | Telemetry pipeline |
| jaeger | `jaegertracing/all-in-one` | 16686 | Trace UI (http://localhost:16686) |

The teaching corpus lives in `vulns/` — ten OWASP 2026 exercises, each
with vulnerable and fixed agent configurations, documents, and code
listings. Ollama runs on the host (outside docker compose) and is
reached via `host.docker.internal`.

## Using an Exercise

1. Pick a vulnerability from the sidebar (LLM01 through LLM10).
2. Read the **Overview** tab — the weakness, the attack, the defense.
3. Open the **Exploit** tab and click a suggested prompt (or type your
   own) to run the attack against the vulnerable state.
4. Toggle **Vulnerable / Fixed** at the top and run the same prompt —
   watch the framework controls stop it.
5. The **Code** tab shows the vulnerable and fixed implementations
   side by side; the **Defense** tab maps each control to the OWASP
   mitigation strategy it embodies.

## Updating

```bash
git pull
docker compose up -d --build
```

`docker compose up -d` **without** `--build` reuses stale images and
silently runs old code — always pass `--build` after pulling.

## Data Persistence

- `docker compose down` — stops containers, **keeps data** (users,
  chat history, agent memory live in named volumes).
- `docker compose down -v` — stops containers and **deletes all
  data**. Next `up` starts completely fresh: registration reopens,
  first new user becomes admin.

To reset just the exercises (keep your login), use the Reset chat
button in each exercise.

## Project Structure

```
epsilon-release/
├── frontend/          # React + Vite + TypeScript (source)
├── backend/           # FastAPI + SQLAlchemy (source, includes tests)
├── vulns/             # Teaching corpus: 10 OWASP 2026 exercises
│   └── 2026/
│       ├── index.yaml
│       └── llm01_prompt_injection/ ... llm10_improper_output/
├── docker-compose.yml
├── init-db.sql        # postgres init (pgvector extension)
└── otel-collector-config.yaml
```

Each exercise directory contains: `config.yaml` (tabs, prompts,
defense references), `vulnerable.yaml` / `fixed.yaml` (agent
configurations), `vulnerable_code` / `fixed_code` (Code tab listings),
and `documents/` (retrieval content — some deliberately poisoned;
that is the lesson).

## Troubleshooting

**Every exercise errors / model not found.** The two Ollama models
were not pulled. Run the two `ollama pull` commands from Prerequisites.

**Backend cannot reach Ollama.** Verify Ollama is running on the host
(`ollama list` works). On Linux, `host.docker.internal` may not
resolve — set `OLLAMA_URL=http://<your-host-IP>:11434` in the backend
environment of `docker-compose.yml`.

**Login does not persist (Safari, plain HTTP).** The auth cookie
carries the `Secure` flag in release mode. Chrome and Firefox treat
`http://localhost` as trustworthy; older Safari versions may not. Set
`DEV_MODE=true` in the backend environment of `docker-compose.yml` for
local-only deployments if login loops on Safari.

**Registration says it is closed.** The first registered user is the
admin and registration closes immediately after. To re-open it, wipe
the data: `docker compose down -v` (then re-register on next start).

**Stale code after `git pull`.** You skipped `--build`. See Updating.

**Want a completely fresh instance.** `docker compose down -v && docker
compose up -d --build`.

## Security Notes

- All service ports bind to `127.0.0.1` — nothing is reachable from
  other machines.
- The agent sandbox (Landlock) restricts file tool access inside
  letta-local; the version pin in `docker-compose.yml` carries a
  comment history of what each LettaLocal version fixed.
- The `execute_code` tool in the vulnerable state is real `exec()` with
  zero validation — confined to the container, but treat it as hostile
  by design. That is what LLM03 teaches.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
