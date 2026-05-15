#!/bin/bash
# build-source-simple.sh - 简化版源码构建脚本
# 先用 npm 安装官方版确保可运行，然后用源码覆盖
#
# 用法:
#   ./build-source-simple.sh --source-path ../openclaw --version 2026.4.24
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ========== 参数解析 ==========
VERSION=""
SOURCE_PATH=""
IMAGE_NAME=""
BUILD_ONLY=false

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
    --image)
      IMAGE_NAME="$2"
      shift 2
      ;;
    --build-only)
      BUILD_ONLY=true
      shift
      ;;
    *)
      echo "未知参数: $1"
      echo "用法: ./build-source-simple.sh --source-path <path> --version <ver>"
      exit 1
      ;;
  esac
done

# 验证参数
if [[ -z "${VERSION}" ]]; then
  echo "错误: 必须指定 --version"
  exit 1
fi

if [[ -z "${SOURCE_PATH}" ]]; then
  echo "错误: 必须指定 --source-path (OpenClaw 源码目录)"
  exit 1
fi

# 转换为绝对路径
if [[ "${SOURCE_PATH}" != /* ]]; then
  SOURCE_PATH="$(pwd)/${SOURCE_PATH}"
fi

if [[ ! -d "${SOURCE_PATH}" ]]; then
  echo "错误: 源码目录不存在: ${SOURCE_PATH}"
  exit 1
fi

if [[ ! -f "${SOURCE_PATH}/package.json" ]]; then
  echo "错误: 源码目录中找不到 package.json: ${SOURCE_PATH}"
  exit 1
fi

# 设置默认镜像名
if [[ -z "${IMAGE_NAME}" ]]; then
  IMAGE_NAME="nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v${VERSION}"
fi

echo ""
log_info "========================================================================"
log_info "  OpenClaw 源码构建（简化版）"
log_info "========================================================================"
log_info "  源码目录: ${SOURCE_PATH}"
log_info "  版本号:   ${VERSION}"
log_info "  镜像名:   ${IMAGE_NAME}"
log_info "========================================================================"
echo ""

# ========== 源码处理：复制到构建上下文 ==========
TEMP_SOURCE_DIR="${SCRIPT_DIR}/_temp_openclaw_source"
log_info "准备源码..."

# 清理旧目录
if [[ -d "${TEMP_SOURCE_DIR}" ]]; then
  rm -rf "${TEMP_SOURCE_DIR}"
fi

# 复制源码（排除 node_modules 和 .git 节省空间）
mkdir -p "${TEMP_SOURCE_DIR}"
cd "${SOURCE_PATH}"
tar --exclude='node_modules' --exclude='.git' --exclude='dist' \
    --exclude='.github' --exclude='.husky' --exclude='.vscode' \
    -cf - . | (cd "${TEMP_SOURCE_DIR}" && tar -xf -)

log_info "源码已复制到构建上下文"

# ========== 执行构建 ==========
echo ""
log_info "开始构建 Docker 镜像..."

DOCKERFILE_PATH="${SCRIPT_DIR}/openclaw-image/Dockerfile.source-simple"

docker_build "${SCRIPT_DIR}" "${IMAGE_NAME}" \
  -f "${DOCKERFILE_PATH}" \
  --build-arg OPENCLAW_SOURCE_PATH="_temp_openclaw_source" \
  --build-arg IMAGE_VERSION="v${VERSION}"

# ========== 验证镜像 ==========
echo ""
log_info "验证镜像..."

echo ""
log_info "Node.js 版本:"
docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'node --version' 2>&1 || log_warn "Node.js 验证跳过"

echo ""
log_info "OpenClaw 版本:"
docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'openclaw --version' 2>&1 || log_warn "OpenClaw 验证警告: 可能需要调整入口"

echo ""
log_info "Python 版本:"
docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'python3 --version'

# ========== 推送 ==========
if [[ "${BUILD_ONLY}" == "true" ]]; then
  echo ""
  log_info "仅构建模式，跳过推送"
else
  echo ""
  log_info "推送镜像到仓库..."
  docker_push "${IMAGE_NAME}"
  log_success "镜像推送完成"
fi

# ========== 清理 ==========
echo ""
log_info "清理临时文件..."
rm -rf "${TEMP_SOURCE_DIR}"

# ========== 完成总结 ==========
log_success "========================================================================"
log_success "  构建完成！"
log_success "========================================================================"
echo ""
echo "镜像信息:"
echo "  名称: ${IMAGE_NAME}"
echo "  版本: v${VERSION}"
echo ""
echo "源码信息:"
echo "  源目录: ${SOURCE_PATH}"
echo "  源码已复制到镜像: /opt/openclaw/src/"
echo ""
echo "在 NoDeskClaw 中使用:"
echo "  1. 进入管理后台 → 引擎版本 → 新增版本"
echo "  2. Runtime: openclaw"
echo "  3. 版本号: ${VERSION}"
echo "  4. 镜像 Tag: v${VERSION}"
echo "  5. 创建实例时选择此版本即可"
echo ""
echo "快速测试命令:"
echo "  docker run --rm -it -p 18789:18789 ${IMAGE_NAME}"
echo ""
echo "注意: 如果你想使用源码而非官方安装版本，可以修改 docker-entrypoint.sh:"
echo "  把 exec openclaw gateway ... 改为 exec node /opt/openclaw/src/bin/openclaw.js gateway ..."
echo ""
echo "========================================================================"
