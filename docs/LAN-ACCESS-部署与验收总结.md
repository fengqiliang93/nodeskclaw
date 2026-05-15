# LAN Access 部署与验收总结

## 目标

确保在局域网内：

- Portal 可访问
- OpenClaw 实例可访问
- 新环境一键部署后管理员账号密码可用
- 提供可重复执行的可达性验收命令

## 一键脚本改造（deploy/lan-access.sh）

已新增/修正以下能力：

1. `print-kubeconfig`
- 输出可直接粘贴到 Portal「添加集群」的 KubeConfig
- 自动将 `server: https://127.0.0.1:6443` 替换为 `server: https://<LAN_IP>:6443`

2. `verify-services`
- 一键检查：Portal、Backend Deployment、LLM Proxy Deployment、所有实例入口 `/healthz`
- 用于部署后验收与回归检查

3. `bootstrap` 默认登录与可用性保证
- 新增参数：`--admin-password`
- 新增参数：`--admin-username`（默认 `admin`；若环境中已存在其它管理员账号，必须传入实际账号名，否则 backend 因 `INIT_ADMIN_ACCOUNT` 与现有用户 email 冲突导致 CrashLoop）
- 默认密码：`xprecise`
- Bootstrap 结束后自动调用登录接口校验账号密码可用

4. LLM 上游改为可配置项
- 新增参数：`--llm-target-base-url`
- 新增参数：`--llm-api-key`
- 适用命令：`bootstrap`、`ensure-llm-proxy`
- 默认值保持兼容：`http://10.100.15.9:3000/v1` + `sk-local-placeholder`
- 可在一键部署时直接覆盖，避免下次部署后仍指向错误上游

5. 实例域名策略
- 新增参数：`--ingress-base-domain-suffix`（默认 `nip.io`）
- 自动生成实例域名：`http://<instance-slug>.<LAN_IP>.nip.io`

6. 默认引擎版本策略
- 自动探测本机 k3s 镜像中的 `deskclaw-openclaw:<tag>`
- 自动发布并设置默认引擎版本，避免 `latest` 不存在导致实例拉取失败
- 支持参数覆盖：`--openclaw-image-registry`、`--openclaw-image-tag`

7. LAN 访问策略（NetworkPolicy）
- `bootstrap` 将 `network_policy_ingress_enabled` 设为 `false`（LAN 场景优先可达）
- `sync-instances` 保留按 Ingress Controller 命名空间补放行逻辑（traefik -> kube-system）

## 局域网其它电脑访问配置

请确保以下条件成立：

1. 网络与端口
- 其它电脑可访问部署机 IP（例如 `10.100.12.211`）
- 放行端口：
  - `30080`（Portal）
  - `80`（实例 HTTP Ingress）
  - 如使用 HTTPS，再放行 `443`

2. DNS/域名
- 默认使用 `nip.io`，无需自建 DNS
- 访问格式：`http://<instance-slug>.<LAN_IP>.nip.io`
- 要求客户端可进行公网 DNS 解析（`nip.io`）

3. K8s IngressClass
- 当前脚本默认 `traefik`
- 如你的集群使用 `nginx`，bootstrap/sync 时传：`--ingress-class nginx`

4. 新增实例后同步
- 若历史实例曾用旧策略，执行：
  - `bash deploy/lan-access.sh sync-instances --lan-ip <LAN_IP> --ingress-class traefik`

## 标准部署与验收命令

多节点场景下，建议先按 [docs/LAN-ACCESS-多机部署操作说明.md](docs/LAN-ACCESS-%E5%A4%9A%E6%9C%BA%E9%83%A8%E7%BD%B2%E6%93%8D%E4%BD%9C%E8%AF%B4%E6%98%8E.md) 中"步骤零"完成 K3s Server/Agent 组网，再执行以下一键部署。

```bash
# 1) 一键部署（示例）
# 若环境中管理员账号非 admin，必须加 --admin-username 参数
bash deploy/lan-access.sh bootstrap \
  --lan-ip 10.100.12.211 \
  --ingress-class traefik \
  --llm-target-base-url http://10.100.12.211:31000/v1 \
  --llm-api-key sk-local-placeholder \
  --admin-password xprecise \
  --admin-username xprecise

# 2) 输出可粘贴 KubeConfig
bash deploy/lan-access.sh print-kubeconfig --lan-ip 10.100.12.211

# 3) 验收所有服务可达性
bash deploy/lan-access.sh verify-services --lan-ip 10.100.12.211

# 4) 修复/同步历史实例入口
bash deploy/lan-access.sh sync-instances --lan-ip 10.100.12.211 --ingress-class traefik
```

## 定制化 OpenClaw 镜像构建、导入与一键部署

### 1) 构建定制 OpenClaw 镜像

在部署机执行：

```bash
cd nodeskclaw-artifacts/openclaw-image
docker build --platform linux/amd64 -t deskclaw-openclaw:v2026.3.13-custom -f Dockerfile .
```

如需源码全量构建或 source 变体，可使用 `Dockerfile.full` / `Dockerfile.source`。

### 2) 导出镜像（离线场景）

```bash
docker save deskclaw-openclaw:v2026.3.13-custom -o deskclaw-openclaw-v2026.3.13-custom.tar
```

### 3) 导入到 k3s containerd

```bash
sudo k3s ctr -n k8s.io images import deskclaw-openclaw-v2026.3.13-custom.tar
```

也可以使用脚本导入 backend/portal/proxy 相关镜像：

```bash
bash deploy/lan-access.sh import-images --dir /opt/offline-images
```

### 4) 一键部署并指定默认 OpenClaw 版本

```bash
bash deploy/lan-access.sh bootstrap \
  --lan-ip 10.100.12.211 \
  --ingress-class traefik \
  --openclaw-image-registry nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw \
  --openclaw-image-tag v2026.3.13-custom \
  --llm-target-base-url http://10.100.12.211:31000/v1 \
  --llm-api-key sk-local-placeholder \
  --admin-password xprecise
```

### 5) 复验

```bash
bash deploy/lan-access.sh verify-services --lan-ip 10.100.12.211
```

若需要单独更新 llm-proxy 上游：

```bash
bash deploy/lan-access.sh ensure-llm-proxy \
  --image nodeskclaw-llm-proxy:local \
  --llm-target-base-url http://10.100.12.211:31000/v1 \
  --llm-api-key sk-local-placeholder
```

## 本次实测结果

- Portal：可达
- Backend Deployment：就绪
- LLM Proxy Deployment：就绪
- 实例 `test-openclaw-a2`：可达（http://10.100.12.211:30333）
- 实例聊天（newapi/deepseek-v3.2）：已验收，返回正确回复
- 模型路由：实例 Pod → 集群内 llm-proxy → 外部 newapi（10.100.15.9:3000）
- 账号：xprecise/xprecise（2026-05-07 验收）

## 后端代码级修复（2026-05-07）

`nodeskclaw-backend/app/services/llm_config_service.py` 已修复：

- **问题**：`personal` key_source 会直接将用户配置的外部 baseUrl 写入实例 `openclaw.json`，实例 Pod 无法直连外部地址（10.100.15.9:3000 在 Pod 网络中不可达）
- **修复**：当 proxy_url 可用时，personal key 同样路由到 llm-proxy（`<proxy_url>/<provider>/v1`），apiKey 替换为实例 proxy_token
- **效果**：实例无论使用 org key 还是 personal key，模型调用均走集群内 llm-proxy 转发

## 备注

如果浏览器中点击实例链接后短时出现 `502`，通常是实例刚重启或 Ingress/NetworkPolicy 尚未收敛，建议先执行一次 `verify-services` 和 `sync-instances`。