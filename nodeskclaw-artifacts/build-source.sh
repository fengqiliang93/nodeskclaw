#!/bin/bash
# build-source.sh — 从 OpenClaw 源码构建镜像
#
# 用法:
#   ./build-source.sh <engine> --source-path <path> --version <ver> [--build-only] [--skip-verify]
#
# 示例:
#   ./build-source.sh openclaw --source-path ../openclaw --version 2026.3.1-custom
#   ./build-source.sh openclaw --source-path ../openclaw --version 2026.3.1 --build-only
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ENGINE="$1"; shift || true
if [ -z "${ENGINE}" ]; then
  log_error "用法: ./build-source.sh <engine> --source-path <path> --version <ver> [--build-only] [--skip-verify]"
  log_info "可用引擎: openclaw"
  exit 1
fi

ENGINE_DIR="${SCRIPT_DIR}/${ENGINE}-image"
if [ ! -d "${ENGINE_DIR}" ]; then
  log_error "引擎目录不存在: ${ENGINE_DIR}"
  exit 1
fi

check_docker

# 解析参数
SOURCE_PATH=""
VERSION=""
BUILD_ONLY=false
SKIP_VERIFY=false
MIRRORS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-path)
      SOURCE_PATH="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --build-only)
      BUILD_ONLY=true
      shift
      ;;
    --skip-verify)
      SKIP_VERIFY=true
      shift
      ;;
    --mirrors)
      MIRRORS="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

if [ -z "${SOURCE_PATH}" ]; then
  log_error "必须指定 --source-path（OpenClaw 源码目录路径）"
  exit 1
fi

if [ -z "${VERSION}" ]; then
  log_error "必须指定 --version（镜像版本号，如 2026.3.1-custom）"
  exit 1
fi

# 转换为绝对路径
if [[ "${SOURCE_PATH}" != /* ]]; then
  SOURCE_PATH="$(pwd)/${SOURCE_PATH}"
fi

if [ ! -d "${SOURCE_PATH}" ]; then
  log_error "源码目录不存在: ${SOURCE_PATH}"
  exit 1
fi

if [ ! -f "${SOURCE_PATH}/package.json" ]; then
  log_error "源码目录中找不到 package.json: ${SOURCE_PATH}"
  exit 1
fi

load_mirrors

REGISTRY="$(registry_for "${ENGINE}")"
IMAGE_TAG="v${VERSION}"

print_build_summary "${ENGINE} (Source Build)" "${VERSION}" "${REGISTRY}" "linux/amd64" "source"

echo "  源码路径: ${SOURCE_PATH}"
echo ""

# 构建（context 是上级目录，这样可以引用 openclaw 源码）
CONTEXT_DIR="$(dirname "${SCRIPT_DIR}")"
DOCKERFILE_PATH="${ENGINE_DIR}/Dockerfile.source"

# 计算相对路径（相对于 CONTEXT_DIR）
REL_SOURCE_PATH="$(realpath --relative-to="${CONTEXT_DIR}" "${SOURCE_PATH}")"

log_info "构建上下文: ${CONTEXT_DIR}"
log_info "相对源码路径: ${REL_SOURCE_PATH}"

docker_build "${CONTEXT_DIR}" "${REGISTRY}:${IMAGE_TAG}" \
  -f "${DOCKERFILE_PATH}" \
  --build-arg OPENCLAW_SOURCE_PATH="${REL_SOURCE_PATH}" \
  --build-arg IMAGE_VERSION="${IMAGE_TAG}"

# --- 验证（可选）---
if [ "${SKIP_VERIFY}" = false ]; then
  log_info "验证镜像..."
  echo "  Node.js: $(docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${REGISTRY}:${IMAGE_TAG}" -c 'node --version')"
  echo "  OpenClaw: $(docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${REGISTRY}:${IMAGE_TAG}" -c 'openclaw --version' 2>&1 || echo "验证失败")"
  echo "  版本标记: $(docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${REGISTRY}:${IMAGE_TAG}" -c 'cat /root/.openclaw-version')"
fi

# --- 推送 ---
log_success "构建完成"

if [ "${BUILD_ONLY}" = true ]; then
  log_info "仅构建模式，跳过推送"
  echo ""
  echo "下一步:"
  echo "  1. 推送到仓库: docker push ${REGISTRY}:${IMAGE_TAG}"
  echo "  2. 在 NoDeskClaw 中配置镜像仓库:"
  echo "     - 系统设置 -> 镜像仓库: ${REGISTRY}"
  echo "     - 引擎版本 -> 新增版本: ${IMAGE_TAG}"
  echo ""
  exit 0
fi

docker_push "${REGISTRY}:${IMAGE_TAG}"
print_done "${REGISTRY}:${IMAGE_TAG}"

echo ""
echo "============================================================"
echo "  在 NoDeskClaw 中使用自定义镜像"
echo "============================================================"
echo "  1. 确认镜像仓库地址已配置:"
echo "     系统设置 -> 配置管理 -> image_registry"
echo "     当前默认: nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw"
echo ""
echo "  2. 在引擎版本中新增版本:"
echo "     管理后台 -> 引擎版本 -> 新增版本"
echo "     - runtime: openclaw"
echo "     - 版本号: ${VERSION}"
echo "     - 镜像 tag: ${IMAGE_TAG}"
echo "     - 状态: published"
echo ""
echo "  3. 创建/升级实例时选择该版本即可"
echo "============================================================"
