#!/bin/bash
# build-full.sh - OpenClaw 源码完整功能构建脚本
# 支持动态自定义选项：预安装工具、浏览器自动化、Skills 等
#
# 用法:
#   ./build-full.sh --source-path ../openclaw --version 2026.3.1-custom
#
# 自定义配置文件（推荐）:
#   cp build-full.env.example build-full.env
#   # 编辑 build-full.env，然后直接运行 ./build-full.sh
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

# ========== 加载配置文件 ==========
if [[ -f "${SCRIPT_DIR}/build-full.env" ]]; then
  set -a
  source "${SCRIPT_DIR}/build-full.env"
  set +a
  log_info "已加载配置文件: build-full.env"
fi

# ========== 参数解析 ==========
show_help() {
  echo "用法: ./build-full.sh [选项]"
  echo ""
  echo "必需参数:"
  echo "  --source-path PATH      OpenClaw 源码目录路径"
  echo "  --version VERSION       镜像版本号（如 2026.3.1-custom）"
  echo ""
  echo "可选参数:"
  echo "  --image NAME            完整镜像名（默认: nodesk-center-cn-beijing.cr.volces.com/public/deskclaw-openclaw:v{VERSION}）"
  echo "  --build-only            仅构建不推送"
  echo "  --skip-verify           跳过镜像验证"
  echo "  --no-go                 不安装 Go 环境"
  echo "  --no-npm-tools          不安装 npm 全局工具"
  echo "  --no-browser            不安装浏览器自动化（Playwright + Chromium）"
  echo "  --config FILE           指定配置文件（默认: build-full.env）"
  echo "  -h, --help              显示帮助"
  echo ""
  echo "示例:"
  echo "  # 使用配置文件构建"
  echo "  ./build-full.sh --source-path ../openclaw --version 2026.3.1-custom"
  echo ""
  echo "  # 最小化构建"
  echo "  ./build-full.sh --source-path ../openclaw --version 2026.3.1-minimal --no-go --no-browser"
  exit 0
}

# 初始化变量
SOURCE_PATH=""
VERSION=""
IMAGE_NAME=""
BUILD_ONLY=false
SKIP_VERIFY=false

# 功能开关
INSTALL_GO="${INSTALL_GO:-true}"
INSTALL_NPM_TOOLS="${INSTALL_NPM_TOOLS:-true}"
INSTALL_BROWSER="${INSTALL_BROWSER:-true}"
TAG_COMPAT_ALIAS="${TAG_COMPAT_ALIAS:-true}"

# 工具版本
GO_VERSION="${GO_VERSION:-1.24.9}"
NPM_VERSION="${NPM_VERSION:-11.12.1}"

# APT 包配置
APT_PACKAGES_CORE="${APT_PACKAGES_CORE:-procps hostname curl wget git openssl ca-certificates gnupg sudo locales bash-completion}"
APT_PACKAGES_DEV="${APT_PACKAGES_DEV:-build-essential pkg-config python3 python3-pip python3-venv python3-dev cmake}"
APT_PACKAGES_BROWSER="${APT_PACKAGES_BROWSER:-chromium chromium-driver xvfb x11vnc novnc websockify}"
APT_PACKAGES_PLAYWRIGHT="${APT_PACKAGES_PLAYWRIGHT:-libgbm1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libasound2}"
APT_PACKAGES_FONTS="${APT_PACKAGES_FONTS:-fonts-liberation fonts-noto-color-emoji fonts-wqy-zenhei fonts-wqy-microhei}"
APT_PACKAGES_MEDIA="${APT_PACKAGES_MEDIA:-ffmpeg}"
APT_PACKAGES_DOCS="${APT_PACKAGES_DOCS:-poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim gnumeric libreoffice-calc csvkit}"
APT_PACKAGES_NET="${APT_PACKAGES_NET:-netcat-openbsd dnsutils iputils-ping socat traceroute mtr-tiny telnet tcpdump nmap}"
APT_PACKAGES_ARCHIVE="${APT_PACKAGES_ARCHIVE:-zip unzip p7zip-full}"
APT_PACKAGES_TERMINAL="${APT_PACKAGES_TERMINAL:-tmux vim less htop iotop jq tree ripgrep zsh fzf fd-find bat git-lfs}"
APT_PACKAGES_SCHED="${APT_PACKAGES_SCHED:-cron at}"
APT_PACKAGES_SYS="${APT_PACKAGES_SYS:-rsync strace lsof file inotify-tools}"
APT_PACKAGES_X11="${APT_PACKAGES_X11:-x11-apps x11-utils xauth dbus-x11}"
APT_PACKAGES_OTHER="${APT_PACKAGES_OTHER:-libasound2-dev sqlite3 libsqlite3-dev redis-tools postgresql-client default-mysql-client shellcheck}"
APT_PACKAGES_EXTRA="${APT_PACKAGES_EXTRA:-}"

# Python 包配置
PIP_PACKAGES_BASE="${PIP_PACKAGES_BASE:-pip setuptools wheel}"
PIP_PACKAGES_HTTP="${PIP_PACKAGES_HTTP:-requests httpx aiohttp urllib3}"
PIP_PACKAGES_CONFIG="${PIP_PACKAGES_CONFIG:-pydantic pyyaml python-dotenv}"
PIP_PACKAGES_CLI="${PIP_PACKAGES_CLI:-rich click typer tenacity invoke httpie}"
PIP_PACKAGES_DOCS="${PIP_PACKAGES_DOCS:-beautifulsoup4 lxml markdown mkdocs mkdocs-material}"
PIP_PACKAGES_OFFICE="${PIP_PACKAGES_OFFICE:-pdfplumber pymupdf python-docx openpyxl xlrd xlwt pyxlsb}"
PIP_PACKAGES_DATA="${PIP_PACKAGES_DATA:-pandas numpy jmespath jsonschema tiktoken pillow polars pyarrow}"
PIP_PACKAGES_TEST="${PIP_PACKAGES_TEST:-pytest pytest-xdist pytest-asyncio ipython black ruff mypy}"
PIP_PACKAGES_EXTRA="${PIP_PACKAGES_EXTRA:-}"

# npm 全局工具
NPM_GLOBAL_TOOLS="${NPM_GLOBAL_TOOLS:-skillhub@latest clawhub@latest typescript@latest tsx@latest yarn@latest pnpm@latest npm-check-updates@latest eslint@latest prettier@latest @biomejs/biome@latest}"

# 镜像源配置
APT_MIRROR="${APT_MIRROR:-}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
GOPROXY="${GOPROXY:-https://goproxy.cn,direct}"

# 解析命令行参数
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
    --skip-verify)
      SKIP_VERIFY=true
      shift
      ;;
    --no-go)
      INSTALL_GO=false
      shift
      ;;
    --no-npm-tools)
      INSTALL_NPM_TOOLS=false
      shift
      ;;
    --no-browser)
      INSTALL_BROWSER=false
      shift
      ;;
    --config)
      set -a
      source "$2"
      set +a
      log_info "已加载配置文件: $2"
      shift 2
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

# ========== 验证参数 ==========
if [[ -z "${SOURCE_PATH}" ]]; then
  echo "错误: 必须指定 --source-path"
  show_help
fi

if [[ -z "${VERSION}" ]]; then
  echo "错误: 必须指定 --version"
  show_help
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

# ========== 显示构建配置 ==========
echo ""
log_info "========================================================================"
log_info "  OpenClaw 完整功能镜像构建"
log_info "========================================================================"
echo ""
log_info "源码路径:   ${SOURCE_PATH}"
log_info "版本:       ${VERSION}"
log_info "镜像名:     ${IMAGE_NAME}"
echo ""
log_info "功能开关:"
log_info "  Go 环境:        ${INSTALL_GO}"
log_info "  npm 全局工具:   ${INSTALL_NPM_TOOLS}"
log_info "  浏览器自动化:   ${INSTALL_BROWSER}"
log_info "  Tag 兼容别名:   ${TAG_COMPAT_ALIAS}"
echo ""
log_info "工具版本:"
log_info "  Go:             ${GO_VERSION}"
log_info ""
log_info "镜像源:"
log_info "  APT 镜像:       ${APT_MIRROR:-<默认>}"
log_info "  PIP 镜像:       ${PIP_INDEX_URL:-<默认>}"
log_info "  GOPROXY:        ${GOPROXY}"
log_info "========================================================================"
echo ""

# 构建上下文目录（使用 nodeskclaw-artifacts 目录）
CONTEXT_DIR="${SCRIPT_DIR}"

# 临时源码目录（复制到构建上下文中）
TEMP_SOURCE_DIR="${SCRIPT_DIR}/_temp_openclaw_source"

# 清理临时目录的函数
cleanup_temp_dir() {
  if [ -d "${TEMP_SOURCE_DIR}" ]; then
    rm -rf "${TEMP_SOURCE_DIR}"
    log_info "已清理临时源码目录: ${TEMP_SOURCE_DIR}"
  fi
}

# 设置 trap，确保脚本退出时清理（包括正常退出和错误）
trap cleanup_temp_dir EXIT INT TERM

log_info "准备源码..."
cleanup_temp_dir

# 使用 cp -a 复制源码（排除 node_modules 等大文件，加快复制）
log_info "复制源码到构建上下文..."
mkdir -p "${TEMP_SOURCE_DIR}"
cp -a "${SOURCE_PATH}/"* "${TEMP_SOURCE_DIR}/"
# 复制隐藏文件
cp -a "${SOURCE_PATH}/.[!.]*" "${TEMP_SOURCE_DIR}/" 2>/dev/null || true
# 删除不需要的大文件
rm -rf "${TEMP_SOURCE_DIR}/node_modules" "${TEMP_SOURCE_DIR}/.git" "${TEMP_SOURCE_DIR}/dist" 2>/dev/null || true
log_info "源码复制完成"

# 更新 package.json 版本号（确保镜像内版本与标签一致）
log_info "更新 package.json 版本号为: ${VERSION}"
if command -v jq &>/dev/null; then
  jq --arg v "${VERSION}" '.version = $v' "${TEMP_SOURCE_DIR}/package.json" > "${TEMP_SOURCE_DIR}/package.json.tmp" && \
    mv "${TEMP_SOURCE_DIR}/package.json.tmp" "${TEMP_SOURCE_DIR}/package.json"
else
  # 没有 jq 时使用 sed
  sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"${VERSION}\"/" "${TEMP_SOURCE_DIR}/package.json"
fi
log_info "package.json 版本已更新"

# ========== 执行构建 ==========
log_info "开始构建 Docker 镜像..."

DOCKERFILE_PATH="${SCRIPT_DIR}/openclaw-image/Dockerfile.full"

docker_build "${CONTEXT_DIR}" "${IMAGE_NAME}" \
  -f "${DOCKERFILE_PATH}" \
  --build-arg OPENCLAW_SOURCE_PATH="_temp_openclaw_source" \
  --build-arg IMAGE_VERSION="v${VERSION}" \
  --build-arg INSTALL_GO="${INSTALL_GO}" \
  --build-arg INSTALL_NPM_TOOLS="${INSTALL_NPM_TOOLS}" \
  --build-arg INSTALL_BROWSER="${INSTALL_BROWSER}" \
  --build-arg GO_VERSION="${GO_VERSION}" \
  --build-arg APT_MIRROR="${APT_MIRROR}" \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL}" \
  --build-arg GOPROXY="${GOPROXY}" \
  --build-arg APT_PACKAGES_CORE="${APT_PACKAGES_CORE}" \
  --build-arg APT_PACKAGES_DEV="${APT_PACKAGES_DEV}" \
  --build-arg APT_PACKAGES_BROWSER="${APT_PACKAGES_BROWSER}" \
  --build-arg APT_PACKAGES_PLAYWRIGHT="${APT_PACKAGES_PLAYWRIGHT}" \
  --build-arg APT_PACKAGES_FONTS="${APT_PACKAGES_FONTS}" \
  --build-arg APT_PACKAGES_MEDIA="${APT_PACKAGES_MEDIA}" \
  --build-arg APT_PACKAGES_DOCS="${APT_PACKAGES_DOCS}" \
  --build-arg APT_PACKAGES_NET="${APT_PACKAGES_NET}" \
  --build-arg APT_PACKAGES_ARCHIVE="${APT_PACKAGES_ARCHIVE}" \
  --build-arg APT_PACKAGES_TERMINAL="${APT_PACKAGES_TERMINAL}" \
  --build-arg APT_PACKAGES_SCHED="${APT_PACKAGES_SCHED}" \
  --build-arg APT_PACKAGES_SYS="${APT_PACKAGES_SYS}" \
  --build-arg APT_PACKAGES_X11="${APT_PACKAGES_X11}" \
  --build-arg APT_PACKAGES_OTHER="${APT_PACKAGES_OTHER}" \
  --build-arg APT_PACKAGES_EXTRA="${APT_PACKAGES_EXTRA}" \
  --build-arg PIP_PACKAGES_BASE="${PIP_PACKAGES_BASE}" \
  --build-arg PIP_PACKAGES_HTTP="${PIP_PACKAGES_HTTP}" \
  --build-arg PIP_PACKAGES_CONFIG="${PIP_PACKAGES_CONFIG}" \
  --build-arg PIP_PACKAGES_CLI="${PIP_PACKAGES_CLI}" \
  --build-arg PIP_PACKAGES_DOCS="${PIP_PACKAGES_DOCS}" \
  --build-arg PIP_PACKAGES_OFFICE="${PIP_PACKAGES_OFFICE}" \
  --build-arg PIP_PACKAGES_DATA="${PIP_PACKAGES_DATA}" \
  --build-arg PIP_PACKAGES_TEST="${PIP_PACKAGES_TEST}" \
  --build-arg PIP_PACKAGES_EXTRA="${PIP_PACKAGES_EXTRA}" \
  --build-arg NPM_GLOBAL_TOOLS="${NPM_GLOBAL_TOOLS}"

log_success "镜像构建完成: ${IMAGE_NAME}"

# 兼容无 v 前缀镜像 tag（例如部署侧使用 2026.5.5）
if [[ "${TAG_COMPAT_ALIAS}" == "true" ]]; then
  image_tag="${IMAGE_NAME##*:}"
  if [[ "${image_tag}" == "v${VERSION}" ]]; then
    alias_image="${IMAGE_NAME%:*}:${VERSION}"
    if [[ "${alias_image}" != "${IMAGE_NAME}" ]]; then
      docker tag "${IMAGE_NAME}" "${alias_image}"
      log_success "已创建兼容 tag: ${alias_image}"
    fi
  fi
fi

# ========== 验证镜像 ==========
if [[ "${SKIP_VERIFY}" != "true" ]]; then
  echo ""
  log_info "验证镜像内容..."

  echo ""
  log_info "Node.js 版本:"
  docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'node --version'

  echo ""
  log_info "OpenClaw 版本:"
  docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'openclaw --version' 2>&1 || log_warn "OpenClaw 验证跳过"

  echo ""
  log_info "Python 版本:"
  docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'python3 --version'

  if [[ "${INSTALL_GO}" == "true" ]]; then
    echo ""
    log_info "Go 版本:"
    docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'go version'
  fi

  echo ""
  log_info "已安装的 APT 包数量:"
  docker run --rm --platform linux/amd64 --entrypoint /bin/sh "${IMAGE_NAME}" -c 'dpkg -l | wc -l'
fi

# ========== 推送镜像 ==========
if [[ "${BUILD_ONLY}" == "true" ]]; then
  echo ""
  log_info "仅构建模式，跳过推送"
else
  echo ""
  log_info "推送镜像到仓库..."
  docker_push "${IMAGE_NAME}"
  log_success "镜像推送完成"
fi

# ========== 完成总结 ==========
echo ""
log_success "========================================================================"
log_success "  构建完成！"
log_success "========================================================================"
echo ""
echo "镜像信息:"
echo "  名称: ${IMAGE_NAME}"
echo "  版本: v${VERSION}"
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
echo "========================================================================"
