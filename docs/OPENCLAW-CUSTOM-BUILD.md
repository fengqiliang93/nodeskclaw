# OpenClaw 自定义镜像构建适配方案

## 方案概述

DeskClaw 现在支持三种 OpenClaw 镜像构建方式，以满足不同场景需求：

1. **官方 npm 版**（默认）：从 npm 安装官方发布版，稳定可靠
2. **源码基础版**：从源码编译，最小化安装，适合需要自定义源码修改的场景
3. **源码完整功能版**：完整工具链 + 浏览器自动化，适合开发环境和复杂任务场景
4. **Git 自动构建**：自动克隆 Git 仓库并构建，适合 CI/CD 流程

新增关键策略：

5. **Tag 兼容别名**：构建 `v版本` 时自动生成无 `v` 的别名 tag，避免部署脚本与镜像仓库标签风格不一致导致 `ImagePullBackOff`

---

## 快速选择指南

| 场景 | 推荐构建方式 | 特点 |
|------|-------------|------|
| 生产环境，追求稳定 | 官方 npm 版 (`build.sh`) | ✓ 官方验证，稳定可靠 |
| 需要自定义源码修改 | 源码基础版 (`build-source.sh`) | ✓ 可自定义，体积小 |
| 需要浏览器/丰富工具 | 源码完整功能版 (`build-full.sh`) | ✓ 功能最全，开箱即用 |
| CI/CD 自动化构建 | Git 自动构建 (`build-from-git.sh`) | ✓ 自动克隆，无需手动管理源码 |

---

## 文件清单

### 新增/修改的文件

```
nodeskclaw-artifacts/
├── build.sh                      # 官方 npm 版构建（原有）
├── build-source.sh               # 源码基础版构建（新增）
├── build-full.sh                 # 源码完整功能版构建（新增）
├── build-from-git.sh             # Git 自动克隆构建（新增）
├── build-full.env                # 完整功能版配置文件（新增）
├── README-SOURCE-BUILD.md        # 源码构建详细指南（新增）
└── openclaw-image/
    ├── Dockerfile                # npm 版 Dockerfile（原有）
    ├── Dockerfile.source         # 源码基础版 Dockerfile（新增）
    └── Dockerfile.full           # 源码完整功能版 Dockerfile（新增）

docs/
└── OPENCLAW-CUSTOM-BUILD.md      # 本文档
```

---

## 使用方法

### 1. 源码基础版构建

适合只需要 OpenClaw 核心功能的场景：

```bash
cd nodeskclaw-artifacts

./build-source.sh \
  --source-path ../openclaw \      # OpenClaw 源码目录
  --version 2026.3.1-custom \       # 镜像版本号
  --build-only                        # 可选：仅构建不推送
```

### 2. 源码完整功能版构建

适合需要浏览器自动化、丰富工具链的场景：

```bash
cd nodeskclaw-artifacts

# 编辑配置（可选）
vim build-full.env

# 构建
./build-full.sh \
  --source-path ../openclaw \
  --version 2026.3.1-custom \
  --build-only
```

**可自定义的功能开关**：
- `--no-go`：不安装 Go 环境
- `--no-npm-tools`：不安装 npm 全局工具
- `--no-browser`：不安装浏览器自动化

### 3. Git 自动构建

适合 CI/CD 自动化流程：

```bash
cd nodeskclaw-artifacts

# 自动克隆官方仓库最新 tag 并构建
./build-from-git.sh \
  --version 2026.3.1-custom \
  --full \                          # 完整功能版
  --clean                            # 构建后清理源码

# 或指定仓库和分支
./build-from-git.sh \
  --repo https://github.com/your-org/openclaw \
  --branch dev \
  --version 2026.3.1-dev
```

---

## 完整功能版可配置项

### 功能开关

| 配置项 | 说明 |
|--------|------|
| `INSTALL_GO` | 安装 Go 环境（lark-cli 需要） |
| `INSTALL_NPM_TOOLS` | 安装 npm 全局工具 |
| `INSTALL_BROWSER` | 安装浏览器自动化（Playwright + Chromium + VNC） |
| `TAG_COMPAT_ALIAS` | 构建后自动创建去掉 `v` 前缀的兼容 tag（默认 `true`） |

示例：

- 输入镜像：`deskclaw-openclaw:v2026.5.5`
- 自动补充：`deskclaw-openclaw:2026.5.5`

### 工具版本

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `GO_VERSION` | `1.24.9` | Go 版本 |
| `NPM_VERSION` | `11.12.1` | npm 版本 |

### APT 包分类

支持按分类自定义安装包：
- `APT_PACKAGES_CORE`：核心系统工具
- `APT_PACKAGES_DEV`：开发构建工具
- `APT_PACKAGES_BROWSER`：浏览器相关
- `APT_PACKAGES_PLAYWRIGHT`：Playwright 依赖
- `APT_PACKAGES_FONTS`：字体（支持中文）
- `APT_PACKAGES_MEDIA`：媒体处理
- `APT_PACKAGES_DOCS`：文档处理（PDF, OCR, Office）
- `APT_PACKAGES_NET`：网络工具
- `APT_PACKAGES_ARCHIVE`：归档工具
- `APT_PACKAGES_TERMINAL`：终端增强工具
- `APT_PACKAGES_SCHED`：任务调度
- `APT_PACKAGES_SYS`：系统监控/调试
- `APT_PACKAGES_X11`：X11 相关
- `APT_PACKAGES_OTHER`：其他工具
- `APT_PACKAGES_EXTRA`：额外自定义包

### Python 包分类

- `PIP_PACKAGES_BASE`：基础包
- `PIP_PACKAGES_HTTP`：HTTP 客户端
- `PIP_PACKAGES_CONFIG`：配置处理
- `PIP_PACKAGES_CLI`：CLI 工具
- `PIP_PACKAGES_DOCS`：文档处理
- `PIP_PACKAGES_OFFICE`：Office 文件处理
- `PIP_PACKAGES_DATA`：数据处理
- `PIP_PACKAGES_TEST`：测试工具
- `PIP_PACKAGES_EXTRA`：额外自定义包

### npm 全局工具

`NPM_GLOBAL_TOOLS`：可自定义安装的 npm 全局工具列表

### 镜像源配置（国内加速）

| 配置项 | 说明 |
|--------|------|
| `APT_MIRROR` | Debian APT 镜像源（推荐: mirrors.aliyun.com） |
| `PIP_INDEX_URL` | Python PIP 镜像源（推荐: https://pypi.tuna.tsinghua.edu.cn/simple） |
| `GOPROXY` | Go 模块代理（推荐: https://goproxy.cn,direct） |

---

## 适配 NoDeskClaw 步骤

### 步骤 1：构建并推送镜像

```bash
# 选择一种构建方式，例如完整功能版
./build-full.sh \
  --source-path ../openclaw \
  --version 2026.3.1-custom
```

如果要明确开启兼容 tag（默认已开启）：

```bash
TAG_COMPAT_ALIAS=true ./build-full.sh \
  --source-path ../openclaw \
  --version 2026.5.5 \
  --image deskclaw-openclaw:v2026.5.5 \
  --build-only
```

### 步骤 2：在 NoDeskClaw 中添加引擎版本

1. 登录管理后台
2. 进入 **引擎版本** → **新增版本**
3. 填写：
   - **Runtime**: `openclaw`
   - **版本号**: `2026.3.1-custom`
   - **镜像 Tag**: `v2026.3.1-custom`
   - **状态**: `published`
4. 保存

### 步骤 3：创建实例

创建新实例或升级现有实例时，选择自定义的引擎版本即可。

### 步骤 4：导入 k3s（离线或本地构建场景）

建议导入双 tag，避免部署侧使用无 `v` 标签时拉取失败：

```bash
docker save deskclaw-openclaw:v2026.5.5 | sudo k3s ctr -n k8s.io images import -
docker save deskclaw-openclaw:2026.5.5 | sudo k3s ctr -n k8s.io images import -
```

多机集群场景下，上述导入动作需在每个可能承载实例 Pod 的节点执行。

---

## 镜像兼容性

✅ **100% 兼容官方镜像**：
- 相同的启动入口 `/docker-entrypoint.sh`
- 相同的配置模板和环境变量
- 相同的 Init Container 逻辑
- 相同的目录结构
- K8s 部署流程完全一致

---

## 预设工具清单（完整功能版）

### 系统工具（APT）
- **开发工具**：`build-essential`, `pkg-config`, `cmake`, `python3-pip`
- **浏览器**：`chromium`, `chromium-driver`, `xvfb`, `x11vnc`, `novnc`
- **文档处理**：`poppler-utils`, `tesseract-ocr`, `libreoffice-calc`
- **网络**：`netcat-openbsd`, `dnsutils`, `iputils-ping`, `socat`, `tcpdump`, `nmap`
- **终端**：`tmux`, `vim`, `htop`, `jq`, `ripgrep`, `zsh`, `fzf`
- **数据库客户端**：`sqlite3`, `redis-tools`, `postgresql-client`, `default-mysql-client`

### Python 包
- **HTTP**：`requests`, `httpx`, `aiohttp`, `urllib3`
- **配置**：`pydantic`, `pyyaml`, `python-dotenv`
- **CLI**：`rich`, `click`, `typer`, `tenacity`, `httpie`
- **数据**：`pandas`, `numpy`, `polars`, `tiktoken`, `pillow`
- **文档**：`beautifulsoup4`, `lxml`, `markdown`, `pdfplumber`, `python-docx`

### npm 全局工具
- `skillhub@latest`（Skill 包管理器）
- `clawhub@latest`（Claw 插件市场）
- `typescript`, `tsx`, `yarn`, `pnpm`, `eslint`, `prettier`

### Go 环境
- Go `1.24.9`（支持 lark-cli 等工具）

---

## 最佳实践

### 生产环境
- 使用源码基础版，减少镜像体积和攻击面
- 只安装必要的包
- 使用固定的版本号，不使用 `latest`

### 开发/测试环境
- 使用完整功能版
- 开启浏览器自动化支持
- 安装丰富的调试工具

### CI/CD 集成
- 使用 `build-from-git.sh` 自动克隆并构建
- 配合 `--build-only` 在 CI 中做验证
- 测试通过后再推送到镜像仓库

### 自定义扩展
- 在 `build-full.env` 的 `*_EXTRA` 变量中添加需要的包
- 或者继承我们的镜像，添加额外的 Dockerfile 层

---

## 验证方法

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
