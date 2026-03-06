# DeskClaw

**Your AI workforce, orchestrated.** Deploy, manage, and scale AI agents on Kubernetes — from a single pane of glass.

DeskClaw 是 AI 员工的可视化编排平台。通过赛博办公室（Cyber Workspace）将多个 AI Agent 组织为协作团队，赋予基因（Gene）能力体系，在 K8s 集群上一键部署、实时监控、弹性伸缩。

## Highlights

- **赛博办公室** — 六边形拓扑工作区，AI 员工自动协作、共享黑板、发布任务
- **基因系统** — 模块化能力市场，为 Agent 热装载技能，支持企业私有化基因
- **一键部署** — 从创建到上线，全流程可视化，SSE 实时推送部署进度
- **多集群管理** — 跨集群实例编排，健康巡检，弹性扩缩
- **飞书 SSO** — 企业级身份认证，组织架构自动同步

## CE / EE

采用 Community Edition / Enterprise Edition 双版本架构：

| | CE（社区版） | EE（企业版） |
|---|---|---|
| 协议 | Apache 2.0 | 商业许可 |
| 核心功能 | 实例部署、集群管理、日志监控、基因市场 | CE 全部 + 多组织、计费、高级审计 |
| 代码 | 本仓库 | 私有 `ee/` 目录 |

运行时通过 `FeatureGate` 自动检测 — `ee/` 存在即 EE，否则 CE。功能清单定义在 `features.yaml`。

**技术实现**：后端 Factory 抽象层 + Hook 事件总线；前端 Stub + Vite Alias Override。

## Architecture

```
DeskClaw/
├── nodeskclaw-portal/             # User Portal — Vue 3 + Tailwind CSS
├── nodeskclaw-frontend/           # Admin Console — Vue 3 + shadcn-vue + Tailwind CSS
├── nodeskclaw-backend/            # API Server — Python 3.12 + FastAPI + SQLAlchemy
├── nodeskclaw-llm-proxy/          # LLM Proxy — Go
├── nodeskclaw-artifacts/          # Docker images & deploy manifests
├── openclaw-channel-nodeskclaw/   # Workspace Agent channel plugin
├── features.yaml                  # CE/EE feature registry
├── ee/                            # Enterprise Edition (private)
├── openclaw/                      # DeskClaw runtime source (external)
└── vibecraft/                     # VibeCraft source (external)
```

## i18n

全栈国际化，覆盖 Portal、Admin、Backend 三端。

- 语言检测：`zh*` -> `zh-CN`，`en*` -> `en-US`，fallback `en-US`
- 错误展示：优先 `message_key` 本地翻译，缺失时回退 `message`
- 后端契约：`code` + `error_code` + `message_key` + `message` + `data`

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
# Edit .env — fill in the required values below
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
