---
name: release-deploy
description: >-
  DeskClaw 发版与部署流程助手。当用户提到"发版"、"release"、"部署"、"deploy"、
  "promote"、"上线"、"发 beta"、"发 pre-release"时触发。根据用户意图生成完整的
  可执行命令，包含前置检查结果和操作确认清单。
---

# DeskClaw 发版与部署

## 触发后的工作流程

### 1. 解析用户意图

从用户消息中提取以下参数：

| 参数 | 如何判断 | 默认值 |
|---|---|---|
| 操作类型 | release / deploy / promote | 必须明确 |
| 版本号 | 用户指定（如 v0.9.8-beta.1） | release/promote 必须指定 |
| CE/EE | 用户说"EE"或"含 admin" → `--ee` | CE（不加 --ee） |
| 镜像源 | 用户说"国内源"/"mirrors"/"cn" → `--mirrors cn` | 不加 |
| 目标环境 | staging（默认）/ 生产（`--prod`） | staging |
| 部署目标 | all / backend / admin / portal / proxy | all |
| 仅构建 | 用户说"只构建不部署" → `--build-only` | 否 |
| 仅部署 | 用户说"不重新构建" → `--deploy-only --tag <version>` | 否 |

### 2. 前置检查（只读命令，直接执行）

```bash
git status --short                        # 未提交变更
git tag -l '<version>*'                   # tag 是否已存在
git log --oneline -1                      # 最新 commit
```

EE 模式额外检查：
```bash
ls -d ee/ 2>/dev/null                     # ee/ 目录存在
cd ee && git status --short               # EE 仓库状态
```

### 3. 输出操作确认清单

按以下格式输出，等用户确认后给出可粘贴的命令：

```
**发版目标**：<版本号> <CE/EE> <Pre-release/正式>

**当前状态**：
- CE 仓库：<干净/有未提交变更>
- EE 仓库：<干净/有未提交变更>（仅 EE 模式）
- 最新 commit：<hash> <message>
- tag <版本号>：<不存在/已存在>

**即将执行**：

| 步骤 | 命令 | 说明 |
|---|---|---|
| 1 | `./deploy/cli.sh ...` | ... |
| 2 | `./deploy/cli.sh ...` | ...（如有） |

**镜像分发**：
- backend/portal/proxy → <PUBLIC_REGISTRY 或 REGISTRY>
- admin → <REGISTRY>（仅 EE）

确认后请在终端运行以上命令。
```

**重要**：构建和发版命令必须由用户手动执行，禁止通过 Shell 工具运行 `deploy/cli.sh`。

## 常见场景速查

### 场景 A：EE Pre-release（如本次 v0.9.8-beta.1）

```bash
# 1. 发版（构建镜像 + git tag + GitHub Pre-release）
./deploy/cli.sh release <version> --ee --mirrors cn

# 2. 部署到 staging（可选）
./deploy/cli.sh deploy --ee --deploy-only --tag <version>
```

### 场景 B：CE Pre-release

```bash
./deploy/cli.sh release <version> --mirrors cn
```

### 场景 C：日常部署到 staging

```bash
./deploy/cli.sh deploy                    # CE
./deploy/cli.sh deploy --ee              # EE
./deploy/cli.sh deploy --ee --mirrors cn # EE + 国内源
./deploy/cli.sh deploy backend           # 只部署后端
```

### 场景 D：部署指定版本（不重新构建）

```bash
./deploy/cli.sh deploy --deploy-only --tag <version>          # staging
./deploy/cli.sh deploy --deploy-only --tag <version> --prod   # 生产
```

### 场景 E：正式发布（staging 转生产）

```bash
./deploy/cli.sh promote <version>
```

## CLI 参数速查

| 参数 | 作用 | 适用命令 |
|---|---|---|
| `--ee` | EE 模式（含 admin + ee/ 代码注入） | deploy, release |
| `--mirrors cn` | 国内镜像源加速构建 | deploy, release |
| `--prod` | 部署到生产环境 | deploy |
| `--tag <tag>` | 指定镜像标签 | deploy |
| `--build-only` | 仅构建推送，不更新 K8s | deploy |
| `--deploy-only` | 仅更新 K8s，需配合 --tag | deploy |
| `--skip-proxy` | 跳过 proxy 组件 | deploy, release |
| `--no-cache` | Docker 不使用缓存 | deploy, release |
| `--force` | 跳过 Secret 差异确认 | init |

## 镜像仓库规则

- `get_component_registry("admin")` → `$REGISTRY`（私有，EE 专用）
- `get_component_registry("其他")` → `$PUBLIC_REGISTRY`（公开）或回退 `$REGISTRY`
- 配置位于 `deploy/.env.local`（不进 git）
