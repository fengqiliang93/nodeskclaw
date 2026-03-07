[中文](README.zh-CN.md)

# DeskClaw

**Your AI workforce, orchestrated.** Deploy, manage, and scale AI agents on Kubernetes -- from a single pane of glass.

DeskClaw is a visual orchestration platform for AI employees. It organizes multiple AI Agents into collaborative teams through Cyber Workspaces, equips them with a Gene capability system, and enables one-click deployment, real-time monitoring, and elastic scaling on K8s clusters.

## Highlights

- **Cyber Workspace** -- Hexagonal topology workspace where AI employees auto-collaborate, share a blackboard, and publish tasks
- **Gene System** -- Modular capability marketplace for hot-loading skills onto Agents, with support for private enterprise genes
- **One-Click Deploy** -- End-to-end visual deployment pipeline with SSE real-time progress streaming
- **Multi-Cluster Management** -- Cross-cluster instance orchestration, health checks, and elastic scaling
- **Feishu SSO** -- Enterprise-grade authentication with automatic org structure sync

## CE / EE

Dual-edition architecture: Community Edition / Enterprise Edition.

| | CE (Community) | EE (Enterprise) |
|---|---|---|
| License | Apache 2.0 | Commercial |
| Features | Instance deploy, cluster management, log monitoring, gene marketplace | All of CE + multi-org, billing, advanced audit |
| Code | This repository | Private `ee/` directory |

Runtime auto-detection via `FeatureGate` -- if `ee/` exists it runs as EE, otherwise CE. Feature registry defined in `features.yaml`.

**Technical implementation**: Backend Factory abstraction + Hook event bus; Frontend Stub + Vite Alias Override.

## Architecture

```
DeskClaw/
├── nodeskclaw-portal/             # User Portal -- Vue 3 + Tailwind CSS
├── nodeskclaw-frontend/           # Admin Console -- Vue 3 + shadcn-vue + Tailwind CSS
├── nodeskclaw-backend/            # API Server -- Python 3.12 + FastAPI + SQLAlchemy
├── nodeskclaw-llm-proxy/          # LLM Proxy -- Go
├── nodeskclaw-artifacts/          # Docker images & deploy manifests
├── openclaw-channel-nodeskclaw/   # Workspace Agent channel plugin
├── features.yaml                  # CE/EE feature registry
├── ee/                            # Enterprise Edition (private)
├── openclaw/                      # DeskClaw runtime source (external)
└── vibecraft/                     # VibeCraft source (external)
```

## i18n

Full-stack internationalization covering Portal, Admin, and Backend.

- Language detection: `zh*` -> `zh-CN`, `en*` -> `en-US`, fallback `en-US`
- Error display: prefer `message_key` local translation, fall back to `message` when missing
- Backend contract: `code` + `error_code` + `message_key` + `message` + `data`

## Quick Start

### Prerequisites

| Dependency | |
|---|---|
| Python >= 3.12 + [uv](https://docs.astral.sh/uv/) | Backend runtime & package manager |
| Node.js >= 18 + npm | Frontend runtime |
| PostgreSQL | Database |
| Feishu App | SSO (App ID + App Secret) |

### 1. Configure

```bash
cd nodeskclaw-backend
cp .env.example .env
# Edit .env -- fill in the required values below
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `JWT_SECRET` | JWT signing key |
| `ENCRYPTION_KEY` | KubeConfig AES key (32-byte base64) |
| `FEISHU_APP_ID` | Feishu App ID |
| `FEISHU_APP_SECRET` | Feishu App Secret |
| `FEISHU_REDIRECT_URI` | `http://localhost:5173/api/v1/auth/feishu/callback` |

### 2. Backend

```bash
cd nodeskclaw-backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

API at `http://localhost:8000` | Swagger at `http://localhost:8000/docs` | Auto-migration on first boot.

### 3. Frontend

```bash
cd nodeskclaw-frontend
npm install && npm run dev
```

Portal at `http://localhost:5173` | `/api` and `/stream` auto-proxy to backend.

### 4. Go

Open `http://localhost:5173`, sign in with Feishu.

> Feishu redirect URL: `http://localhost:5173/api/v1/auth/feishu/callback`

## Documentation

| | |
|---|---|
| [Backend](nodeskclaw-backend/README.md) | API overview, directory layout, env vars |
| [Artifacts](nodeskclaw-artifacts/README.md) | DeskClaw image build & Dockerfile |
| [Channel Plugin](openclaw-channel-nodeskclaw/README.md) | Workspace agent collaboration plugin |

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE)
