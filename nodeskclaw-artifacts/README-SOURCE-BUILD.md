# OpenClaw 源码构建完整指南
## 概述

DeskClaw 支持三种构建策略，你可以根据需要选择：

| 构建方式 | 脚本 | 特点 | 适用场景 |
|---------|------|------|---------|
| **官方 npm 版** | `build.sh` | 从 npm 安装官方发布版 | 生产环境，稳定可靠 |
| **源码简化版** | `build-source-simple.sh` | **先安装官方版再覆盖源码，保证可运行** | 快速验证、自定义修改 | ⭐ 推荐 |
| **源码基础版** | `build-source.sh` | 从源码编译，最小化安装 | 需要自定义源码修改 | |
| **源码完整功能版** | `build-full.sh` | 完整工具链 + 浏览器自动化 | 开发环境，功能需求多 | |
| **Git 自动构建** | `build-from-git.sh` | 自动克隆 Git 仓库并构建 | 自动构建流程 | |

---

## 🚀 快速开始

### 方式一：源码简化版（⭐ 最推荐）

**先安装官方 npm 版本（保证可运行），再用源码覆盖。** 100% 兼容，支持自定义修改：

```bash
cd nodeskclaw-artifacts

./build-source-simple.sh \
  --source-path ../openclaw \
  --version 2026.4.24-custom \
  --build-only
```

### 方式二：完整功能版

适合需要浏览器自动化、丰富工具链的场景：

```bash
cd nodeskclaw-artifacts

# 1. 编辑配置（可选）
vim build-full.env

# 2. 构建并推送
./build-full.sh \
  --source-path ../openclaw \
  --version 2026.4.24-custom
```

### 方式三：基础版（最小化）

只包含 OpenClaw 核心，无额外工具：

```bash
./build-source.sh \
  --source-path ../openclaw \
  --version 2026.3.1-custom
```

### 方式三：Git 自动克隆构建

自动从 Git 仓库克隆最新代码并构建：

```bash
./build-from-git.sh \
  --version 2026.3.1-custom \
  --clean
```

---

## 📋 完整功能版配置说明

### 功能开关

在 `build-full.env` 中可以配置：

```bash
# 安装 Go 环境（lark-cli 需要）
INSTALL_GO=true

# 安装 npm 全局工具（skillhub, clawhub, typescript 等）
INSTALL_NPM_TOOLS=true

# 安装浏览器自动化（Playwright + Chromium + VNC）
INSTALL_BROWSER=true
```

### 工具版本

```bash
GO_VERSION=1.24.9
NPM_VERSION=11.12.1
```

### APT 包分类自定义

```bash
# 核心系统工具
APT_PACKAGES_CORE="procps curl wget git ca-certificates..."

# 开发构建工具
APT_PACKAGES_DEV="build-essential python3-pip cmake..."

# 浏览器相关
APT_PACKAGES_BROWSER="chromium chromium-driver xvfb..."

# 文档处理（PDF, OCR, Office）
APT_PACKAGES_DOCS="poppler-utils tesseract-ocr libreoffice-calc..."

# 网络工具
APT_PACKAGES_NET="netcat-openbsd dnsutils iputils-ping socat..."

# 终端增强工具
APT_PACKAGES_TERMINAL="tmux vim htop jq ripgrep zsh fzf..."

# 额外自定义包
APT_PACKAGES_EXTRA=""
```

### Python 包分类自定义

```bash
PIP_PACKAGES_BASE="pip setuptools wheel"
PIP_PACKAGES_HTTP="requests httpx aiohttp"
PIP_PACKAGES_CONFIG="pydantic pyyaml python-dotenv"
PIP_PACKAGES_OFFICE="pdfplumber python-docx openpyxl..."
PIP_PACKAGES_DATA="pandas numpy tiktoken pillow..."

# 额外自定义 Python 包
PIP_PACKAGES_EXTRA=""
```

### npm 全局工具

```bash
NPM_GLOBAL_TOOLS="skillhub@latest clawhub@latest typescript@latest tsx@latest yarn@latest pnpm@latest..."
```

### 镜像源配置（国内加速）

```bash
# Debian APT 镜像源
APT_MIRROR=mirrors.aliyun.com

# Python PIP 镜像源
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Go 模块代理
GOPROXY=https://goproxy.cn,direct
```

---

## 🎛️ 命令行参数详解

### build-full.sh

```bash
./build-full.sh \
  --source-path ../openclaw \          # OpenClaw 源码路径
  --version 2026.3.1-custom \          # 镜像版本
  --image my-registry.com/openclaw:v1 \ # 自定义镜像名
  --build-only \                         # 仅构建不推送
  --skip-verify \                        # 跳过验证
  --no-go \                              # 不安装 Go
  --no-npm-tools \                       # 不安装 npm 全局工具
  --no-browser \                         # 不安装浏览器自动化
  --config my-config.env                 # 指定配置文件
```

### build-from-git.sh

```bash
./build-from-git.sh \
  --repo https://github.com/your-org/openclaw \  # Git 仓库地址
  --branch dev \                                   # Git 分支/标签
  --version 2026.3.1-dev \                        # 镜像版本
  --full \                                         # 完整功能版（默认）
  --base \                                         # 基础版
  --build-only \                                   # 仅构建不推送
  --clean \                                         # 构建后删除源码
  --clone-dir ./custom-src                         # 自定义克隆目录
```

---

## 📦 预置工具清单

### 完整功能版默认包含

#### 系统工具（APT）
- **开发工具**: `build-essential, pkg-config, cmake, python3-pip`
- **浏览器**: `chromium, chromium-driver, xvfb, x11vnc, novnc`
- **文档处理**: `poppler-utils, tesseract-ocr, libreoffice-calc`
- **网络**: `netcat-openbsd, dnsutils, iputils-ping, socat, tcpdump, nmap`
- **终端**: `tmux, vim, htop, jq, ripgrep, zsh, fzf`
- **数据库客户端**: `sqlite3, redis-tools, postgresql-client, default-mysql-client`

#### Python 包
- **HTTP**: `requests, httpx, aiohttp, urllib3`
- **配置**: `pydantic, pyyaml, python-dotenv`
- **CLI**: `rich, click, typer, tenacity, httpie`
- **数据**: `pandas, numpy, polars, tiktoken, pillow`
- **文档**: `beautifulsoup4, lxml, markdown, pdfplumber, python-docx`

#### npm 全局工具
- `skillhub@latest` (Skill 包管理器)
- `clawhub@latest` (Claw 插件市场)
- `typescript, tsx, yarn, pnpm, eslint, prettier`

#### Go 环境
- Go `1.24.9` (支持 lark-cli 等工具)

---

## 🔧 适配 NoDeskClaw

### 步骤 1: 构建并推送镜像

```bash
./build-full.sh \
  --source-path ../openclaw \
  --version 2026.3.1-custom
```

### 步骤 2: 添加引擎版本

1. 登录 NoDeskClaw 管理后台
2. 进入 **引擎版本** → **新增版本**
3. 填写：
   - **Runtime**: `openclaw`
   - **版本号**: `2026.3.1-custom`
   - **镜像 Tag**: `v2026.3.1-custom`
   - **状态**: `published`
4. 保存

### 步骤 3: 创建实例

创建新实例或升级现有实例时，选择你自定义的引擎版本即可。

---

## 🧪 镜像验证

构建完成后，可以快速验证镜像内容：

```bash
# 验证 Node.js
docker run --rm your-image node --version

# 验证 OpenClaw
docker run --rm your-image openclaw --version

# 验证 Python
docker run --rm your-image python3 --version

# 验证 Go（如果安装）
docker run --rm your-image go version

# 验证已安装包数量
docker run --rm your-image dpkg -l | wc -l

# 启动测试
docker run --rm -it -p 18789:18789 your-image
```

---

## 📂 文件结构

```
nodeskclaw-artifacts/
├── build.sh                      # 官方 npm 版构建
├── build-source.sh               # 源码基础版构建
├── build-full.sh                 # 源码完整功能版构建
├── build-from-git.sh             # Git 自动克隆构建
├── build-full.env                # 完整功能版配置文件
├── README-SOURCE-BUILD.md        # 本文档
├── common.sh                     # 公共函数
└── openclaw-image/
    ├── Dockerfile                # npm 版 Dockerfile
    ├── Dockerfile.source         # 源码基础版 Dockerfile
    ├── Dockerfile.full           # 源码完整功能版 Dockerfile
    ├── docker-entrypoint.sh      # 容器入口脚本
    ├── init-container.sh         # Init Container 脚本
    ├── openclaw.json.template    # 配置模板
    ├── repair-sessions-index.js  # 会话修复脚本
    └── repair-user-data.js       # 用户数据修复脚本
```

---

## 💡 最佳实践

### 生产环境
- 使用 `build-source.sh` 基础版，减少镜像体积和攻击面
- 只安装必要的包
- 使用固定的版本号，不使用 `latest`

### 开发/测试环境
- 使用 `build-full.sh` 完整功能版
- 开启浏览器自动化支持
- 安装丰富的调试工具

### CI/CD 集成
- 使用 `build-from-git.sh` 自动克隆并构建
- 配合 `--build-only` 在 CI 中做验证
- 测试通过后再推送到镜像仓库

### 自定义扩展
- 在 `build-full.env` 的 `*_EXTRA` 变量中添加你需要的包
- 或者继承我们的镜像，添加额外的 Dockerfile 层

---

## 🆘 常见问题

### Q: 构建时提示 npm install 失败
**A**: 检查网络连接，或配置 npm 镜像源。可以在 `build-full.env` 中设置：
```bash
NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
```

### Q: 构建速度很慢
**A**: 
- 确保 Docker BuildKit 已启用（`DOCKER_BUILDKIT=1`）
- 使用 `--build-only` 本地缓存构建
- 国内用户配置 `APT_MIRROR` 和 `PIP_INDEX_URL` 加速下载

### Q: 实例启动后 OpenClaw 访问不了
**A**: 
- 检查 `OPENCLAW_GATEWAY_BIND` 环境变量（应设为 `lan`）
- 检查端口映射是否正确（`18789`）
- 查看容器日志：`kubectl logs <pod-name>`

### Q: 自定义工具不生效
**A**: 确保在 `APT_PACKAGES_EXTRA` 或 `PIP_PACKAGES_EXTRA` 中添加，并且重新构建镜像。

---

## 📖 相关文档

- [DeskClaw 官方文档](https://docs.deskclaw.com)
- [OpenClaw 官方仓库](https://github.com/openclaw/openclaw)
