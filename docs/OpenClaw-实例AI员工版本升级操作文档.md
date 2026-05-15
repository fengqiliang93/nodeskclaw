# OpenClaw 实例 AI 员工版本升级操作文档

## 1. 全流程概览

```text
1. 检查新版本
      ↓
2. 更新 Dockerfile 版本号
      ↓
3. 构建并推送新镜像（linux/amd64）
      ↓
4. 验证镜像可用性
      ↓
5. 在 NoDeskClaw 中注册新版本（engine-versions）
      ↓
6. 执行实例升级（单个 / 批量）
      ↓
7. 验证升级结果
```

## 2. 前置准备

- 已安装并可用：`docker`、`kubectl`、`jq`、`npm`
- 具备 NoDeskClaw 管理员账号（用于获取 API Token）
- 已登录镜像仓库（示例）：

```bash
docker login nodesk-center-cn-beijing.cr.volces.com
```

- 当前项目目录：

```bash
cd /home/x-ai/WorkSpace/OpenSourceCode/nodeskclaw
```

## 3. 检查 OpenClaw 新版本

### 3.1 自动检查最新稳定版

```bash
cd nodeskclaw-artifacts/openclaw-image
./check-update.sh
```

说明：脚本会对 npm 版本列表做稳定版过滤，仅保留 `YYYY.M.DD` 形式版本。

### 3.2 自动更新 Dockerfile 版本号

```bash
./check-update.sh --update
```

说明：该命令会自动更新 `Dockerfile` 中的 `OPENCLAW_VERSION` 和 `IMAGE_VERSION`。

## 4. 构建并推送新镜像

镜像仓库路径规则：

- `nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw`

### 4.1 使用国内镜像源构建并推送（推荐）

```bash
cd ../
./build.sh openclaw --version 2026.4.22 --mirrors cn
```

### 4.2 自动检测最新版并构建推送

```bash
./build.sh openclaw --mirrors cn
```

### 4.3 仅构建不推送

```bash
./build.sh openclaw --version 2026.4.22 --build-only --mirrors cn
```

说明：

- `build.sh` 默认使用 `docker build --platform linux/amd64`
- 不加 `--build-only` 时，构建完成后会自动 push

### 4.4 本地手动构建镜像后，直接导入 K3s（不依赖外部仓库）

适用场景：你在本地 `docker build` 成功了，但不希望或暂时不能 push 到公网仓库。

关键原则：

- 镜像 tag 仍建议使用平台升级约定（如 `v2026.4.22`）
- 在 NoDeskClaw 升级时，`image_version` 必须与镜像 tag 一致
- K3s 是 `containerd`，需要把镜像导入 `k8s.io` 命名空间

步骤：

```bash
# 1) 本地构建并打上“平台会使用的完整镜像名”
docker build --platform linux/amd64 \
  -t nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v2026.4.22 \
  nodeskclaw-artifacts/openclaw-image

# 2) 导出镜像 tar
docker save -o openclaw-v2026.4.22.tar \
  nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v2026.4.22

# 3) 拷贝到每个 K3s 节点（单节点就只传一台）
scp openclaw-v2026.4.22.tar user@<node-ip>:/tmp/

# 4) 在每个节点导入到 containerd(k8s.io)
ssh user@<node-ip> "sudo k3s ctr -n k8s.io images import /tmp/openclaw-v2026.4.22.tar"

# 5) 校验每个节点都能看到该镜像
ssh user@<node-ip> "sudo k3s ctr -n k8s.io images ls | grep deskclaw-openclaw | grep v2026.4.22"
```

注意：

- 多节点集群必须“每个节点都导入”
- 请避免使用 `latest`，否则 K8s 可能触发强制拉取
- 若后续 Pod 调度到未导入节点，会出现 `ImagePullBackOff`

### 4.5 本地手工镜像推到内网 Registry，再用于升级（推荐）

适用场景：你有内网 Harbor/Registry，希望统一拉取来源，不手工导入每个节点。

```bash
# 1) 本地镜像 retag 到内网仓库
docker tag \
  nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v2026.4.22 \
  10.100.12.211:5000/deskclaw-openclaw:v2026.4.22

# 2) 推送内网仓库
docker push 10.100.12.211:5000/deskclaw-openclaw:v2026.4.22
```

然后把 NoDeskClaw 的镜像仓库地址切到内网仓库：

```bash
curl -s -X PUT "$BASE/api/v1/settings/image_registry" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"10.100.12.211:5000/deskclaw-openclaw"}' | jq
```

如果内网仓库需要账号密码，再设置：

```bash
curl -s -X PUT "$BASE/api/v1/settings/registry_username" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"<username>"}' | jq

curl -s -X PUT "$BASE/api/v1/settings/registry_password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"<password>"}' | jq
```

完成后按第 6~9 章执行“版本注册 + 实例升级”即可。

## 5. 镜像验证

### 5.1 使用 verify.sh 执行集成验证

```bash
./verify.sh nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v2026.4.22
```

### 5.2 快速手动校验

```bash
docker run --rm --platform linux/amd64 \
  nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v2026.4.22 \
  cat /root/.openclaw-version
```

预期输出：`v2026.4.22`

## 6. 注册新版本到 NoDeskClaw

### 6.1 获取管理员 Token

```bash
BASE=http://10.100.12.211:30080

TOKEN=$(curl -s "$BASE/api/v1/auth/account-login" \
  -H "Content-Type: application/json" \
  -d '{"account":"admin","password":"xprecise"}' \
  | jq -r '.data.access_token')

echo "$TOKEN"
```

### 6.2 查询已注册版本

```bash
curl -s "$BASE/api/v1/engine-versions?runtime=openclaw" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data[] | {id,version,image_tag,is_default,status}'
```

### 6.3 发布新版本

```bash
TARGET_VERSION=2026.4.22

curl -s -X POST "$BASE/api/v1/admin/engine-versions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"runtime\": \"openclaw\",
    \"version\": \"v${TARGET_VERSION}\",
    \"image_tag\": \"v${TARGET_VERSION}\",
    \"release_notes\": \"升级至 OpenClaw ${TARGET_VERSION}\"
  }" | jq
```

### 6.4 设为默认版本（可选）

```bash
VERSION_ID=$(curl -s "$BASE/api/v1/engine-versions?runtime=openclaw" \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r ".data[] | select(.version == \"v${TARGET_VERSION}\") | .id")

curl -s -X PATCH "$BASE/api/v1/admin/engine-versions/$VERSION_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_default": true}' | jq
```

## 7. 单个实例升级

### 7.1 查询实例列表

```bash
curl -s "$BASE/api/v1/instances" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data[] | {id,name,image_version,status}'
```

### 7.2 保存配置并应用

```bash
INSTANCE_ID=替换为实例ID
TARGET_VERSION=2026.4.22

# Step 1: 写入 pending_config（不立即生效）
curl -s -X PUT "$BASE/api/v1/instances/$INSTANCE_ID/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"image_version\": \"v${TARGET_VERSION}\"}" | jq

# Step 2: 应用配置（触发滚动更新）
curl -s -X POST "$BASE/api/v1/instances/$INSTANCE_ID/apply" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 7.3 观察升级状态

```bash
watch -n3 "curl -s \"$BASE/api/v1/instances/$INSTANCE_ID\" \
  -H \"Authorization: Bearer $TOKEN\" \
  | jq '.data | {name,image_version,status,health_status}'"
```

## 8. 批量升级所有 OpenClaw 实例

接口：`POST /api/v1/workspaces/maintenance/batch-upgrade-instances`

### 8.1 Dry Run 预检（强烈建议先执行）

```bash
TARGET_VERSION=2026.4.22

curl -s -X POST "$BASE/api/v1/workspaces/maintenance/batch-upgrade-instances" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"runtime\": \"openclaw\",
    \"image_version\": \"v${TARGET_VERSION}\",
    \"dry_run\": true
  }" | jq '.data.upgrade'
```

### 8.2 正式执行批量升级

```bash
curl -s -X POST "$BASE/api/v1/workspaces/maintenance/batch-upgrade-instances" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"runtime\": \"openclaw\",
    \"image_version\": \"v${TARGET_VERSION}\",
    \"dry_run\": false,
    \"with_repair\": true
  }" | jq '.data'
```

说明：

- `dry_run=true` 只做评估，不改动实例
- `with_repair=true` 会在升级后执行修复逻辑

## 9. 升级后验证

### 9.1 校验实例版本分布

```bash
curl -s "$BASE/api/v1/instances" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.data | group_by(.image_version) | map({version: .[0].image_version, count: length})'
```

### 9.2 校验 K8s Pod 与镜像

```bash
kubectl get pods -n nodeskclaw-staging --context default

kubectl get pods -n nodeskclaw-staging --context default \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.initContainers[0].image}{"\n"}{end}'
```

### 9.3 查看 init-container 升级日志

```bash
kubectl logs <pod-name> -n nodeskclaw-staging --context default -c init-openclaw | head -30
```

## 10. 回滚操作

### 10.1 查看历史版本

```bash
curl -s "$BASE/api/v1/instances/$INSTANCE_ID/history" \
  -H "Authorization: Bearer $TOKEN" | jq '.data[:5]'
```

### 10.2 执行回滚

```bash
curl -s -X POST "$BASE/api/v1/instances/$INSTANCE_ID/rollback" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_revision": 5}' | jq
```

## 11. 数据安全机制说明（为什么升级不丢数据）

升级过程中，实例数据通常不会因为镜像升级而丢失，核心原因如下：

1. 业务数据在持久化存储（PVC / 挂载目录），不在镜像层。
2. `init-container.sh` 在版本变化时走“轻量升级”策略：
   - 更新版本标记
   - 合并内置插件（`cp -n` 不覆盖已有用户文件）
   - 补齐新目录结构
3. `docker-entrypoint.sh` 默认使用已存在配置，不会强制覆盖。
4. 只有显式设置 `OPENCLAW_FORCE_RECONFIG=true` 才会按模板重建配置。

## 12. 故障排查建议

### 12.1 镜像构建慢或失败（国内网络）

- 优先使用：`--mirrors cn`
- 检查 `deploy/mirrors/cn.env` 中 APT/PIP/NPM 配置是否可用

### 12.2 批量升级返回部分失败

- 从 `failed` 列表提取实例 ID
- 对失败实例执行单实例升级流程（先 `PUT /config` 再 `POST /apply`）
- 同步查看 Pod 事件和日志

### 12.3 版本注册后前端不可选

- 检查 `runtime` 是否填 `openclaw`
- 检查 `version` 与 `image_tag` 是否与镜像 tag 一致（建议都用 `vYYYY.M.DD`）
- 检查是否误设置 `status=deprecated`

### 12.4 本地导入镜像后仍然拉取失败

- 确认 Pod 里的镜像全名与导入镜像全名完全一致（含仓库路径 + tag）
- 多节点时确认目标节点已导入该镜像
- 执行：

```bash
kubectl describe pod <pod-name> -n nodeskclaw-staging --context default
```

- 若事件里显示 `pull access denied`，优先检查：
  - `image_registry` 配置是否仍指向旧仓库
  - `registry_username/registry_password` 是否正确
  - 内网仓库证书/网络是否可达

### 12.5 飞书通道配置存在但实例内不生效（无响应）

典型现象：

- NoDeskClaw 平台 `channel-configs.feishu` 已存在；
- OpenClaw 控制台 Channels 不显示 Feishu 或飞书消息无响应；
- 实例日志出现 `feishu failed during register` / `Cannot find module '@larksuiteoapi/node-sdk'`。

根因：

- 镜像中仅包含了 `@larksuiteoapi/node-sdk` 主包目录，缺少其传递依赖（transitive dependencies），导致运行时加载失败。

修复要求（`nodeskclaw-artifacts/openclaw-image/Dockerfile.full`）：

- 在镜像构建阶段临时安装 SDK；
- 将完整 `node_modules` 复制到以下两个目录：
  - `/opt/openclaw/dist/extensions/feishu/node_modules`
  - `/opt/openclaw/dist-runtime/extensions/feishu/node_modules`
- 不要只复制 `@larksuiteoapi` 单目录。

建议发布方式：

```bash
# 1) 构建并推送新 tag（不要复用旧 tag）
./build-full.sh --source-path ../openclaw --version 2026.5.7-feishu2 \
  --image 10.100.15.9:5000/deskclaw-openclaw:v2026.5.7-feishu2 --build-only
docker push 10.100.15.9:5000/deskclaw-openclaw:v2026.5.7-feishu2

# 2) 批量升级所有 openclaw 实例到新 tag
curl -s -X POST "$BASE/api/v1/workspaces/maintenance/batch-upgrade-instances" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runtime": "openclaw",
    "image_version": "v2026.5.7-feishu2",
    "dry_run": false,
    "with_repair": true
  }' | jq '.data'
```

升级后验收要点：

- `GET /api/v1/instances`：全部实例 `running + healthy`；
- `GET /api/v1/instances/{id}/channel-configs`：`feishu` 配置存在；
- `GET /api/v1/instances/{id}/pods/{pod}/logs`：无上述 Feishu 注册错误日志；
- 通过浏览器自动化对实例入口和控制台完成覆盖校验。

### 12.6 引擎版本目录为空（创建实例无可选镜像）

典型现象：

- 实例已存在且镜像版本正常（`GET /api/v1/instances` 可见 `image_version`）；
- 但组织设置“引擎版本管理”为空；
- 新建实例时“镜像版本”下拉为空。

处理方式：

- 使用实例当前 `image_version` 发布一个引擎版本，并设为默认版本。
- 如果使用了新后端版本，访问 `/api/v1/engine-versions` 时会自动回填并修复默认版本；建议仍执行一次人工确认。

验收口径：

- `GET /api/v1/engine-versions?runtime=openclaw` 返回非空；
- `GET /api/v1/engine-versions/default?runtime=openclaw` 返回默认版本；
- 新建实例页面“镜像版本”下拉可见对应 tag。

---

文档版本：`2026-04-30`
