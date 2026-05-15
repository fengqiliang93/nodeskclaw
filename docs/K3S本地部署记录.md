# K3S 本地部署记录

> 记录本仓库在本机 `k3s` 上从残留环境清理到重新部署成功的实际步骤。

## 当前结果

当前使用的 K8s 上下文：`default`

当前命名空间：`nodeskclaw-staging`

当前已运行组件：

- `nodeskclaw-backend`
- `nodeskclaw-portal`
- `nodeskclaw-postgres`

当前检查命令：

```bash
kubectl --context default -n nodeskclaw-staging get deploy,pod,svc
```

## 1. 清理旧环境

先盘点残留资源：

```bash
kubectl config get-contexts
kubectl --context default get ns
kubectl --context default get all -A | grep -Ei 'nodeskclaw|clawmanager|deskclaw' || true
kubectl --context default get pvc -A | grep -Ei 'nodeskclaw|clawmanager|deskclaw|clawreef' || true
kubectl --context default get pv | grep -Ei 'nodeskclaw|clawmanager|deskclaw|clawreef' || true
```

本次实际清理命令：

```bash
kubectl --context default delete namespace clawmanager-system clawmanager-user-1
kubectl --context default delete pv clawmanager-mysql-pv clawreef-pv-user-1-instance-2
```

## 2. 初始化部署配置

创建本地部署配置：

```bash
cat > deploy/.env.local <<'EOF'
REGISTRY="nodesk-center-cn-beijing.cr.volces.com/public"
KUBE_CONTEXT="default"
EOF
```

确认后端 `.env` 至少包含这些关键项：

- `DATABASE_URL`
- `JWT_SECRET`
- `ENCRYPTION_KEY`

检查方式：

```bash
for k in DATABASE_URL JWT_SECRET ENCRYPTION_KEY; do
  grep -q "^${k}=" nodeskclaw-backend/.env && echo "$k=SET" || echo "$k=MISSING"
done
```

## 3. 处理 `.env` 重复键

本次 `deploy/cli.sh init` 直接失败，原因是 `nodeskclaw-backend/.env` 中有重复键：

- `RESET_ADMIN_PASSWORD`

所以先生成去重后的临时文件，再拿这个文件做 `init`：

```bash
awk -F= 'BEGIN{OFS="="} /^[[:space:]]*#/ || /^[[:space:]]*$/ {next} /^[^=]+=/ {key=$1; sub(/^[[:space:]]+|[[:space:]]+$/, "", key); val=substr($0, index($0,"=")+1); data[key]=val; order[++n]=key} END{for(i=1;i<=n;i++){k=order[i]; if(!(k in seen)){seen[k]=1; last[++m]=k}} for(i=1;i<=m;i++){k=last[i]; print k, data[k]}}' nodeskclaw-backend/.env > /tmp/nodeskclaw-backend.dedup.env
```

## 4. 初始化 k3s 命名空间和基础清单

执行初始化：

```bash
./deploy/cli.sh init --context default --env-file /tmp/nodeskclaw-backend.dedup.env --force
```

初始化后会创建：

- namespace: `nodeskclaw-staging`
- secret: `nodeskclaw-backend-env`
- deployment/service: `nodeskclaw-backend`、`nodeskclaw-portal`

注意：

- `deploy/cli.sh init` 结尾可能打印 `clean_env: unbound variable`
- 这个报错来自脚本 trap，但前面的 Secret 和 Deployment 可能已经创建成功

所以要用下面命令确认真实状态，而不是只看脚本退出码：

```bash
kubectl --context default -n nodeskclaw-staging get deploy,svc,secret
```

## 5. 解决默认镜像不可拉取问题

仓库内 K8s 清单默认写死的镜像 tag 在当前环境不可拉取：

- `20260227-a195b8d`
- `20260227-ab67cbf`

`v0.8.3` 也不可直接从该公开仓库拉取。

本次采用的办法是：

1. 本地构建 backend/portal 镜像
2. 推送到 `ttl.sh` 临时仓库
3. 把 Deployment 切到 `ttl.sh` 镜像地址

### 5.1 构建 backend

```bash
docker build --network host --platform linux/amd64 \
  -f nodeskclaw-backend/Dockerfile \
  -t nodeskclaw-backend:local \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/ \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
  --build-arg APT_MIRROR=mirrors.aliyun.com \
  ./
```

### 5.2 构建 portal

```bash
docker build --network host --platform linux/amd64 \
  -f nodeskclaw-portal/Dockerfile \
  -t nodeskclaw-portal:local \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg ALPINE_MIRROR=mirrors.aliyun.com \
  nodeskclaw-portal
```

### 5.3 推送临时镜像

```bash
TS=$(date +%s)
BACKEND_IMG="ttl.sh/nodeskclaw-backend-${TS}:12h"
PORTAL_IMG="ttl.sh/nodeskclaw-portal-${TS}:12h"

docker tag nodeskclaw-backend:local "$BACKEND_IMG"
docker tag nodeskclaw-portal:local "$PORTAL_IMG"

docker push "$BACKEND_IMG"
docker push "$PORTAL_IMG"
```

### 5.4 更新 Deployment 镜像

```bash
kubectl --context default -n nodeskclaw-staging set image deployment/nodeskclaw-backend nodeskclaw-backend="$BACKEND_IMG"
kubectl --context default -n nodeskclaw-staging set image deployment/nodeskclaw-portal nodeskclaw-portal="$PORTAL_IMG"
kubectl --context default -n nodeskclaw-staging rollout restart deployment/nodeskclaw-backend deployment/nodeskclaw-portal
```

## 6. 给 backend 补 PostgreSQL

backend 初始失败原因：`.env` 里的 `DATABASE_URL` 指向了 `localhost:5432`，在 k3s Pod 内不可用。

本次直接在 `nodeskclaw-staging` 内创建 PostgreSQL：

```bash
cat <<'EOF' | kubectl --context default -n nodeskclaw-staging apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: nodeskclaw-postgres-secret
stringData:
  POSTGRES_USER: nodeskclaw
  POSTGRES_PASSWORD: nodeskclaw
  POSTGRES_DB: nodeskclaw
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nodeskclaw-postgres-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nodeskclaw-postgres
  labels:
    app: nodeskclaw-postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nodeskclaw-postgres
  template:
    metadata:
      labels:
        app: nodeskclaw-postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          envFrom:
            - secretRef:
                name: nodeskclaw-postgres-secret
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec:
              command: ["sh", "-c", "pg_isready -U $POSTGRES_USER -d $POSTGRES_DB"]
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["sh", "-c", "pg_isready -U $POSTGRES_USER -d $POSTGRES_DB"]
            initialDelaySeconds: 15
            periodSeconds: 20
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: nodeskclaw-postgres-data
---
apiVersion: v1
kind: Service
metadata:
  name: nodeskclaw-postgres
  labels:
    app: nodeskclaw-postgres
spec:
  selector:
    app: nodeskclaw-postgres
  ports:
    - port: 5432
      targetPort: 5432
      protocol: TCP
EOF
```

等待数据库启动：

```bash
kubectl --context default -n nodeskclaw-staging rollout status deployment/nodeskclaw-postgres --timeout=240s
```

## 7. 修正 backend 的 DATABASE_URL

backend Secret 不能用对 Secret YAML 做 `sed` 的方式改 `DATABASE_URL`，因为 Secret 中的值已经是 base64 编码。

正确做法是直接 patch 这个 key：

```bash
kubectl --context default -n nodeskclaw-staging patch secret nodeskclaw-backend-env --type merge -p '{"data":{"DATABASE_URL":"cG9zdGdyZXNxbCthc3luY3BnOi8vbm9kZXNrY2xhdzpub2Rlc2tjbGF3QG5vZGVza2NsYXctcG9zdGdyZXM6NTQzMi9ub2Rlc2tjbGF3"}}'
```

这个值实际对应：

```text
postgresql+asyncpg://nodeskclaw:nodeskclaw@nodeskclaw-postgres:5432/nodeskclaw
```

然后重启 backend：

```bash
kubectl --context default -n nodeskclaw-staging rollout restart deployment/nodeskclaw-backend
kubectl --context default -n nodeskclaw-staging delete pod -l app=nodeskclaw-backend --force --grace-period=0
kubectl --context default -n nodeskclaw-staging rollout status deployment/nodeskclaw-backend --timeout=360s
```

## 8. 当前怎么使用

### 8.1 查看运行状态

```bash
kubectl --context default -n nodeskclaw-staging get deploy,pod,svc
```

### 8.2 本机访问 Portal 和 Backend

如果还没配置 Ingress，直接用端口转发：

```bash
kubectl --context default -n nodeskclaw-staging port-forward svc/nodeskclaw-portal 4517:80
kubectl --context default -n nodeskclaw-staging port-forward svc/nodeskclaw-backend 4510:8000
```

访问地址：

- Portal: `http://127.0.0.1:4517`
- Backend API: `http://127.0.0.1:4510`
- Swagger: `http://127.0.0.1:4510/docs`

### 8.3 查看日志

```bash
kubectl --context default -n nodeskclaw-staging logs deployment/nodeskclaw-backend --all-pods=true --tail=200
kubectl --context default -n nodeskclaw-staging logs deployment/nodeskclaw-portal --all-pods=true --tail=200
kubectl --context default -n nodeskclaw-staging logs deployment/nodeskclaw-postgres --all-pods=true --tail=200
```

## 9. 关键注意事项

### 9.1 `ttl.sh` 镜像只有 12 小时有效

这次 backend/portal 用的是临时仓库镜像：

- `ttl.sh/nodeskclaw-backend-<timestamp>:12h`
- `ttl.sh/nodeskclaw-portal-<timestamp>:12h`

12 小时后如果 Pod 因为重建、节点重启、手动 rollout 再次拉镜像，可能会失败。

更长期的做法有两种：

1. 推到稳定可访问的镜像仓库，再更新 Deployment
2. 用 `sudo k3s ctr images import -` 把本地镜像导入 k3s containerd

### 9.2 `cr-pull-secret` 不存在

当前 Pod 事件里会看到：

```text
FailedToRetrieveImagePullSecret: cr-pull-secret
```

因为现在镜像来自公开仓库，这个告警不会阻止启动，但会一直存在。

如果后续切换到私有镜像仓库，需要补这个 Secret。

### 9.3 如果 backend 又出现 CrashLoopBackOff

优先排查：

```bash
kubectl --context default -n nodeskclaw-staging get secret nodeskclaw-backend-env -o jsonpath='{.data.DATABASE_URL}' | base64 -d; echo
kubectl --context default -n nodeskclaw-staging logs deployment/nodeskclaw-backend --all-pods=true --tail=200
kubectl --context default -n nodeskclaw-staging get pod -l app=nodeskclaw-postgres
```

## 10. 本次最终成功状态

最终校验命令：

```bash
kubectl --context default -n nodeskclaw-staging get deploy,pod,svc
```

成功结果应至少包含：

- `deployment.apps/nodeskclaw-backend 1/1`
- `deployment.apps/nodeskclaw-portal 1/1`
- `deployment.apps/nodeskclaw-postgres 1/1`
