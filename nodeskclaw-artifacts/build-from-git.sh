#!/bin/bash
# build-from-git.sh - 从 Git 仓库自动克隆并构建 OpenClaw 镜像
#
# 用法:
#   ./build-from-git.sh --version 2026.3.1-custom
#   ./build-from-git.sh --repo https://github.com/your-org/openclaw --branch dev --version 2026.3.1-dev
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

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ========== 参数解析 ==========
show_help() {
  echo "用法: ./build-from-git.sh [选项]"
  echo ""
  echo "必需参数:"
  echo "  --version VERSION       镜像版本号（如 2026.3.1-custom）"
  echo ""
  echo "可选参数:"
  echo "  --repo URL              Git 仓库地址（默认: https://github.com/openclaw/openclaw）"
  echo "  --branch NAME           Git 分支/标签（默认: 检测最新 tag）"
  echo "  --image NAME            完整镜像名"
  echo "  --clone-dir PATH        克隆目录（默认: ./openclaw-src）"
  echo "  --full                  构建完整功能版（默认）"
  echo "  --base                  构建基础版（无额外工具）"
  echo "  --build-only            仅构建不推送"
  echo "  --clean                 构建后删除克隆目录"
  echo "  -h, --help              显示帮助"
  echo ""
  echo "示例:"
  echo "  # 构建最新 tag 的完整功能版"
  echo "  ./build-from-git.sh --version 2026.3.1-custom"
  echo ""
  echo "  # 构建指定分支"
  echo "  ./build-from-git.sh --branch dev --version 2026.3.1-dev"
  exit 0
}

# 初始化变量
GIT_REPO="https://github.com/openclaw/openclaw"
GIT_BRANCH=""
VERSION=""
IMAGE_NAME=""
CLONE_DIR="${SCRIPT_DIR}/openclaw-src"
BUILD_MODE="full"
BUILD_ONLY=false
CLEAN_AFTER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      GIT_REPO="$2"
      shift 2
      ;;
    --branch)
      GIT_BRANCH="$2"
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
    --clone-dir)
      CLONE_DIR="$2"
      shift 2
      ;;
    --full)
      BUILD_MODE="full"
      shift
      ;;
    --base)
      BUILD_MODE="base"
      shift
      ;;
    --build-only)
      BUILD_ONLY=true
      shift
      ;;
    --clean)
      CLEAN_AFTER=true
      shift
      ;;
    -h|--help)
      show_help
      ;;
    *)
      echo "未知参数: $1"
      show_help
      ;;
  esac
done

# 验证参数
if [[ -z "${VERSION}" ]]; then
  echo "错误: 必须指定 --version"
  show_help
fi

echo ""
log_info "========================================================================"
log_info "  OpenClaw Git 自动构建"
log_info "========================================================================"
echo ""
log_info "仓库:       ${GIT_REPO}"
log_info "分支:       ${GIT_BRANCH:-<自动检测最新 tag>}"
log_info "版本:       ${VERSION}"
log_info "构建模式:   ${BUILD_MODE}"
log_info "克隆目录:   ${CLONE_DIR}"
echo ""

# ========== 清理旧目录 ==========
if [[ -d "${CLONE_DIR}" ]]; then
  warn "克隆目录已存在，将删除: ${CLONE_DIR}"
  rm -rf "${CLONE_DIR}"
fi

# ========== 克隆代码 ==========
log_info "克隆 Git 仓库..."

if [[ -n "${GIT_BRANCH}" ]]; then
  git clone --depth 1 --branch "${GIT_BRANCH}" "${GIT_REPO}" "${CLONE_DIR}"
else
  # 自动检测最新 tag
  git clone --depth 50 "${GIT_REPO}" "${CLONE_DIR}"
  cd "${CLONE_DIR}"
  LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "main")
  info "自动检测到最新 tag: ${LATEST_TAG}"
  git checkout "${LATEST_TAG}"
  cd "${SCRIPT_DIR}"
fi

log_success "代码克隆完成"

# ========== 验证源码 ==========
if [[ ! -f "${CLONE_DIR}/package.json" ]]; then
  echo "错误: 克隆的仓库中找不到 package.json"
  exit 1
fi

REPO_VERSION=$(grep -o '"version": *"[^"]*"' "${CLONE_DIR}/package.json" | cut -d'"' -f4)
log_info "仓库版本: ${REPO_VERSION}"

# ========== 执行构建 ==========
echo ""
log_info "开始构建..."

BUILD_ARGS=()
BUILD_ARGS+=(--source-path "${CLONE_DIR}")
BUILD_ARGS+=(--version "${VERSION}")

if [[ "${BUILD_ONLY}" == "true" ]]; then
  BUILD_ARGS+=(--build-only)
fi

if [[ -n "${IMAGE_NAME}" ]]; then
  BUILD_ARGS+=(--image "${IMAGE_NAME}")
fi

if [[ "${BUILD_MODE}" == "full" ]]; then
  # 使用 build-full.sh
  if [[ -f "${SCRIPT_DIR}/build-full.env" ]]; then
    BUILD_ARGS+=(--config "${SCRIPT_DIR}/build-full.env")
  fi
  "${SCRIPT_DIR}/build-full.sh" "${BUILD_ARGS[@]}"
else
  # 使用 build-source.sh（基础版）
  "${SCRIPT_DIR}/build-source.sh" "${BUILD_ARGS[@]}"
fi

# ========== 清理 ==========
if [[ "${CLEAN_AFTER}" == "true" ]]; then
  echo ""
  info "清理克隆目录..."
  rm -rf "${CLONE_DIR}"
  success "清理完成"
fi

echo ""
log_success "构建完成！"
echo ""
echo "提示: 如需再次构建相同代码，下次可以直接使用:"
if [[ "${BUILD_MODE}" == "full" ]]; then
  echo "  ./build-full.sh --source-path ${CLONE_DIR} --version ${VERSION}"
else
  echo "  ./build-source.sh --source-path ${CLONE_DIR} --version ${VERSION}"
fi
echo ""
