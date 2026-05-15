# LAN Access 多机部署操作说明

## 目标

用于在“多节点 K8s 集群 + 多台访问机”场景下，完成 NoDeskClaw 的局域网部署、镜像分发、服务验收与常见故障排查。

## 拓扑说明

- 部署机：`<LAN_IP>`，同时作为 K8s 节点之一，对外提供 Portal、Ingress、NodePort 入口
- 其它 K8s 节点：例如 `<LAN_IP>`，实例 Pod 可能调度到任一节点
- 访问机：同一局域网内的其它电脑，通过浏览器访问 Portal 和实例域名
- 可选模型上游机：可与部署机同机，也可以是集群外另一台机器

示例地址：

- 部署机 LAN IP：`<LAN_IP>`
- 其它节点 IP：`<LAN_IP>`
- 模型上游地址：`http://<LAN_IP>:3000/v1`
- Portal 地址：`http://<LAN_IP>:30080`

说明：

- 实例 Pod 可以实际运行在 `<LAN_IP>` 或 `<LAN_IP>`。
- 浏览器访问入口仍以部署机暴露的地址为准，不直接访问 Pod IP。
- 如使用 Ingress 域名，域名应统一指向部署机 LAN IP，例如 `<LAN_IP>`。

## 前置条件

1. 部署机、其它 K8s 节点、访问机在同一网段，节点间互相可达。
2. 部署机已安装并可使用：`docker`、`kubectl`、`k3s`。
3. 防火墙已放行：`30080`（Portal）、`80`（实例 HTTP）、可选 `443`（HTTPS）。
4. 如使用 `nip.io`，访问机需可解析公网 DNS。

## 步骤零：将两台机器组为 K3s 集群

以下以两台机器为例：

- Server 节点（部署机）：`<LAN_IP>`
- Agent 节点：`<LAN_IP>`

### 0.1 在部署机初始化 K3s Server

在 `<LAN_IP>` 执行：

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 --node-ip <LAN_IP> --advertise-address <LAN_IP> --flannel-backend host-gw" sh -
```

说明：

- 当前这类“多节点在同一局域网二层网段”场景，推荐直接使用 `host-gw`。
- 这样可以避免 VXLAN `8472/UDP` 被网络环境、宿主机内核或网卡卸载特性影响，也不会再引入额外封装带来的 MTU 缩减。
- 如果继续使用默认 VXLAN，后续可能出现“NodePort 只有本节点能访问、跨节点 Pod 网段互通超时、局域网入口偶发不可用”等问题。
- 如果是把**已经运行中的集群**从 VXLAN 切到 `host-gw`，切换后要额外确认 `cni0` 与新建 Pod `eth0` 的 MTU 已一起切到 `1500`；如果桥还停在旧的 `1450`，而新 Pod 已变成 `1500`，会再次出现“实例 Running 但飞书/部分 HTTPS 超时”的问题。

检查服务状态：

```bash
sudo systemctl status k3s --no-pager
kubectl get nodes -o wide
```

预期此时至少能看到 `<LAN_IP>` 这一台节点为 `Ready`。

### 0.2 在部署机读取集群加入 Token

在 `<LAN_IP>` 执行：

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

记下输出内容，后面 Agent 节点加入集群时要用。

### 0.3 在第二台机器加入为 K3s Agent

在 `<LAN_IP>` 执行：

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<LAN_IP>:6443 K3S_TOKEN=<上一步读取的token> INSTALL_K3S_EXEC="agent --node-ip <LAN_IP>" sh -
```

如果 Server 端已经使用 `--flannel-backend host-gw`，Agent 端不需要重复传该参数，直接加入即可；实际网络后端由 Server 配置统一下发。

检查 Agent 服务状态：

```bash
sudo systemctl status k3s-agent --no-pager
```

### 0.4 在部署机确认两台节点都已加入

回到 `<LAN_IP>` 执行：

```bash
kubectl get nodes -o wide
```

预期结果类似：

```text
NAME           STATUS   ROLES                  INTERNAL-IP
<LAN_IP>    Ready    control-plane,master   <LAN_IP>
<LAN_IP>    Ready    <none>                 <LAN_IP>
```

如果 `<LAN_IP>` 没有 `Ready`，先排查：

- 两台机器是否能互通 `6443`
- Agent 节点时间是否漂移过大
- `sudo journalctl -u k3s-agent -n 200 --no-pager` 是否有证书或网络报错

### 0.5 导出并保存部署机 KubeConfig

在 `<LAN_IP>` 执行：

```bash
sudo cat /etc/rancher/k3s/k3s.yaml
```

如需在其它机器使用 `kubectl`，把其中默认的 `127.0.0.1` 改成 `<LAN_IP>` 后再分发。

### 0.6 多节点场景下的镜像准备

如果你使用的是本地构建镜像，而不是所有节点都可直接拉取的远端仓库镜像，需要注意：

- `nodeskclaw-backend`、`nodeskclaw-portal`、`nodeskclaw-llm-proxy`、`deskclaw-openclaw` 这类镜像，可能会被调度到任意节点。
- 因此本地离线镜像应导入到每一台可能承载 Pod 的节点，而不只是 `<LAN_IP>`。

例如：

```bash
# 在 <LAN_IP> 导入
sudo k3s ctr -n k8s.io images import /opt/offline-images/deskclaw-openclaw-v2026.3.13-custom.tar

# 在 <LAN_IP> 同样导入
sudo k3s ctr -n k8s.io images import /opt/offline-images/deskclaw-openclaw-v2026.3.13-custom.tar
```

如果镜像来自统一远端仓库，且两台机器都能正常拉取，则不需要手工逐台导入。

补充说明：

- OpenClaw 定制镜像需要把持久配置恢复逻辑放在镜像入口层，否则 `models.providers`（自定义模型提供商）和用户通道配置可能会在重启后丢失。
- 仅靠平台 API 写入配置不够，镜像重启后仍可能被启动流程重写。
- `nodeskclaw-backend` 在 K8s 内必须能自动推导到集群可达的 `AGENT_API_BASE_URL`（后端 API 地址）和 `TUNNEL_BASE_URL`（实例反连 WebSocket 地址），不能落回 `localhost`，否则实例部署和 tunnel 会直接失败。

## 步骤一：准备与导入镜像

在线场景可直接在部署机构建；离线场景先导出 tar 再导入。多节点场景下，离线镜像需要导入到每一台可能运行 Pod 的节点。

```bash
# 部署机：导入离线镜像目录
bash deploy/lan-access.sh import-images --dir /opt/offline-images
```

如果 `<LAN_IP>` 也会承载实例 Pod，需要在该机器上执行同等导入，或确保其可以从远端仓库拉取相同镜像。

如需手工导入 OpenClaw 定制镜像：

```bash
sudo k3s ctr -n k8s.io images import /opt/offline-images/deskclaw-openclaw-v2026.3.13-custom.tar
```

## 步骤二：一键部署

```bash
bash deploy/lan-access.sh bootstrap \
  --lan-ip <LAN_IP> \
  --ingress-class traefik \
  --openclaw-image-registry nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw \
  --openclaw-image-tag v2026.3.13-custom \
  --llm-target-base-url http://<LAN_IP>:3000/v1 \
  --llm-api-key sk-local-placeholder \
  --admin-password <admin-password>
```

说明：

- `--lan-ip` 应填写对外统一访问入口 IP；当前场景为部署机 `<LAN_IP>`。
- Pod 即使被调度到 `<LAN_IP>`，Portal/实例入口仍通过 Service/Ingress 转发，不需要把入口改成 Pod 所在节点。
- `--llm-target-base-url`、`--llm-api-key` 是模型调用稳定性的关键参数。
- 若上游模型在另一台机器且 k3s Pod 无法直连，可先在部署机做 relay，再把 `--llm-target-base-url` 指向 relay 地址。
- OpenClaw 网关配置必须显式开启 `gateway.http.endpoints.chatCompletions.enabled=true`，否则实例 `/v1/chat/completions` 会返回 404。

## 步骤三：同步实例入口

```bash
bash deploy/lan-access.sh sync-instances --lan-ip <LAN_IP> --ingress-class traefik
```

## 步骤四：多机验收

在部署机执行：

```bash
bash deploy/lan-access.sh verify-services --lan-ip <LAN_IP>
```

再检查实例是否已经分布到预期节点：

```bash
kubectl get pods -A -o wide
```

在访问机执行浏览器验收：

1. 访问 `http://<LAN_IP>:30080`，确认登录页可打开。
2. 使用你显式设置的管理员账号密码登录。
3. 打开实例列表，点击实例访问地址，确认实例首页可达。
4. 执行一次模型调用，确认返回正常。
5. 对测试实例执行一次“克隆”，确认新实例能正常打开 Control UI，页面不再出现 `Control UI assets not found`。
6. 打开新克隆实例执行一次模型调用，确认克隆链路同样正常。
7. 打开新克隆实例的“可用通道”和“通道配置”，确认 `feishu` 通道已自动继承，且聊天、日志、LAN 访问都正常。

建议在每台 K3s 节点额外执行一次 flannel MTU 自检，避免节点重启或历史残留导致新 Pod 获得错误的 `eth0` MTU：

```bash
sudo bash deploy/lan-access.sh check-flannel-mtu-local
```

如果某台节点执行了 `--repair`，除了重启该节点上的实例 Pod，还要滚动重启该节点上已经运行中的系统 Pod（尤其是 CoreDNS），否则 kube-dns Service 仍可能把流量打到旧 MTU 的 DNS Pod，表现为数据库/Service 域名偶发解析失败。

## 步骤五：为访问机提供 KubeConfig（可选）

如需在 Portal 中手动添加集群，执行：

```bash
bash deploy/lan-access.sh print-kubeconfig --lan-ip <LAN_IP>
```

将输出内容复制到 Portal 的“添加集群”表单。

## 常见问题

1. Pod 调度到其它节点后访问异常
- 先确认 Pod 实际落在哪个节点：`kubectl get pods -A -o wide --context <name>`。
- 若 Pod 在 `<LAN_IP>`，但入口是 `<LAN_IP>`，这属于正常情况；优先排查 Service、Ingress、NetworkPolicy，而不是直接访问 Pod IP。

2. 访问机打不开 Portal
- 检查部署机防火墙、交换机 ACL、端口开放情况。
- 在访问机执行 `curl http://<LAN_IP>:30080` 验证网络层。

3. 实例链接 502
- 实例刚重启或 Ingress 尚未收敛。
- 先执行：`bash deploy/lan-access.sh verify-services --lan-ip <LAN_IP>`。
- 再执行：`bash deploy/lan-access.sh sync-instances --lan-ip <LAN_IP> --ingress-class traefik`。

4. 克隆后的新实例出现 `Control UI assets not found`
- 这通常表示克隆部署时没有复用源实例正在运行的定制 OpenClaw 镜像。
- 当前版本已改为克隆优先继承源实例实际运行镜像；若仍复现，先检查源实例 Deployment 的容器镜像，再检查系统默认镜像配置是否与源实例一致。

5. 模型调用报 network connection error
- 检查 `--llm-target-base-url` 指向是否可达。
- 在 llm-proxy Pod 中验证上游连通性。
- 如需 relay，确保 relay 进程常驻并可被 Pod 访问。

6. 飞书通道配置已下发但机器人仍无响应
- 先看实例日志是否有：
  - `feishu failed during register`
  - `Cannot find module '@larksuiteoapi/node-sdk'`
- 若存在，说明是 OpenClaw 运行镜像依赖缺失，不是平台配置问题。
- 使用 `nodeskclaw-artifacts/openclaw-image/Dockerfile.full` 修复：必须把 SDK 的完整 `node_modules`（含传递依赖）复制到
  - `/opt/openclaw/dist/extensions/feishu/node_modules`
  - `/opt/openclaw/dist-runtime/extensions/feishu/node_modules`
- 重新构建并发布新 tag 后，执行批量升级：

```bash
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

- 验收口径：全量实例 `running+healthy`、`channel-configs.feishu` 存在、日志无上述报错、实例入口可达。
- 若日志出现 `tenant_access_token/internal timeout` 或 `[ws] timeout of 15000ms exceeded`，说明实例所在节点外网到飞书不通。
- 从当前版本开始可通过后端环境变量 `FEISHU_NODE_SELECTOR` 固化飞书实例调度节点（例如 `node-role.kubernetes.io/control-plane=true`），平台在写入 `feishu` 通道配置时会自动同步到实例 `advanced_config.node_selector` 并 patch Deployment：

```bash
# 推荐在 bootstrap 前设置（也可写入 nodeskclaw-backend/.env）
export FEISHU_NODE_SELECTOR='node-role.kubernetes.io/control-plane=true'
bash deploy/lan-access.sh bootstrap --lan-ip <LAN_IP> ...
```

- 该策略用于“代码级永久收敛”：后续重建/克隆会继承 `advanced_config.node_selector`，不需要每次手工 patch 节点调度。
- 如果只有某一台节点上的实例出现飞书 TLS 超时，而同节点普通 HTTP 站点仍可访问，优先检查该节点 flannel MTU 是否漂移。典型根因是：
  - `/run/flannel/subnet.env` 中的 `FLANNEL_MTU` 仍是旧值 `1500`
  - 但 `cni0` / `flannel.1` 已是 `1450`
  - 结果是新 Pod `eth0` 仍拿到 `1500`，对外握手时会错误宣告 `mss 1460`，导致 `open.feishu.cn` 这类返回大 TLS 报文的站点在宿主机转发到 Pod 前被丢弃
- 建议在异常节点直接执行：

```bash
sudo bash deploy/lan-access.sh check-flannel-mtu-local --repair
```

- 该命令会重启本机 `k3s` / `k3s-agent`，重建 `/run/flannel/subnet.env`，修复完成后再重启该节点上的实例 Pod 一次；如果该节点上有 CoreDNS 等系统 Pod，也要同步滚动重启，否则 kube-dns Service 仍可能命中旧 MTU Pod，表现为 `Temporary failure in name resolution` 这类间歇性 DNS 故障。

7. 克隆实例长时间停在 `restoring`
- 优先看 backend 日志是否有：
  - `备份分片解码失败`
  - `Incorrect padding`
  - `克隆源备份失败`
- 根因通常不是实例 Pod 本身未就绪，而是源实例备份通过 `kubectl exec` 回传 tar 分片时，单片过大导致 base64 输出被截断。
- 当前修复要求：
  - 备份分片大小降低到保守值，避免 websocket/exec 输出截断。
  - 每片输出统一 `tr -d '\n'` 后再解码。
  - clone 管道在源备份失败或超时时必须把新实例显式标记为 `failed`，不能静默留在 `restoring`。

8. 克隆后飞书通道缺失或实例列表一直正常但通道页为空
- 先确认不是源实例自身缺配置，再检查 clone 恢复链路是否满足以下条件：
  - 备份找 Pod 时优先使用 `app.kubernetes.io/name=<slug>`，并保留 Pod name 前缀兜底。
  - `write_channel_configs()` 必须支持“新增通道”，不能只更新已有键。
  - clone 结束前状态应保持 `restoring`，等通道复制、LLM 同步、runtime 重启全部完成后再切回 `running`。

7. 组织设置里的“引擎版本管理”为空，创建实例也无可选镜像版本
- 典型现象：`GET /api/v1/instances` 有实例且 `image_version` 有值，但 `GET /api/v1/engine-versions?runtime=openclaw` 返回空数组。
- 快速修复（使用现有实例版本自动回填目录并设为默认）：

```bash
python - <<'PY'
import requests
base='http://<LAN_IP>:30080'
login=requests.post(base+'/api/v1/auth/account-login',json={'account':'admin','password':'Nodeskclaw@2026!'},timeout=10)
token=login.json()['data']['access_token']
h={'Authorization':f'Bearer {token}'}
inst=requests.get(base+'/api/v1/instances',headers=h,timeout=20).json()['data']
tag=sorted({x.get('image_version') for x in inst if x.get('image_version')})[-1]
version=tag[1:] if tag.startswith('v') else tag
ev=requests.post(base+'/api/v1/engine-versions',headers={**h,'Content-Type':'application/json'},
                 json={'runtime':'openclaw','version':version,'image_tag':tag,'release_notes':'backfill from instances'},
                 timeout=20).json()['data']
requests.patch(base+f\"/api/v1/engine-versions/{ev['id']}\",headers={**h,'Content-Type':'application/json'},
               json={'is_default':True},timeout=20)
print('backfilled:', tag)
PY
```

- 预防：保持后端为最新版本（已内置版本目录自动回填与默认版本自动修复逻辑）。

8. `NodePort` 地址可见但连接拒绝（如 `<LAN_IP>:31549`）
- 现象：实例 Ingress 可访问，但 `NodePort` / `ClusterIP` 从宿主机访问失败（`curl: (7) Failed to connect`）。
- 这类场景优先使用 Ingress 作为实例入口，不要将可用性绑定在 NodePort。
- 若业务必须保留固定 LAN 端口（例如 `31549`），可在服务器侧加一个宿主机反向代理，把该端口转发到实例 Ingress，并固定 Host 头。

示例（服务器 `<LAN_IP>`）：

```bash
mkdir -p /path/to/nodeskclaw-proxy
cat > /path/to/nodeskclaw-proxy/example-proxy.conf <<'EOF'
server {
  listen 31549;
  server_name _;
  location / {
    proxy_pass http://127.0.0.1:80;
    proxy_set_header Host <instance-slug>.<LAN_IP>.nip.io;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
EOF

docker rm -f example-proxy >/dev/null 2>&1 || true
docker run -d --name example-proxy --restart unless-stopped \
  --network host \
  -v /path/to/nodeskclaw-proxy/example-proxy.conf:/etc/nginx/conf.d/default.conf:ro \
  nginx:1.27-alpine
```

## 多机场景下的彻底清理与从0重建

建议在以下场景执行完整清理：

1. 大版本切换。
2. 镜像标签策略调整（如从 `v2026.5.5` 改为 `2026.5.5`）。
3. 出现“实例有记录但无 Pod”或 `ImagePullBackOff`。

推荐流程：

```bash
# 1) 清理平台与实例
bash deploy/lan-access.sh reset-all --context default --lan-ip <LAN_IP>

# 2) 重新构建 openclaw（确保 TAG_COMPAT_ALIAS=true）
cd nodeskclaw-artifacts
./build-full.sh --source-path ../openclaw --version 2026.5.5 --image deskclaw-openclaw:v2026.5.5 --build-only
cd ..

# 3) 在每台节点导入双 tag（示例仅演示当前机器）
docker save deskclaw-openclaw:v2026.5.5 | sudo k3s ctr -n k8s.io images import -
docker save deskclaw-openclaw:2026.5.5 | sudo k3s ctr -n k8s.io images import -

# 4) 重建并导入平台镜像
docker build --platform linux/amd64 -t nodeskclaw-backend:local -f nodeskclaw-backend/Dockerfile .
docker build --platform linux/amd64 -t nodeskclaw-portal:local nodeskclaw-portal/
docker save nodeskclaw-backend:local | sudo k3s ctr -n k8s.io images import -
docker save nodeskclaw-portal:local | sudo k3s ctr -n k8s.io images import -

# 5) 重新初始化
bash deploy/lan-access.sh bootstrap --context default --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh sync-instances --context default --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh verify-services --context default --lan-ip <LAN_IP>
```

说明：完整清理与从 0 重建的详细版本见 `docs/彻底清理环境与从0一键部署指南.md`。

## 回归建议

每次变更镜像、升级配置或迁移分支后，至少执行一次完整回归：

```bash
bash deploy/lan-access.sh bootstrap --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh sync-instances --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh verify-services --lan-ip <LAN_IP>
```

## Agent 直接操作指南（可复制 Prompt）

### A. 多机集群从0部署

```text
请按 docs/LAN-ACCESS-多机部署操作说明.md 完成两节点 K3s + NoDeskClaw 从0部署。

参数：
- Server 节点: <server-ip>
- Agent 节点: <agent-ip>
- LAN 入口 IP: <lan-ip>
- K8s context: <ctx>
- OpenClaw 版本: <version>

执行要求：
1. 先校验两节点 Ready。
2. 镜像若为离线导入，必须在两台节点都导入。
3. 执行 bootstrap -> sync-instances -> verify-services。
4. 输出：节点状态、关键服务状态、访问地址清单。

约束：
1. 不修改 openclaw 源码。
2. 不做未确认的破坏性操作。
```

### B. 多机回归验收（含克隆链路）

```text
请对当前多机环境执行完整验收，并重点验证克隆链路。

验收点：
1. Portal 可从访问机打开并登录。
2. 实例列表入口可达（域名 + NodePort）。
3. 原实例模型调用成功。
4. 克隆后新实例 Control UI 正常（无 assets not found）。
5. 新克隆实例模型调用成功。

输出：
- 每个验收点的结果（PASS/FAIL）
- FAIL 时附带最短修复路径
```

### C. 多机故障排查（网络/调度/镜像）

```text
请排查“多机环境访问异常”问题，按证据链输出结论。

排查顺序：
1. 节点与 Pod 调度：kubectl get nodes/pods -o wide。
2. 入口链路：Service / Ingress / NetworkPolicy。
3. 镜像可用性：两节点镜像标签是否齐全。
4. 应用状态：backend/portal/llm-proxy 日志。

输出格式：
1. 现象
2. 根因
3. 修复建议
4. 验证命令
```
