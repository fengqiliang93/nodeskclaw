#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

KUBE_CONTEXT="${KUBE_CONTEXT:-default}"
STAGING_NS="${STAGING_NS:-nodeskclaw-staging}"
INSTANCE_NS_PREFIX="${INSTANCE_NS_PREFIX:-nodeskclaw-default-}"
LLM_PROXY_IMAGE="${LLM_PROXY_IMAGE:-nodeskclaw-llm-proxy:local}"
BACKEND_IMAGE="${BACKEND_IMAGE:-nodeskclaw-backend:local}"
PORTAL_IMAGE="${PORTAL_IMAGE:-nodeskclaw-portal:local}"
LLM_TARGET_BASE_URL="${LLM_TARGET_BASE_URL:-http://<LAN_IP>:3000/v1}"
LLM_API_KEY="${LLM_API_KEY:-sk-local-placeholder}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/nodeskclaw-backend/.env}"
KUBECONFIG_FILE="${KUBECONFIG_FILE:-$HOME/.kube/config}"
PORTAL_NODEPORT="${PORTAL_NODEPORT:-30080}"
DEFAULT_CLUSTER_NAME="${DEFAULT_CLUSTER_NAME:-local-k3s}"
INGRESS_CLASS="${INGRESS_CLASS:-traefik}"
OPENCLAW_IMAGE_REGISTRY="${OPENCLAW_IMAGE_REGISTRY:-}"
OPENCLAW_DEFAULT_IMAGE_TAG="${OPENCLAW_DEFAULT_IMAGE_TAG:-}"
INGRESS_BASE_DOMAIN_SUFFIX="${INGRESS_BASE_DOMAIN_SUFFIX:-nip.io}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-CHANGE_ME_ADMIN_PASSWORD}"
LAN_IP="${LAN_IP:-}"
BUILD_IMAGES="${BUILD_IMAGES:-false}"
BUILD_TARGETS="${BUILD_TARGETS:-backend,portal,proxy}"
FEISHU_NODE_SELECTOR="${FEISHU_NODE_SELECTOR:-node-role.kubernetes.io/control-plane=true}"
REPAIR_FLANNEL_MTU="${REPAIR_FLANNEL_MTU:-false}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[lan-access]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK  ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ WARN ]${NC} $*"; }
err()  { echo -e "${RED}[ERROR ]${NC} $*" >&2; }

usage() {
  cat <<'EOF'
NoDeskClaw 局域网部署辅助脚本

用法:
  ./deploy/lan-access.sh <command> [options]

命令:
  import-images                      导入 tar 包或本机 Docker 镜像到 k3s containerd
  ensure-llm-proxy                  部署/更新 llm-proxy，并修复 backend LLM_PROXY 环境变量
  reset-all                         清理当前 NoDeskClaw / OpenClaw 相关部署环境
  bootstrap                         从零初始化控制台、数据库、默认集群与局域网访问配置
  sync-instances                    同步所有实例的 Ingress/NetworkPolicy/newapi 配置
  show-urls                         输出控制台与实例访问地址
  print-kubeconfig                  输出可粘贴到“添加集群”的 KubeConfig（server 自动替换为 LAN IP）
  verify-services                   校验 Portal/Backend/LLM/实例入口可达性
  check-flannel-mtu-local          检查当前节点 flannel MTU 是否一致，可选自动修复

  公共选项:
  --context <name>                  kubectl context (默认: default)
  --staging-ns <name>               staging 命名空间 (默认: nodeskclaw-staging)
  --instance-prefix <prefix>        实例命名空间前缀 (默认: nodeskclaw-default-)
  --lan-ip <ip>                     指定局域网 IP（不传则自动探测）
  --repair                          对支持的检查命令执行自动修复
  环境变量 FEISHU_NODE_SELECTOR      飞书实例节点选择器（默认: node-role.kubernetes.io/control-plane=true）

命令选项:
  import-images:
    --dir <path>                    tar 目录
    --image <name[:tag]>            本机 docker images 中的镜像，可重复传入

  ensure-llm-proxy:
    --image <name:tag>              llm-proxy 镜像（默认: nodeskclaw-llm-proxy:local）
    --llm-target-base-url <url>     llm-proxy 转发目标（默认: http://<LAN_IP>:3000/v1）
    --llm-api-key <key>             llm-proxy 转发使用的 API Key（默认: sk-local-placeholder）

  bootstrap:
    --rebuild [targets]             构建前重新 docker build，targets 逗号分隔: backend,portal,proxy（默认全部）
    --env-file <path>               backend .env 文件
    --backend-image <name:tag>      backend 镜像
    --portal-image <name:tag>       portal 镜像
    --proxy-image <name:tag>        llm-proxy 镜像
    --llm-target-base-url <url>     llm-proxy 转发目标（默认: http://<LAN_IP>:3000/v1）
    --llm-api-key <key>             llm-proxy 转发使用的 API Key（默认: sk-local-placeholder）
    --kubeconfig-file <path>        写入默认 cluster 记录用的 kubeconfig
    --portal-nodeport <port>        Portal NodePort，默认 30080
    --ingress-class <name>          默认 ingress class，默认 traefik
    --openclaw-image-registry <v>   写入 system_configs.image_registry
    --openclaw-image-tag <tag>      默认发布的 OpenClaw 镜像 tag（默认自动探测）
    --ingress-base-domain-suffix <v>实例域名后缀（默认: nip.io）
    --admin-username <name>         管理员账号（默认: admin）
    --admin-password <pwd>          管理员密码（必填，不再内置默认明文密码）

示例:
  ./deploy/lan-access.sh import-images --dir /opt/offline-images
  ./deploy/lan-access.sh import-images --image nodeskclaw-backend:local --image nodeskclaw-portal:local
  ./deploy/lan-access.sh reset-all
  ./deploy/lan-access.sh bootstrap --lan-ip <LAN_IP>
  ./deploy/lan-access.sh ensure-llm-proxy --image my-registry/nodeskclaw-llm-proxy:v1
  ./deploy/lan-access.sh sync-instances --lan-ip <LAN_IP>
  ./deploy/lan-access.sh show-urls --lan-ip <LAN_IP>
  ./deploy/lan-access.sh print-kubeconfig --lan-ip <LAN_IP>
  ./deploy/lan-access.sh verify-services --lan-ip <LAN_IP>
  sudo ./deploy/lan-access.sh check-flannel-mtu-local --repair
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "缺少命令: $1"; exit 1; }
}

detect_lan_ip() {
  if [[ -n "$LAN_IP" ]]; then
    return
  fi
  LAN_IP="$(kubectl --context "$KUBE_CONTEXT" get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')"
  if [[ -z "$LAN_IP" ]]; then
    err "自动探测 LAN IP 失败，请手动传 --lan-ip"
    exit 1
  fi
}

get_instance_namespaces() {
  kubectl --context "$KUBE_CONTEXT" get ns -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | grep "^${INSTANCE_NS_PREFIX}" || true
}

image_exists_locally() {
  docker image inspect "$1" >/dev/null 2>&1
}

import_image_source() {
  local src="$1"
  if [[ -f "$src" ]]; then
    log "导入镜像归档: $src"
    if [[ "$src" == *.tar ]]; then
      sudo k3s ctr -n k8s.io images import "$src"
    else
      gunzip -c "$src" | sudo k3s ctr -n k8s.io images import -
    fi
    return
  fi

  if image_exists_locally "$src"; then
    log "从本机 Docker 镜像导入: $src"
    docker save "$src" | sudo k3s ctr -n k8s.io images import -
    return
  fi

  err "无法识别导入源: $src"
  exit 1
}

import_images() {
  local tar_dir="$1"
  shift
  local -a sources=("$@")

  if [[ -n "$tar_dir" ]]; then
    if [[ ! -d "$tar_dir" ]]; then
      err "目录不存在: $tar_dir"
      exit 1
    fi
    mapfile -t dir_sources < <(find "$tar_dir" -maxdepth 1 -type f \( -name '*.tar' -o -name '*.tar.gz' -o -name '*.tgz' \) | sort)
    sources+=("${dir_sources[@]}")
  fi

  if [[ "${#sources[@]}" -eq 0 ]]; then
    err "未提供任何镜像导入源，请传 --dir 或 --image"
    exit 1
  fi

  log "开始导入镜像，共 ${#sources[@]} 个来源"
  for src in "${sources[@]}"; do
    import_image_source "$src"
  done
  ok "镜像导入完成"
}

build_platform_images() {
  local targets="$BUILD_TARGETS"
  local -a backend_build_args=()
  require_cmd docker

  if [[ -n "${PIP_INDEX_URL:-}" ]]; then
    backend_build_args+=(--build-arg "PIP_INDEX_URL=${PIP_INDEX_URL}")
  fi
  if [[ -n "${PIP_TRUSTED_HOST:-}" ]]; then
    backend_build_args+=(--build-arg "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}")
  fi
  if [[ -n "${APT_MIRROR:-}" ]]; then
    backend_build_args+=(--build-arg "APT_MIRROR=${APT_MIRROR}")
  fi

  if [[ "$targets" == *backend* ]]; then
    log "构建 backend 镜像: ${BACKEND_IMAGE}"
    docker build --platform linux/amd64 "${backend_build_args[@]}" -t "$BACKEND_IMAGE" \
      -f "$PROJECT_ROOT/nodeskclaw-backend/Dockerfile" "$PROJECT_ROOT"
    ok "backend 镜像构建完成"
  fi

  if [[ "$targets" == *portal* ]]; then
    log "构建 portal 镜像: ${PORTAL_IMAGE}"
    docker build --platform linux/amd64 -t "$PORTAL_IMAGE" "$PROJECT_ROOT/nodeskclaw-portal/"
    ok "portal 镜像构建完成"
  fi

  if [[ "$targets" == *proxy* ]]; then
    log "构建 llm-proxy 镜像: ${LLM_PROXY_IMAGE}"
    docker build --platform linux/amd64 -t "$LLM_PROXY_IMAGE" "$PROJECT_ROOT/nodeskclaw-llm-proxy/"
    ok "llm-proxy 镜像构建完成"
  fi
}

resolve_platform_images() {
  # 尝试方法1: 直接 k3s containerd
  if sudo -n k3s ctr -n k8s.io images ls >/dev/null 2>&1; then
    log "尝试通过 k3s containerd 直接导入镜像"
    import_images "" "$BACKEND_IMAGE" "$PORTAL_IMAGE" "$LLM_PROXY_IMAGE"
    return
  fi

  # 尝试方法2: 如果镜像是本地 Docker 镜像，导出为 tar 后用 k3s ctr 加载
  if sudo -n k3s ctr -n k8s.io image import /dev/stdin >/dev/null 2>&1 <<< ""; then
    log "尝试通过 k3s ctr 加载本地 Docker 镜像"
    local tmp_tar tmp_tar2 tmp_tar3
    tmp_tar="$(mktemp)"
    tmp_tar2="$(mktemp)"
    tmp_tar3="$(mktemp)"
    trap 'rm -f "$tmp_tar" "$tmp_tar2" "$tmp_tar3"' RETURN

    if docker save "$BACKEND_IMAGE" -o "$tmp_tar" 2>/dev/null && \
       sudo k3s ctr -n k8s.io image import "$tmp_tar" 2>/dev/null; then
      log "Backend 镜像导入成功"
    else
      warn "无法导入 Backend 镜像"
      return
    fi

    if docker save "$PORTAL_IMAGE" -o "$tmp_tar2" 2>/dev/null && \
       sudo k3s ctr -n k8s.io image import "$tmp_tar2" 2>/dev/null; then
      log "Portal 镜像导入成功"
    else
      warn "无法导入 Portal 镜像"
      return
    fi

    if docker save "$LLM_PROXY_IMAGE" -o "$tmp_tar3" 2>/dev/null && \
       sudo k3s ctr -n k8s.io image import "$tmp_tar3" 2>/dev/null; then
      log "LLM Proxy 镜像导入成功"
    else
      warn "无法导入 LLM Proxy 镜像"
      return
    fi

    return
  fi

  warn "无法加载本地镜像，K8s 将在拉取时使用默认镜像仓库"
  log "尝试回退到 ttl.sh 临时仓库（带重试）"

  push_with_retry() {
    local src="$1"
    local name_hint="$2"
    local max_try=4
    local i ref
    for ((i=1; i<=max_try; i++)); do
      ref="ttl.sh/${name_hint}-$(date +%s)-$RANDOM:12h"
      log "[$i/$max_try] 推送临时镜像: $src -> $ref" >&2
      if docker tag "$src" "$ref" >/dev/null 2>&1 && timeout 180s docker push "$ref" >/dev/null 2>&1; then
        echo "$ref"
        return 0
      fi
      warn "推送失败，准备重试: $src" >&2
    done
    return 1
  }

  local backend_ref portal_ref proxy_ref
  backend_ref="$(push_with_retry "$BACKEND_IMAGE" "nodeskclaw-backend")" || {
    err "无法推送 backend 镜像到 ttl.sh"
    return 1
  }
  portal_ref="$(push_with_retry "$PORTAL_IMAGE" "nodeskclaw-portal")" || {
    err "无法推送 portal 镜像到 ttl.sh"
    return 1
  }
  proxy_ref="$(push_with_retry "$LLM_PROXY_IMAGE" "nodeskclaw-llm-proxy")" || {
    err "无法推送 llm-proxy 镜像到 ttl.sh"
    return 1
  }

  BACKEND_IMAGE="$backend_ref"
  PORTAL_IMAGE="$portal_ref"
  LLM_PROXY_IMAGE="$proxy_ref"
  ok "已切换为 ttl.sh 临时镜像"
}

detect_openclaw_image_defaults() {
  if [[ -n "$OPENCLAW_IMAGE_REGISTRY" && -n "$OPENCLAW_DEFAULT_IMAGE_TAG" ]]; then
    return
  fi

  local refs
  refs="$(sudo k3s ctr -n k8s.io images ls 2>/dev/null | awk 'NR>1{print $1}' || true)"
  while IFS= read -r ref; do
    [[ -z "$ref" ]] && continue
    [[ "$ref" == *@sha256:* ]] && continue
    if [[ "$ref" == *deskclaw-openclaw:* ]]; then
      if [[ -z "$OPENCLAW_IMAGE_REGISTRY" ]]; then
        OPENCLAW_IMAGE_REGISTRY="${ref%:*}"
      fi
      if [[ -z "$OPENCLAW_DEFAULT_IMAGE_TAG" ]]; then
        OPENCLAW_DEFAULT_IMAGE_TAG="${ref##*:}"
      fi
      break
    fi
  done <<< "$refs"

  OPENCLAW_IMAGE_REGISTRY="${OPENCLAW_IMAGE_REGISTRY:-nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw}"
  OPENCLAW_DEFAULT_IMAGE_TAG="${OPENCLAW_DEFAULT_IMAGE_TAG:-v2026.3.13}"
}

reset_all() {
  mapfile -t namespaces < <(get_instance_namespaces)
  namespaces+=("$STAGING_NS")

  for ns in "${namespaces[@]}"; do
    if kubectl --context "$KUBE_CONTEXT" get ns "$ns" >/dev/null 2>&1; then
      log "删除命名空间: $ns"
      kubectl --context "$KUBE_CONTEXT" delete ns "$ns" --wait=false
    fi
  done

  for ns in "${namespaces[@]}"; do
    if kubectl --context "$KUBE_CONTEXT" get ns "$ns" >/dev/null 2>&1; then
      log "等待命名空间删除: $ns"
      kubectl --context "$KUBE_CONTEXT" wait --for=delete ns/"$ns" --timeout=240s || true
    fi
  done

  ok "现有部署环境已清理"
}

ensure_postgres() {
  kubectl --context "$KUBE_CONTEXT" get ns "$STAGING_NS" >/dev/null 2>&1 || kubectl --context "$KUBE_CONTEXT" create ns "$STAGING_NS"

  cat <<'EOF' | kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" apply -f -
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
spec:
  selector:
    app: nodeskclaw-postgres
  ports:
  - port: 5432
    targetPort: 5432
EOF

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout status deploy/nodeskclaw-postgres --timeout=240s
}

prepare_env_file() {
  local src="$1"
  local dest="$2"
  local admin_username="$3"
  cp "$src" "$dest"
  python3 - "$dest" "$admin_username" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
admin_username = sys.argv[2].strip() or "admin"
raw = path.read_text(encoding="utf-8").splitlines()
override = {
     "DATABASE_URL": "postgresql+asyncpg://nodeskclaw:nodeskclaw@nodeskclaw-postgres.nodeskclaw-staging.svc.cluster.local:5432/nodeskclaw",
     "LLM_PROXY_URL": "http://nodeskclaw-llm-proxy.nodeskclaw-staging.svc.cluster.local",
     "LLM_PROXY_INTERNAL_URL": "http://nodeskclaw-llm-proxy.nodeskclaw-staging.svc.cluster.local",
     "AGENT_API_BASE_URL": "http://nodeskclaw-backend.nodeskclaw-staging.svc.cluster.local:8000/api/v1",
      "TUNNEL_BASE_URL": "ws://nodeskclaw-backend.nodeskclaw-staging.svc.cluster.local:8000/api/v1/tunnel/connect",
      "FEISHU_NODE_SELECTOR": os.environ.get("FEISHU_NODE_SELECTOR", "node-role.kubernetes.io/control-plane=true"),
      "INIT_ADMIN_ACCOUNT": admin_username,
  }
kept = []
seen = set()
for line in raw:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    key = stripped.split("=", 1)[0].strip()
    if key in override or key == "NODESKCLAW_EDITION":
        continue
    if key in seen:
        continue
    kept.append(stripped)
    seen.add(key)
for key, value in override.items():
    kept.append(f"{key}={value}")
path.write_text("\n".join(kept) + "\n", encoding="utf-8")
PY
}

patch_platform_images() {
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" set image deploy/nodeskclaw-backend nodeskclaw-backend="$BACKEND_IMAGE"
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" set image deploy/nodeskclaw-portal nodeskclaw-portal="$PORTAL_IMAGE"
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" patch deploy nodeskclaw-backend --type json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" patch deploy nodeskclaw-portal --type json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"IfNotPresent"}]'
}

ensure_portal_nodeport() {
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" patch svc nodeskclaw-portal --type merge -p "
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 80
      protocol: TCP
      nodePort: ${PORTAL_NODEPORT}
"
}

wait_platform_ready() {
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout status deploy/nodeskclaw-backend --timeout=300s
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout status deploy/nodeskclaw-portal --timeout=300s
}

bootstrap_backend_state() {
  local admin_password="$1"
  local kubeconfig_b64
  kubeconfig_b64="$(base64 -w0 "$KUBECONFIG_FILE")"

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" exec -i deploy/nodeskclaw-backend -- env \
    LAN_IP="$LAN_IP" \
    INGRESS_CLASS="$INGRESS_CLASS" \
    KUBECONFIG_B64="$kubeconfig_b64" \
    ADMIN_PASSWORD="$admin_password" \
    ADMIN_USERNAME="$ADMIN_USERNAME" \
    DEFAULT_CLUSTER_NAME="$DEFAULT_CLUSTER_NAME" \
    OPENCLAW_IMAGE_REGISTRY="$OPENCLAW_IMAGE_REGISTRY" \
    OPENCLAW_DEFAULT_IMAGE_TAG="$OPENCLAW_DEFAULT_IMAGE_TAG" \
    INGRESS_BASE_DOMAIN_SUFFIX="$INGRESS_BASE_DOMAIN_SUFFIX" \
    /app/.venv/bin/python - <<'PY'
if True:
  import asyncio
  import base64
  import os
  from sqlalchemy import select

  from app.core.deps import async_session_factory
  from app.core.security import encrypt_kubeconfig
  from app.models.cluster import Cluster
  from app.models.engine_version import EngineVersion
  from app.models.organization import Organization
  from app.models.system_config import SystemConfig
  from app.models.user import User
  from app.services.auth_service import _hash_password
  from app.services.cluster_service import _parse_kubeconfig_meta


  async def main():
    async with async_session_factory() as db:
      admin = (await db.execute(
        select(User).where(
          User.username == os.environ.get("ADMIN_USERNAME", "admin"),
          User.deleted_at.is_(None),
        )
      )).scalar_one()

      admin.password_hash = _hash_password(os.environ["ADMIN_PASSWORD"])
      admin.must_change_password = False

      configs = {
        "ingress_base_domain": f"{os.environ['LAN_IP']}.{os.environ.get('INGRESS_BASE_DOMAIN_SUFFIX', 'nip.io')}",
        "ingress_subdomain_suffix": "",
        "ingress_tls_enabled": "false",
        "network_policy_ingress_enabled": "false",
        "network_policy_egress_enabled": "true",
      }
      image_registry = os.environ.get("OPENCLAW_IMAGE_REGISTRY")
      if image_registry:
        configs["image_registry"] = image_registry

      for key, value in configs.items():
        row = (await db.execute(
          select(SystemConfig).where(SystemConfig.key == key, SystemConfig.deleted_at.is_(None))
        )).scalar_one_or_none()
        if row is None:
          db.add(SystemConfig(key=key, value=value))
        else:
          row.value = value

      org = (await db.execute(
        select(Organization).where(Organization.deleted_at.is_(None)).order_by(Organization.created_at.asc())
      )).scalars().first()

      kubeconfig = base64.b64decode(os.environ["KUBECONFIG_B64"]).decode()
      lan_ip = os.environ.get("LAN_IP", "")
      if lan_ip:
        kubeconfig = kubeconfig.replace("https://127.0.0.1:6443", f"https://{lan_ip}:6443")
      api_server_url, auth_type = _parse_kubeconfig_meta(kubeconfig)
      cluster = (await db.execute(
        select(Cluster).where(
          Cluster.name == os.environ["DEFAULT_CLUSTER_NAME"],
          Cluster.deleted_at.is_(None),
        )
      )).scalar_one_or_none()

      provider_config = {
        "cloud_vendor": "custom",
        "auth_type": auth_type,
        "api_server_url": api_server_url,
        "ingress_class": os.environ["INGRESS_CLASS"],
      }

      if cluster is None:
        cluster = Cluster(
          name=os.environ["DEFAULT_CLUSTER_NAME"],
          compute_provider="k8s",
          status="connected",
          health_status="healthy",
          credentials_encrypted=encrypt_kubeconfig(kubeconfig),
          provider_config=provider_config,
          created_by=admin.id,
          org_id=org.id if org else admin.current_org_id,
        )
        db.add(cluster)
      else:
        cluster.compute_provider = "k8s"
        cluster.status = "connected"
        cluster.health_status = "healthy"
        cluster.credentials_encrypted = encrypt_kubeconfig(kubeconfig)
        cluster.provider_config = provider_config
        if org is not None:
          cluster.org_id = org.id

      default_tag = os.environ.get("OPENCLAW_DEFAULT_IMAGE_TAG", "v2026.3.13")
      default_version = default_tag[1:] if default_tag.startswith("v") else default_tag
      versions = (await db.execute(
        select(EngineVersion).where(
          EngineVersion.runtime == "openclaw",
          EngineVersion.deleted_at.is_(None),
        )
      )).scalars().all()

      if not versions:
        db.add(EngineVersion(
          runtime="openclaw",
          version=default_version,
          image_tag=default_tag,
          status="published",
          is_default=True,
          published_by=admin.id,
          release_notes="bootstrap auto publish",
        ))
      else:
        picked = versions[0]
        for ev in versions:
          ev.is_default = False
          if ev.image_tag == default_tag:
            picked = ev
        picked.is_default = True
        picked.status = "published"
        picked.image_tag = default_tag
        picked.version = default_version

      await db.commit()


  asyncio.run(main())
PY
}

force_sync_admin_password() {
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" exec -i deploy/nodeskclaw-backend -- env \
  ADMIN_USERNAME="$ADMIN_USERNAME" \
  ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  /app/.venv/bin/python - <<'PY'
if True:
  import asyncio
  import os
  from sqlalchemy import select

  from app.core.deps import async_session_factory
  from app.models.user import User
  from app.services.auth_service import _hash_password


  async def main():
    async with async_session_factory() as db:
      user = (await db.execute(
        select(User).where(User.username == os.environ.get("ADMIN_USERNAME", "admin"), User.deleted_at.is_(None))
      )).scalar_one_or_none()

      if user is None:
        raise SystemExit("admin user not found")

      user.password_hash = _hash_password(os.environ["ADMIN_PASSWORD"])
      user.must_change_password = False
      await db.commit()


  asyncio.run(main())
PY
}

bootstrap() {
  detect_lan_ip
  require_cmd docker
  require_cmd python3

  if [[ "$ADMIN_PASSWORD" == "CHANGE_ME_ADMIN_PASSWORD" ]]; then
    err "请显式传入 --admin-password 或设置环境变量 ADMIN_PASSWORD，禁止使用仓库内置默认密码"
    exit 1
  fi

  if [[ ! -f "$ENV_FILE" ]]; then
    err "环境变量文件不存在: $ENV_FILE"
    exit 1
  fi
  if [[ ! -f "$KUBECONFIG_FILE" ]]; then
    err "kubeconfig 文件不存在: $KUBECONFIG_FILE"
    exit 1
  fi

  if [[ "$BUILD_IMAGES" == "true" ]]; then
    build_platform_images
  fi

  resolve_platform_images
  detect_openclaw_image_defaults
  ensure_postgres

  local tmp_env
  tmp_env="$(mktemp)"
  export FEISHU_NODE_SELECTOR
  prepare_env_file "$ENV_FILE" "$tmp_env" "$ADMIN_USERNAME"

  log "初始化 staging 资源"
  (cd "$PROJECT_ROOT" && ./deploy/cli.sh init --context "$KUBE_CONTEXT" --env-file "$tmp_env" --force)

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout restart deploy/nodeskclaw-backend >/dev/null 2>&1 || true
  patch_platform_images
  ensure_portal_nodeport
  wait_platform_ready
  ensure_llm_proxy

  local admin_password
  admin_password="$ADMIN_PASSWORD"

  bootstrap_backend_state "$admin_password"

  if ! verify_portal_login; then
    err "管理员账号校验失败，请检查启动日志与数据库状态"
    exit 1
  fi

  ok "bootstrap 完成"
  echo "管理员账号: ${ADMIN_USERNAME}"
  echo "管理员密码: <已按输入值设置>"
  echo "Portal 地址: http://${LAN_IP}:${PORTAL_NODEPORT}"
  echo "实例基础域名: *.${LAN_IP}.${INGRESS_BASE_DOMAIN_SUFFIX}"
  echo "镜像仓库: ${OPENCLAW_IMAGE_REGISTRY}"
  echo "默认引擎版本: ${OPENCLAW_DEFAULT_IMAGE_TAG}"
  echo "飞书节点选择器: ${FEISHU_NODE_SELECTOR}"
}

verify_portal_login() {
  detect_lan_ip
  local resp
  local attempts=6
  local i
  local repaired=0

  for ((i=1; i<=attempts; i++)); do
    resp="$(curl -s --max-time 10 "http://${LAN_IP}:${PORTAL_NODEPORT}/api/v1/auth/account-login" \
      -H 'Content-Type: application/json' \
      -d "{\"account\":\"${ADMIN_USERNAME}\",\"password\":\"${ADMIN_PASSWORD}\"}" || true)"

    if echo "$resp" | grep -Eq '"code":(0|200)|"access_token"'; then
      if [[ "$repaired" -eq 1 ]]; then
        ok "管理员账号登录校验通过（已自动同步密码）"
      else
        ok "管理员账号登录校验通过"
      fi
      return 0
    fi

    if echo "$resp" | grep -q '"error_code":40120' && [[ "$repaired" -eq 0 ]]; then
      warn "管理员密码校验失败，尝试自动同步管理员密码后重试"
      force_sync_admin_password
      repaired=1
      continue
    fi

    if [[ "$i" -lt "$attempts" ]]; then
      sleep 2
    fi
  done

  if [[ -z "$resp" ]]; then
    warn "管理员账号登录校验未通过: <empty response>"
  else
    warn "管理员账号登录校验未通过: ${resp}"
  fi
  return 1
}

ensure_llm_proxy() {
  log "确保 llm-proxy 部署存在并可用"

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nodeskclaw-llm-proxy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nodeskclaw-llm-proxy
  template:
    metadata:
      labels:
        app: nodeskclaw-llm-proxy
    spec:
      containers:
      - name: llm-proxy
        image: ${LLM_PROXY_IMAGE}
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          value: "postgresql+asyncpg://nodeskclaw:nodeskclaw@nodeskclaw-postgres.${STAGING_NS}.svc.cluster.local:5432/nodeskclaw"
        - name: TARGET_BASE_URL
          value: "${LLM_TARGET_BASE_URL}"
        - name: API_KEY
          value: "${LLM_API_KEY}"
---
apiVersion: v1
kind: Service
metadata:
  name: nodeskclaw-llm-proxy
spec:
  selector:
    app: nodeskclaw-llm-proxy
  ports:
  - port: 80
    targetPort: 8080
EOF

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout status deploy/nodeskclaw-llm-proxy --timeout=180s

  log "修复 backend LLM_PROXY 环境变量"
  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" set env deploy/nodeskclaw-backend \
    LLM_PROXY_URL="http://nodeskclaw-llm-proxy.${STAGING_NS}.svc.cluster.local" \
    LLM_PROXY_INTERNAL_URL="http://nodeskclaw-llm-proxy.${STAGING_NS}.svc.cluster.local" \
    INIT_ADMIN_ACCOUNT="$ADMIN_USERNAME"

  kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" rollout status deploy/nodeskclaw-backend --timeout=180s
  ok "llm-proxy 与 backend LLM 配置已同步"
}

patch_instance_network_policy() {
  local ns="$1"
  local np
  np="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get networkpolicy -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  if [[ -z "$np" ]]; then
    warn "[$ns] 未找到 networkpolicy，跳过"
    return
  fi

  local allow_ns=""
  if [[ "$INGRESS_CLASS" == "traefik" ]]; then
    allow_ns="kube-system"
  elif [[ "$INGRESS_CLASS" == "nginx" ]]; then
    allow_ns="ingress-nginx"
  fi

  if [[ -z "$allow_ns" ]]; then
    return
  fi

  local tmp_json
  tmp_json="$(mktemp)"
  kubectl --context "$KUBE_CONTEXT" -n "$ns" get networkpolicy "$np" -o json > "$tmp_json"

  python3 - "$tmp_json" "$allow_ns" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
allow_ns = sys.argv[2]
obj = json.loads(path.read_text(encoding="utf-8"))
spec = obj.setdefault("spec", {})
ing = spec.setdefault("ingress", [])
if not ing:
    ing.append({"from": []})
frm = ing[0].setdefault("from", [])
target = {
    "namespaceSelector": {
        "matchLabels": {
            "kubernetes.io/metadata.name": allow_ns,
        }
    }
}
if target not in frm:
    frm.append(target)

lan_cidrs = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
for cidr in lan_cidrs:
    block = {"ipBlock": {"cidr": cidr}}
    if block not in frm:
        frm.append(block)

obj.pop("status", None)
meta = obj.get("metadata", {})
for key in ["creationTimestamp", "resourceVersion", "uid", "generation", "managedFields", "selfLink"]:
    meta.pop(key, None)
path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
PY

  kubectl --context "$KUBE_CONTEXT" -n "$ns" apply -f "$tmp_json" >/dev/null
  rm -f "$tmp_json"
  ok "[$ns] NetworkPolicy 已补齐 ${allow_ns} ingress 放行 + LAN ipBlock 放行"
}

fix_instance_ingress_backends() {
  local ns="$1"
  local ing="$2"
  local tmp_json
  tmp_json="$(mktemp)"

  kubectl --context "$KUBE_CONTEXT" -n "$ns" get ingress "$ing" -o json > "$tmp_json"

  python3 - "$tmp_json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
obj = json.loads(path.read_text(encoding="utf-8"))

spec = obj.get("spec", {})
rules = spec.get("rules", [])
for rule in rules:
    http = rule.get("http") or {}
    paths = http.get("paths") or []
    for p in paths:
        backend = p.setdefault("backend", {}).setdefault("service", {})
        port = backend.setdefault("port", {})
        route_path = p.get("path", "")
        if route_path.startswith("/sse"):
            port["number"] = 9721
            port.pop("name", None)
        elif route_path == "/":
            port["number"] = 18789
            port.pop("name", None)

obj.pop("status", None)
meta = obj.get("metadata", {})
for key in ["creationTimestamp", "resourceVersion", "uid", "generation", "managedFields", "selfLink"]:
    meta.pop(key, None)

path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
PY

  kubectl --context "$KUBE_CONTEXT" -n "$ns" apply -f "$tmp_json" >/dev/null
  rm -f "$tmp_json"
  ok "[$ns] Ingress 后端端口已校正 (/ -> 18789, /sse -> 9721)"
}

ensure_instance_lan_service() {
  local ns="$1"
  local ing="$2"
  local svc_name="$ing"
  local lan_svc_name="${svc_name}-lan"

  if ! kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "$svc_name" >/dev/null 2>&1; then
    warn "[$ns] 未找到主 Service: ${svc_name}，跳过 LAN Service 补齐"
    return
  fi

  local tmp_json
  tmp_json="$(mktemp)"
  kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "$svc_name" -o json > "$tmp_json"

  local lan_yaml
  lan_yaml="$(python3 - "$tmp_json" "$lan_svc_name" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
lan_name = sys.argv[2]
obj = json.loads(path.read_text(encoding="utf-8"))

selector = obj.get("spec", {}).get("selector") or {}

lan = {
    "apiVersion": "v1",
    "kind": "Service",
    "metadata": {
        "name": lan_name,
    },
    "spec": {
        "type": "NodePort",
        "selector": selector,
        "ports": [
            {
                "name": "gateway",
                "port": 18789,
                "targetPort": 18789,
                "protocol": "TCP",
            }
        ],
    },
}

print(json.dumps(lan, ensure_ascii=False))
PY
)"

  rm -f "$tmp_json"
  echo "$lan_yaml" | kubectl --context "$KUBE_CONTEXT" -n "$ns" apply -f - >/dev/null

  local lan_nodeport
  lan_nodeport="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "$lan_svc_name" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"
  if [[ -n "$lan_nodeport" ]]; then
    ok "[$ns] LAN 直连地址: http://${LAN_IP}:${lan_nodeport}"
  else
    warn "[$ns] LAN Service 已创建，但暂未拿到 NodePort"
  fi
}

patch_instance_newapi() {
  local ns="$1"
  local dep
  dep="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get deploy -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  if [[ -z "$dep" ]]; then
    warn "[$ns] 未找到 deployment，跳过"
    return
  fi

  kubectl --context "$KUBE_CONTEXT" -n "$ns" exec deploy/"$dep" -- sh -lc "
set -e
CFG=\"/root/.openclaw/openclaw.json\"
if [ ! -f \"\$CFG\" ]; then
  echo \"config not found: \$CFG\"
  exit 0
fi

node <<'NODE'
const fs = require('fs')
const path = '/root/.openclaw/openclaw.json'
const raw = fs.readFileSync(path, 'utf8')
const cfg = JSON.parse(raw)
if (!Array.isArray(cfg.providers)) process.exit(0)
let changed = false
for (const p of cfg.providers) {
  if (p.provider === 'newapi') {
    const expected = 'http://nodeskclaw-llm-proxy.${STAGING_NS}.svc.cluster.local/newapi/v1'
    if (p.baseUrl !== expected) {
      p.baseUrl = expected
      changed = true
    }
  }
}
if (changed) fs.writeFileSync(path, JSON.stringify(cfg, null, 2))
NODE
"

  kubectl --context "$KUBE_CONTEXT" -n "$ns" rollout restart deploy/"$dep"
  kubectl --context "$KUBE_CONTEXT" -n "$ns" rollout status deploy/"$dep" --timeout=180s
}

sync_instances() {
  detect_lan_ip
  log "同步实例 Ingress 与 newapi 配置，LAN_IP=${LAN_IP}"

  mapfile -t namespaces < <(get_instance_namespaces)
  if [[ "${#namespaces[@]}" -eq 0 ]]; then
    warn "未发现实例命名空间（前缀: ${INSTANCE_NS_PREFIX}）"
    return
  fi

  for ns in "${namespaces[@]}"; do
    local ing
    ing="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get ingress -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -z "$ing" ]]; then
      warn "[$ns] 未找到 ingress，跳过"
      continue
    fi

    local host
    host="${ing}.${LAN_IP}.${INGRESS_BASE_DOMAIN_SUFFIX}"

    log "[$ns] 修复 ingress: ${ing} -> ${host}"
    kubectl --context "$KUBE_CONTEXT" -n "$ns" patch ingress "$ing" --type merge -p "
spec:
  ingressClassName: ${INGRESS_CLASS}
  tls: []
"

    kubectl --context "$KUBE_CONTEXT" -n "$ns" patch ingress "$ing" --type json -p="[
      {
        \"op\": \"replace\",
        \"path\": \"/spec/rules/0/host\",
        \"value\": \"${host}\"
      }
    ]" >/dev/null 2>&1 || kubectl --context "$KUBE_CONTEXT" -n "$ns" patch ingress "$ing" --type json -p="[
      {
        \"op\": \"add\",
        \"path\": \"/spec/rules/0/host\",
        \"value\": \"${host}\"
      }
    ]"

    fix_instance_ingress_backends "$ns" "$ing"
    ensure_instance_lan_service "$ns" "$ing"

    patch_instance_network_policy "$ns"
    patch_instance_newapi "$ns"
    local lan_np
    lan_np="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "${ing}-lan" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"
    if [[ -n "$lan_np" ]]; then
      ok "[$ns] 实例已同步，访问地址: http://${host} | http://${LAN_IP}:${lan_np}"
    else
      ok "[$ns] 实例已同步，访问地址: http://${host}"
    fi
  done
}

show_urls() {
  detect_lan_ip

  echo ""
  echo "NoDeskClaw 访问入口"
  echo "===================="

  local admin_np
  local portal_np
  admin_np="$(kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" get svc nodeskclaw-admin -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"
  portal_np="$(kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" get svc nodeskclaw-portal -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"

  if [[ -n "$admin_np" ]]; then
    echo "控制台(EE Admin): http://${LAN_IP}:${admin_np}"
  fi
  if [[ -n "$portal_np" ]]; then
    echo "控制台(Portal):   http://${LAN_IP}:${portal_np}"
  fi
  if [[ -z "$admin_np" && -z "$portal_np" ]]; then
    echo "未找到 NodePort 控制台 Service，请先确认 nodeskclaw-admin 或 nodeskclaw-portal 服务类型。"
  fi

  echo ""
  echo "OpenClaw 实例入口"
  echo "------------------"
  mapfile -t namespaces < <(get_instance_namespaces)
  for ns in "${namespaces[@]}"; do
    local ing
    ing="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get ingress -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -n "$ing" ]]; then
      local host_url
      host_url="http://${ing}.${LAN_IP}.${INGRESS_BASE_DOMAIN_SUFFIX}"
      local lan_np
      lan_np="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "${ing}-lan" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"
      if [[ -n "$lan_np" ]]; then
        echo "${ns}: ${host_url} | http://${LAN_IP}:${lan_np}"
      else
        echo "${ns}: ${host_url}"
      fi
    fi
  done
}

verify_services() {
  detect_lan_ip

  local failed=0
  local code

  echo ""
  echo "服务可达性检查"
  echo "=============="

  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${LAN_IP}:${PORTAL_NODEPORT}/")"
  if [[ "$code" == "200" ]]; then
    ok "Portal 可达: http://${LAN_IP}:${PORTAL_NODEPORT}"
  else
    err "Portal 不可达，HTTP=${code}"
    failed=1
  fi

  local backend_ready
  backend_ready="$(kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" get deploy nodeskclaw-backend -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)"
  if [[ "$backend_ready" =~ ^[1-9][0-9]*$ ]]; then
    ok "Backend Deployment 就绪 (${backend_ready} replicas)"
  else
    err "Backend Deployment 未就绪"
    failed=1
  fi

  local proxy_ready
  proxy_ready="$(kubectl --context "$KUBE_CONTEXT" -n "$STAGING_NS" get deploy nodeskclaw-llm-proxy -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)"
  if [[ "$proxy_ready" =~ ^[1-9][0-9]*$ ]]; then
    ok "LLM Proxy Deployment 就绪 (${proxy_ready} replicas)"
  else
    err "LLM Proxy Deployment 未就绪"
    failed=1
  fi

  mapfile -t namespaces < <(get_instance_namespaces)
  for ns in "${namespaces[@]}"; do
    local ing
    ing="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get ingress -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -z "$ing" ]]; then
      warn "[$ns] 未找到 ingress，跳过"
      continue
    fi
    local host
    host="${ing}.${LAN_IP}.${INGRESS_BASE_DOMAIN_SUFFIX}"

    local host_ok=0
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${host}/")"
    if [[ "$code" == "200" ]]; then
      ok "[$ns] 域名入口可达: http://${host}"
      host_ok=1
    else
      warn "[$ns] 域名入口异常: http://${host}/ (HTTP=${code})"
    fi

    local lan_np
    lan_np="$(kubectl --context "$KUBE_CONTEXT" -n "$ns" get svc "${ing}-lan" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || true)"
    local np_ok=0
    if [[ -n "$lan_np" ]]; then
      code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${LAN_IP}:${lan_np}/")"
      if [[ "$code" == "200" ]]; then
        ok "[$ns] NodePort 入口可达: http://${LAN_IP}:${lan_np}"
        np_ok=1
      else
        warn "[$ns] NodePort 入口异常: http://${LAN_IP}:${lan_np}/ (HTTP=${code})"
      fi
    else
      warn "[$ns] 未发现 ${ing}-lan NodePort Service"
    fi

    if [[ "$host_ok" -eq 0 && "$np_ok" -eq 0 ]]; then
      err "[$ns] 实例入口均不可达（域名与 NodePort）"
      failed=1
    fi
  done

  return "$failed"
}

print_kubeconfig() {
  detect_lan_ip

  local raw
  raw="$(kubectl --context "$KUBE_CONTEXT" config view --minify --flatten)"

  if [[ -z "$raw" ]]; then
    err "读取 kubeconfig 失败，请检查 --context 是否正确"
    exit 1
  fi

  echo ""
  echo "可用于 Portal -> 组织设置 -> 集群 -> 添加集群 的 KubeConfig"
  echo "========================================================"
  echo "提示: 已将 server 地址替换为 https://${LAN_IP}:6443"
  echo ""
  echo "$raw" | sed -E "s@server: https://(127\\.0\\.0\\.1|localhost):6443@server: https://${LAN_IP}:6443@g"
}

detect_k3s_service_name() {
  if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^k3s-agent\.service'; then
    echo "k3s-agent"
    return
  fi
  if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^k3s\.service'; then
    echo "k3s"
    return
  fi
  err "未找到 k3s 或 k3s-agent systemd 服务"
  exit 1
}

check_flannel_mtu_local() {
  require_cmd systemctl

  if [[ ! -f /run/flannel/subnet.env ]]; then
    err "当前节点缺少 /run/flannel/subnet.env，flannel 可能尚未初始化"
    exit 1
  fi

  local subnet_mtu cni_mtu flannel_mtu service
  subnet_mtu="$(awk -F= '/^FLANNEL_MTU=/{print $2}' /run/flannel/subnet.env)"
  cni_mtu="$(cat /sys/class/net/cni0/mtu 2>/dev/null || true)"
  flannel_mtu="$(cat /sys/class/net/flannel.1/mtu 2>/dev/null || true)"

  if [[ -z "$subnet_mtu" ]]; then
    err "无法从 /run/flannel/subnet.env 解析 FLANNEL_MTU"
    exit 1
  fi
  if [[ -z "$cni_mtu" ]]; then
    err "当前节点缺少 cni0，无法校验 Pod 网桥 MTU"
    exit 1
  fi

  log "FLANNEL_MTU=${subnet_mtu} cni0=${cni_mtu}${flannel_mtu:+ flannel.1=${flannel_mtu}}"

  if [[ "$subnet_mtu" == "$cni_mtu" && ( -z "$flannel_mtu" || "$subnet_mtu" == "$flannel_mtu" ) ]]; then
    ok "当前节点 flannel MTU 一致"
    return 0
  fi

  warn "检测到 flannel MTU 不一致：/run/flannel/subnet.env=${subnet_mtu}，cni0=${cni_mtu}${flannel_mtu:+，flannel.1=${flannel_mtu}}"
  warn "这会导致新 Pod 使用错误的 eth0 MTU，典型现象是仅部分 HTTPS/TLS 站点超时（如 open.feishu.cn）"

  if [[ "$REPAIR_FLANNEL_MTU" != "true" ]]; then
    err "请执行: sudo ./deploy/lan-access.sh check-flannel-mtu-local --repair"
    exit 1
  fi

  service="$(detect_k3s_service_name)"
  warn "开始重启 ${service} 以重建 flannel subnet.env"
  sudo systemctl restart "$service"
  sleep 5

  subnet_mtu="$(awk -F= '/^FLANNEL_MTU=/{print $2}' /run/flannel/subnet.env)"
  cni_mtu="$(cat /sys/class/net/cni0/mtu 2>/dev/null || true)"
  flannel_mtu="$(cat /sys/class/net/flannel.1/mtu 2>/dev/null || true)"
  log "修复后 FLANNEL_MTU=${subnet_mtu} cni0=${cni_mtu}${flannel_mtu:+ flannel.1=${flannel_mtu}}"

  if [[ "$subnet_mtu" != "$cni_mtu" || ( -n "$flannel_mtu" && "$subnet_mtu" != "$flannel_mtu" ) ]]; then
    err "自动修复后 MTU 仍不一致，请继续排查节点 flannel 状态"
    exit 1
  fi

  ok "当前节点 flannel MTU 已修复"
  warn "该节点上已运行的业务 Pod 仍需重启一次；如果该节点承载了 CoreDNS 等系统 Pod，也要一起滚动重启，避免继续用旧 eth0 MTU"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

COMMAND="$1"
shift

IMPORT_DIR=""
IMPORT_IMAGE_SOURCES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context)
      KUBE_CONTEXT="$2"
      shift 2
      ;;
    --staging-ns)
      STAGING_NS="$2"
      shift 2
      ;;
    --instance-prefix)
      INSTANCE_NS_PREFIX="$2"
      shift 2
      ;;
    --lan-ip)
      LAN_IP="$2"
      shift 2
      ;;
    --image)
      if [[ "$COMMAND" == "ensure-llm-proxy" ]]; then
        LLM_PROXY_IMAGE="$2"
      else
        IMPORT_IMAGE_SOURCES+=("$2")
      fi
      shift 2
      ;;
    --dir)
      IMPORT_DIR="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --backend-image)
      BACKEND_IMAGE="$2"
      shift 2
      ;;
    --portal-image)
      PORTAL_IMAGE="$2"
      shift 2
      ;;
    --proxy-image)
      LLM_PROXY_IMAGE="$2"
      shift 2
      ;;
    --llm-target-base-url)
      LLM_TARGET_BASE_URL="$2"
      shift 2
      ;;
    --llm-api-key)
      LLM_API_KEY="$2"
      shift 2
      ;;
    --kubeconfig-file)
      KUBECONFIG_FILE="$2"
      shift 2
      ;;
    --portal-nodeport)
      PORTAL_NODEPORT="$2"
      shift 2
      ;;
    --ingress-class)
      INGRESS_CLASS="$2"
      shift 2
      ;;
    --openclaw-image-registry)
      OPENCLAW_IMAGE_REGISTRY="$2"
      shift 2
      ;;
    --openclaw-image-tag)
      OPENCLAW_DEFAULT_IMAGE_TAG="$2"
      shift 2
      ;;
    --ingress-base-domain-suffix)
      INGRESS_BASE_DOMAIN_SUFFIX="$2"
      shift 2
      ;;
    --rebuild)
      BUILD_IMAGES="true"
      if [[ $# -gt 1 && "$2" != --* ]]; then
        BUILD_TARGETS="$2"
        shift 2
      else
        shift 1
      fi
      ;;
    --admin-username)
      ADMIN_USERNAME="$2"
      shift 2
      ;;
    --admin-password)
      ADMIN_PASSWORD="$2"
      shift 2
      ;;
    --repair)
      REPAIR_FLANNEL_MTU="true"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

require_cmd kubectl

case "$COMMAND" in
  import-images)
    require_cmd docker
    import_images "$IMPORT_DIR" "${IMPORT_IMAGE_SOURCES[@]}"
    ;;
  ensure-llm-proxy)
    ensure_llm_proxy
    ;;
  reset-all)
    reset_all
    ;;
  bootstrap)
    bootstrap
    ;;
  sync-instances)
    sync_instances
    ;;
  show-urls)
    show_urls
    ;;
  print-kubeconfig)
    print_kubeconfig
    ;;
  verify-services)
    verify_services
    ;;
  check-flannel-mtu-local)
    check_flannel_mtu_local
    ;;
  *)
    err "未知命令: $COMMAND"
    usage
    exit 1
    ;;
esac
