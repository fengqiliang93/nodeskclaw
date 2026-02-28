#!/bin/bash
# 构建 amd64 架构的 OpenClaw 镜像并推送到容器镜像仓库
set -e

REGISTRY="<YOUR_REGISTRY>/<YOUR_NAMESPACE>/nodeskclaw-openclaw-base"
TAG="$(date +%Y%m%d)-$(git rev-parse --short HEAD 2>/dev/null || echo 'manual')"

echo "构建镜像: ${REGISTRY}:${TAG} (linux/amd64)"
docker build --platform linux/amd64 \
  --build-arg http_proxy= \
  --build-arg https_proxy= \
  --build-arg HTTP_PROXY= \
  --build-arg HTTPS_PROXY= \
  -t "${REGISTRY}:${TAG}" .

echo "推送镜像..."
docker push "${REGISTRY}:${TAG}"

echo "完成: ${REGISTRY}:${TAG}"
