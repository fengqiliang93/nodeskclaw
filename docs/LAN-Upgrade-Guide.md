# NoDeskClaw 局域网访问升级指南

本文用于把当前分支的“局域网可访问”定制改动迁移到其它 NoDeskClaw 分支。

## 1. 当前 NoDeskClaw 访问地址

基于当前集群实测（Host IP: 10.100.12.211）：

- Portal: http://10.100.12.211:30080
- Employee-01 域名入口: http://test-employee-01-ratszo.10.100.12.211.nip.io
- Employee-01 NodePort 入口: http://10.100.12.211:31889
- Employee-02 域名入口: http://test-employee-02.10.100.12.211.nip.io
- Employee-02 NodePort 入口: http://10.100.12.211:31947

查询命令：

```bash
kubectl get svc -A | grep -E "nodeskclaw-portal|test-employee-01-ratszo-lan|test-employee-02-lan|traefik"
kubectl get ingress -A | grep -E "test-employee-01-ratszo|test-employee-02"
```

## 2. 克隆的 OpenClaw 实例是否可直接被局域网访问

结论：可以，但要满足以下条件。

- 实例运行在 K8s 模式（非 docker compute provider）。
- 每个实例都存在对应 NodePort Service（名称为 <instance>-lan）。
- 实例 Namespace 内 NetworkPolicy 已允许局域网来源 IP（10/8, 172.16/12, 192.168/16）。
- Ingress host 已同步到当前 LAN IP（如 *.10.100.12.211.nip.io）。

建议使用脚本一次性修复/同步：

```bash
bash deploy/lan-access.sh sync-instances
bash deploy/lan-access.sh show-urls
bash deploy/lan-access.sh verify-services
```

根因说明（这次故障定位结果）：

- 之前出现“本机 curl 可通，局域网浏览器 ERR_EMPTY_RESPONSE”的原因是 NetworkPolicy 仅放行了集群内来源，LAN 外部来源被 kube-router iptables 链 REJECT。
- 修复后，NodePort 从局域网终端可正常打开 OpenClaw 控制台。

## 3. 相对官方源仓库的定制化改动清单

以下是本次与“官方基线”相比的核心定制点（按迁移优先级排序）。

### 3.1 部署脚本：局域网同步与验收增强

文件：deploy/lan-access.sh

关键改动：

- 新增/增强 patch_instance_network_policy
  - 自动放行 ingress controller namespace（traefik -> kube-system，nginx -> ingress-nginx）。
  - 新增 LAN ipBlock 放行：10.0.0.0/8、172.16.0.0/12、192.168.0.0/16。
- 新增 ensure_instance_lan_service
  - 自动创建 <instance>-lan NodePort Service。
- 增强 sync_instances
  - 修正 Ingress host。
  - 修正 Ingress backend 端口映射：/ -> 18789，/sse -> 9721。
  - 补齐 NodePort Service。
  - 补齐 NetworkPolicy。
- 增强 show_urls
  - 同时输出域名入口与 NodePort 入口。
- 增强 verify_services
  - 按实例同时检测域名入口与 NodePort 入口。

### 3.2 后端：实例部署时自动创建 NodePort

文件：nodeskclaw-backend/app/services/deploy_service.py

关键改动：

- 部署流程中创建 NodePort Service（调用 build_nodeport_service）。
- 构建 NetworkPolicy 时，按 ingress class 增补 ingress_allow_namespaces。
- rebuild 流程同样补齐上述逻辑，避免重建后回退。

### 3.3 后端：K8s 资源构建器增强

文件：nodeskclaw-backend/app/services/k8s/resource_builder.py

关键改动：

- build_network_policy 新增 ingress_allow_namespaces 参数。
- build_network_policy ingress 来源改为可组合命名空间列表。
- 新增 build_nodeport_service
  - Service type=NodePort。
  - 端口覆盖 gateway(18789) 与 sse(9721)。
- build_ingress 补充 traefik 注解支持（entrypoints: web,websecure）。

### 3.4 后端：实例详情新增 NodePort 地址

文件：nodeskclaw-backend/app/schemas/instance.py

- InstanceDetail 增加字段：nodeport_url。

文件：nodeskclaw-backend/app/services/instance_service.py

关键改动：

- 新增 _compute_nodeport_url
  - 从 <instance>-lan Service 提取 nodePort。
  - node_ip 推导优先级：ingress_domain -> cluster gateway_ip -> K8s node IP。
- 在 get_instance_detail 中注入 nodeport_url。

### 3.5 门户前端：展示“局域网直连”地址

文件：nodeskclaw-portal/src/views/InstanceDetail.vue

- 实例详情页新增 nodeport_url 展示块。

文件：nodeskclaw-portal/src/i18n/locales/zh-CN.ts
文件：nodeskclaw-portal/src/i18n/locales/en-US.ts

- 新增文案键：instanceDetail.nodepointUrl（局域网直连 / Local Network Direct Access）。

## 4. 迁移到其它分支的推荐顺序

1. 先迁移后端资源层
   - resource_builder.py
   - deploy_service.py
2. 再迁移实例查询层
   - instance.py
   - instance_service.py
3. 再迁移前端展示层
   - InstanceDetail.vue
   - zh-CN.ts / en-US.ts
4. 最后迁移运维脚本
   - deploy/lan-access.sh

## 5. 迁移后验收清单

```bash
# 1) 同步实例入口
bash deploy/lan-access.sh sync-instances

# 2) 查看地址输出
bash deploy/lan-access.sh show-urls

# 3) 自动可达性验证
bash deploy/lan-access.sh verify-services

# 4) 手工检查网络策略（必须出现局域网 CIDR）
kubectl get networkpolicy -n <instance-namespace> -o yaml

# 5) 手工检查 NodePort Service
kubectl get svc -n <instance-namespace> <instance>-lan -o yaml
```

通过标准：

- 域名入口或 NodePort 入口至少一个可达（建议两个都可达）。
- 局域网其它机器浏览器可直接打开 NodePort 地址，不再出现 ERR_EMPTY_RESPONSE。

## 6. 注意事项

- NodePort 可达依赖节点网络与安全组/防火墙；若跨网段访问，请额外放通 30000-32767 或具体 NodePort。
- 若使用严格 NetworkPolicy，务必保留 LAN ipBlock 放行规则，否则会复现“本机可通、外部不通”。
- 若集群非 traefik/nginx，请同步调整 ingress_allow_namespaces 逻辑。

## 7. 从0一键部署回归建议

若迁移后稳定性存疑，建议直接执行“清理 -> 重建 -> 验收”闭环，而不是只做增量修复：

```bash
bash deploy/lan-access.sh reset-all --context default --lan-ip <LAN_IP>
bash deploy/lan-access.sh bootstrap --context default --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh sync-instances --context default --lan-ip <LAN_IP> --ingress-class traefik
bash deploy/lan-access.sh verify-services --context default --lan-ip <LAN_IP>
```

如果涉及 OpenClaw 镜像升级，务必同时导入 `v版本` 和无 `v` 版本 tag，避免拉取标签不一致。

## 8. 关联文档

1. 彻底清理与从0部署：`docs/彻底清理环境与从0一键部署指南.md`
2. 多机部署落地：`docs/LAN-ACCESS-多机部署操作说明.md`
3. 构建与 tag 策略：`docs/OPENCLAW-CUSTOM-BUILD.md`
4. 总盘点与跨分支复用：`docs/定制开发变更盘点与跨分支复用指南.md`
