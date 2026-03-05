# deploy/ — CI/CD 构建部署脚本

NoDeskClaw 前后端的镜像构建、推送和 K8s 部署更新工具集。

## 目录结构

```
deploy/
├── deploy.sh         # 统一构建推送部署脚本
├── init-secrets.sh   # 首次部署初始化（创建 K8s Secret + 应用清单）
├── k8s/
│   ├── backend.yaml  # 后端 Deployment + Service
│   ├── admin.yaml    # Admin 前端 Deployment + Service
│   └── portal.yaml   # Portal 前端 Deployment + Service
└── README.md
```

## 部署架构

三个独立镜像，各自有 Deployment + ClusterIP Service，部署在 `nodeskclaw-system` Namespace：

| 组件 | 镜像名 | 端口 | 说明 |
|------|--------|------|------|
| backend | `nodeskclaw-backend` | 8000 | FastAPI，处理 API + SSE |
| admin | `nodeskclaw-admin` | 80 | Nginx，Admin 前端，反代 `/api` `/stream` 到 backend |
| portal | `nodeskclaw-portal` | 80 | Nginx，Portal 前端，反代 `/api` 到 backend |

镜像仓库：`<YOUR_REGISTRY>/<YOUR_NAMESPACE>/`

## 用法

### 首次部署

```bash
# 1. 确保 kubectl 指向正确的 VKE 集群
# 2. 确保 cr-pull-secret 已在 nodeskclaw-system 中创建
# 3. 初始化（从 .env 创建 Secret + 应用 K8s 清单）
./deploy/init-secrets.sh

# 4. 构建、推送、部署全部组件
./deploy/deploy.sh all
```

### 日常更新

```bash
# 更新后端
./deploy/deploy.sh backend

# 更新 Admin 前端
./deploy/deploy.sh admin

# 更新 Portal 前端
./deploy/deploy.sh portal

# 全量更新
./deploy/deploy.sh all
```

### 高级用法

```bash
# 仅构建和推送镜像，不更新 K8s
./deploy/deploy.sh backend --build-only

# 仅更新 K8s 到指定标签（不重新构建）
./deploy/deploy.sh admin --deploy-only --tag 20260218-b0f6ad1

# 构建时不使用 Docker 缓存
./deploy/deploy.sh portal --no-cache
```

### 镜像标签格式

`YYYYMMDD-<git-short-hash>`，例如 `20260218-b0f6ad1`

## 前提条件

- Docker Desktop 运行中，且能访问 Docker Hub（拉取基础镜像）
- 已登录容器镜像仓库：`docker login <YOUR_REGISTRY>`
- `kubectl` 已配置正确的 VKE 集群上下文
- `nodeskclaw-system` Namespace 和 `cr-pull-secret` 已存在
- 创建本地部署配置 `deploy/.env.local`（已被 `.gitignore` 忽略），填写真实镜像仓库地址：
  ```bash
  # deploy/.env.local
  REGISTRY="<YOUR_REGISTRY>/<YOUR_NAMESPACE>"
  ```

## Dockerfile 位置

| 组件 | Dockerfile | Nginx 配置 |
|------|-----------|------------|
| backend | `nodeskclaw-backend/Dockerfile` | — |
| admin | `nodeskclaw-frontend/Dockerfile` | `nodeskclaw-frontend/nginx.conf` |
| portal | `nodeskclaw-portal/Dockerfile` | `nodeskclaw-portal/nginx.conf` |

## CE/EE 构建差异

`deploy.sh` 自动检测项目根目录下是否存在 `ee/` 目录：

- **CE 模式**（无 `ee/`）：使用各组件自身的 Dockerfile 和 build context，构建纯 CE 镜像
- **EE 模式**（有 `ee/`）：自动生成临时 Dockerfile，将 build context 提升到项目根，注入 EE 代码：
  - backend：追加 `COPY ee/ ./ee/` 将 EE 后端模块打入镜像
  - admin：`COPY ee/frontend/admin/ /ee/frontend/admin/` 使 Vite alias 覆盖生效
  - portal：`COPY ee/frontend/portal/ /ee/frontend/portal/` 同理

K8s 清单（`k8s/*.yaml`）CE/EE 通用，差异仅在镜像内容。
