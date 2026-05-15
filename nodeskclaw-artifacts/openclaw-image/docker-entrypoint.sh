#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# OpenClaw 容器启动脚本
#
# 职责:
#   1. 配置初始化 - 从模板生成 openclaw.json（首次 / 强制重建）
#   2. 凭证注入   - 将环境变量中的凭证写入文件
#   3. 缓存清理   - 清理 jiti 编译缓存
#   4. 前台启动   - exec 让 Node.js 成为 PID 1，接收 K8s SIGTERM
#
# 注意: 不依赖 apt 包，用 node 替代 envsubst
# =============================================================================

OPENCLAW_DIR="/root/.openclaw"
CONFIG_FILE="${OPENCLAW_DIR}/openclaw.json"
TEMPLATE_FILE="/opt/openclaw/openclaw.json.template"
TEMPLATE_FILE_FALLBACK="${OPENCLAW_DIR}/openclaw.json.template"
CREDENTIALS_DIR="${OPENCLAW_DIR}/credentials"
PERSISTENT_CONFIG_SNAPSHOT="${OPENCLAW_DIR}/persistent-config.snapshot.json"
PERSISTENT_CONFIG_SNAPSHOT_LEGACY="${OPENCLAW_DIR}/.openclaw/persistent-config.snapshot.json"

# ---- 0. 清理旧数据（PVC 版本不兼容） ----

# 清理 PVC 中旧版本的 extensions，因为它们与新 OpenClaw 版本不兼容。
# 但需保留 NoDeskClaw 自己动态下发的 channel 插件目录，否则 clone/restore
# 后重启会把 openclaw-channel-nodeskclaw 直接删掉，导致 gateway 首启失败。
RUNTIME_EXTENSIONS_DIR="${OPENCLAW_DIR}/extensions"
if [ -d "${RUNTIME_EXTENSIONS_DIR}" ]; then
  echo "[entrypoint] 清理 PVC 中的旧 extensions（保留托管 channel 插件）: ${RUNTIME_EXTENSIONS_DIR}"
  find "${RUNTIME_EXTENSIONS_DIR}" -mindepth 1 -maxdepth 1 \
    ! -name "openclaw-channel-nodeskclaw" \
    ! -name "openclaw-channel-learning" \
    -exec rm -rf {} +
fi

# 剪掉 dist-runtime 中未完整构建的半成品扩展。
# 这些目录只剩 manifest/package.json，缺失 index.js/setup-entry.js，
# 一旦 OpenClaw 因 channel 配置触发扩展扫描，就会直接校验失败。
DIST_RUNTIME_EXTENSIONS_DIR="/opt/openclaw/dist-runtime/extensions"
if [ -d "${DIST_RUNTIME_EXTENSIONS_DIR}" ]; then
  DIST_EXT_DIR="${DIST_RUNTIME_EXTENSIONS_DIR}" node -e "
    const fs = require('fs');
    const path = require('path');
    const root = process.env.DIST_EXT_DIR;
    for (const name of fs.readdirSync(root)) {
      const dir = path.join(root, name);
      if (!fs.statSync(dir).isDirectory()) continue;
      const pkgPath = path.join(dir, 'package.json');
      if (!fs.existsSync(pkgPath)) continue;
      try {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
        const oc = pkg.openclaw ?? {};
        const expected = [];
        if (Array.isArray(oc.extensions)) expected.push(...oc.extensions);
        if (typeof oc.setupEntry === 'string') expected.push(oc.setupEntry);
        const missing = expected.filter((rel) => {
          if (typeof rel !== 'string' || !rel.startsWith('./')) return false;
          return !fs.existsSync(path.join(dir, rel.slice(2)));
        });
        if (missing.length > 0) {
          fs.rmSync(dir, { recursive: true, force: true });
          console.log('[entrypoint] 已裁剪半成品扩展: ' + name + ' missing=' + missing.join(','));
        }
      } catch (error) {
        fs.rmSync(dir, { recursive: true, force: true });
        console.log('[entrypoint] 已移除损坏扩展: ' + name + ' error=' + error.message);
      }
    }
  "
fi

# 清理配置中的过期 plugin/channel 残留。
# OpenClaw v2026.5.5 对 plugins 校验更严格，旧 PVC 上的 plugins.load.paths
# 和 channels.nodeskclaw 容易导致启动时 Config validation failed。
RUNTIME_CONFIG="${OPENCLAW_DIR}/.openclaw/openclaw.json"
for CFG in "${CONFIG_FILE}" "${RUNTIME_CONFIG}"; do
  if [ -f "${CFG}" ]; then
    echo "[entrypoint] 清理配置残留: ${CFG}"
    CFG_PATH="${CFG}" node -e "
      const fs = require('fs');
      const f = process.env.CFG_PATH;
      let text = fs.readFileSync(f, 'utf8');
      text = text.replace(/^\s*\/\/.*$/gm, '');
      const c = JSON.parse(text);
      let changed = false;

      // 彻底删除 plugins，避免旧 paths / entries 触发启动校验失败。
      if (c.plugins) {
        delete c.plugins;
        changed = true;
      }

      // 清理旧隧道配置，避免扩展缺失时的无效 channel 引用。
      if (c.channels?.nodeskclaw) {
        delete c.channels.nodeskclaw;
        if (Object.keys(c.channels).length === 0) delete c.channels;
        changed = true;
      }

      if (changed) {
        fs.writeFileSync(f, JSON.stringify(c, null, 2));
        console.log('[entrypoint] 已清理 plugins/channels 残留: ' + f);
      }
    "
  fi
done


# ---- 1. 配置初始化 ----

# 用 node 实现 envsubst（替换模板中的 ${VAR} 占位符）
envsubst_node() {
  node -e "
    const fs = require('fs');
    let t = fs.readFileSync('$1', 'utf8');
    t = t.replace(/\\\$\{([^}]+)\}/g, (_, k) => process.env[k] ?? '');
    fs.writeFileSync('$2', t);
  "
}

# 设置默认值
export OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
export OPENCLAW_GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-lan}"
export OPENCLAW_LOG_LEVEL="${OPENCLAW_LOG_LEVEL:-info}"

# 未指定 Token 时自动生成一个随机 Token
if [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]; then
  OPENCLAW_GATEWAY_TOKEN=$(node -e "console.log(require('crypto').randomBytes(24).toString('hex'))")
  export OPENCLAW_GATEWAY_TOKEN
  echo "[entrypoint] =================================================="
  echo "[entrypoint] 未指定 OPENCLAW_GATEWAY_TOKEN，已自动生成"
  echo "[entrypoint] Token: ${OPENCLAW_GATEWAY_TOKEN}"
  echo "[entrypoint]"
  echo "[entrypoint] 打开控制台: http://localhost:${OPENCLAW_GATEWAY_PORT}/?token=${OPENCLAW_GATEWAY_TOKEN}"
  echo "[entrypoint]"
  echo "[entrypoint] 如需固定 Token，启动时加 -e OPENCLAW_GATEWAY_TOKEN=<你的Token>"
  echo "[entrypoint] =================================================="
fi

if [ "${OPENCLAW_FORCE_RECONFIG:-false}" = "true" ]; then
  echo "[entrypoint] OPENCLAW_FORCE_RECONFIG=true，从模板重新生成配置..."
  if [ -f "${TEMPLATE_FILE}" ]; then
    envsubst_node "${TEMPLATE_FILE}" "${CONFIG_FILE}"
    echo "[entrypoint] 配置已重新生成: ${CONFIG_FILE}"
  elif [ -f "${TEMPLATE_FILE_FALLBACK}" ]; then
    envsubst_node "${TEMPLATE_FILE_FALLBACK}" "${CONFIG_FILE}"
    echo "[entrypoint] 配置已重新生成: ${CONFIG_FILE}"
  else
    echo "[entrypoint] 警告: 模板文件不存在，跳过配置生成"
  fi
elif [ ! -f "${CONFIG_FILE}" ]; then
  echo "[entrypoint] 首次启动，从模板生成配置..."
  if [ -f "${TEMPLATE_FILE}" ]; then
    envsubst_node "${TEMPLATE_FILE}" "${CONFIG_FILE}"
    echo "[entrypoint] 配置已生成: ${CONFIG_FILE}"
  elif [ -f "${TEMPLATE_FILE_FALLBACK}" ]; then
    envsubst_node "${TEMPLATE_FILE_FALLBACK}" "${CONFIG_FILE}"
    echo "[entrypoint] 配置已生成: ${CONFIG_FILE}"
  else
    echo "[entrypoint] 警告: 模板文件不存在，将以无配置模式启动"
  fi
else
  echo "[entrypoint] 配置文件已存在，跳过生成"
fi

# ---- 1.1. 配置补全（兼容旧版 PVC 上的配置） ----

if [ -f "${CONFIG_FILE}" ]; then
  node -e "
    const fs = require('fs');
    const f = '${CONFIG_FILE}';
    let text = fs.readFileSync(f, 'utf8');
    text = text.replace(/^\s*\/\/.*$/gm, '');
    const c = JSON.parse(text);
    let changed = false;
    if (!c.gateway) c.gateway = {};
    if (!c.gateway.controlUi) c.gateway.controlUi = {};
    if (!c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback) {
      c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
      changed = true;
    }
    if (c.gateway?.controlUi && !c.gateway.controlUi.dangerouslyDisableDeviceAuth) {
      c.gateway.controlUi.dangerouslyDisableDeviceAuth = true;
      changed = true;
    }
    // 确保 allowedOrigins 包含 '*' 以支持局域网访问
    if (!c.gateway?.controlUi?.allowedOrigins?.includes('*')) {
      if (!c.gateway) c.gateway = {};
      if (!c.gateway.controlUi) c.gateway.controlUi = {};
      if (!Array.isArray(c.gateway.controlUi.allowedOrigins)) c.gateway.controlUi.allowedOrigins = [];
      c.gateway.controlUi.allowedOrigins.unshift('*');
      changed = true;
    }
    const skills = c.skills ?? (c.skills = {});
    const load = skills.load ?? (skills.load = {});
    const extraDirs = Array.isArray(load.extraDirs) ? load.extraDirs : [];
    if (!extraDirs.includes('/root/.openclaw/skills')) {
      extraDirs.push('/root/.openclaw/skills');
      load.extraDirs = extraDirs;
      changed = true;
    }
    const tools = c.tools ?? (c.tools = {});
    const allow = Array.isArray(tools.allow) ? tools.allow.filter(Boolean) : [];
    if (allow.includes('*')) {
      if (allow.length !== 1 || allow[0] !== '*') {
        tools.allow = ['*'];
        changed = true;
      }
    } else if (allow.length === 0 || (allow.length === 1 && allow[0] === 'exec')) {
      tools.allow = ['*'];
      changed = true;
    } else if (allow.length > 0) {
      tools.allow = allow;
    }
    const exec = tools.exec ?? (tools.exec = {});
    if (!exec.security) { exec.security = 'full'; changed = true; }
    if (!exec.ask) { exec.ask = 'off'; changed = true; }
    const browser = c.browser ?? (c.browser = {});
    if (browser.noSandbox !== true) {
      browser.noSandbox = true;
      changed = true;
    }

    if (c.channels?.feishu && typeof c.channels.feishu === 'object') {
      const feishu = c.channels.feishu;
      if (typeof feishu.streaming !== 'boolean') {
        feishu.streaming = true;
        changed = true;
      }
      if (typeof feishu.blockStreaming !== 'boolean') {
        feishu.blockStreaming = false;
        changed = true;
      }
      const defaultAccount = typeof feishu.defaultAccount === 'string' && feishu.defaultAccount ? feishu.defaultAccount : 'default';
      const account = feishu.accounts?.[defaultAccount];
      if (account && typeof account === 'object') {
        if (typeof account.streaming !== 'boolean') {
          account.streaming = feishu.streaming;
          changed = true;
        }
        if (typeof account.blockStreaming !== 'boolean') {
          account.blockStreaming = feishu.blockStreaming;
          changed = true;
        }
      }
    }

    // 注入 NoDeskClaw 隧道通道配置（如果环境变量已设置）
    const NODESKCLAW_INSTANCE_ID = process.env.NODESKCLAW_INSTANCE_ID;
    const NODESKCLAW_API_URL = process.env.NODESKCLAW_API_URL;
    const NODESKCLAW_TOKEN = process.env.NODESKCLAW_TOKEN;
    const NODESKCLAW_TUNNEL_URL = process.env.NODESKCLAW_TUNNEL_URL;

    // 仅在 nodeskclaw 扩展存在时注入 channel 配置。
    // 某些构建变体可能未包含该扩展，强行注入会导致配置校验失败。
    const hasNodeskclawExtension = fs.existsSync('/opt/openclaw/dist-runtime/extensions/nodeskclaw');

    if (NODESKCLAW_INSTANCE_ID && NODESKCLAW_API_URL && NODESKCLAW_TOKEN && hasNodeskclawExtension) {
      const channels = c.channels ?? (c.channels = {});
      const nodeskclaw = channels.nodeskclaw ?? (channels.nodeskclaw = {});
      const accounts = nodeskclaw.accounts ?? (nodeskclaw.accounts = {});
      const defaultAccount = accounts.default ?? (accounts.default = {});

      let accountChanged = false;
      if (defaultAccount.instanceId !== NODESKCLAW_INSTANCE_ID) {
        defaultAccount.instanceId = NODESKCLAW_INSTANCE_ID;
        accountChanged = true;
      }
      if (defaultAccount.apiUrl !== NODESKCLAW_API_URL) {
        defaultAccount.apiUrl = NODESKCLAW_API_URL;
        accountChanged = true;
      }
      if (defaultAccount.apiToken !== NODESKCLAW_TOKEN) {
        defaultAccount.apiToken = NODESKCLAW_TOKEN;
        accountChanged = true;
      }
      if (NODESKCLAW_TUNNEL_URL && nodeskclaw.tunnelUrl !== NODESKCLAW_TUNNEL_URL) {
        nodeskclaw.tunnelUrl = NODESKCLAW_TUNNEL_URL;
        accountChanged = true;
      }

      if (accountChanged) {
        changed = true;
        console.log('[entrypoint] 已注入 NoDeskClaw 隧道配置');
      }
    } else {
      // 环境未启用或扩展缺失时，清理历史残留配置，避免旧 PVC 配置触发隧道重连循环。
      if (c.channels?.nodeskclaw) {
        delete c.channels.nodeskclaw;
        if (Object.keys(c.channels).length === 0) {
          delete c.channels;
        }
        changed = true;
        console.log('[entrypoint] 已清理陈旧的 NoDeskClaw 通道配置');
      }
    }

    if (changed) {
      fs.writeFileSync(f, JSON.stringify(c, null, 2));
      console.log('[entrypoint] 已更新 controlUi / skills / exec / channel 配置');
    }
  "
fi

# ---- 1.1.2. 生成后再次清理配置残留（模板可能重新注入 plugins） ----

for CFG in "${CONFIG_FILE}" "${RUNTIME_CONFIG}"; do
  if [ -f "${CFG}" ]; then
    CFG_PATH="${CFG}" node -e "
      const fs = require('fs');
      const f = process.env.CFG_PATH;
      let text = fs.readFileSync(f, 'utf8');
      text = text.replace(/^\s*\/\/.*$/gm, '');
      const c = JSON.parse(text);
      let changed = false;

      if (c.plugins) {
        delete c.plugins;
        changed = true;
      }
      if (c.channels?.nodeskclaw) {
        delete c.channels.nodeskclaw;
        if (Object.keys(c.channels).length === 0) delete c.channels;
        changed = true;
      }

      if (changed) {
        fs.writeFileSync(f, JSON.stringify(c, null, 2));
        console.log('[entrypoint] 生成后清理 plugins/channels: ' + f);
      }
    "
  fi
done

# ---- 1.1.3. 记录持久配置快照 ----

if [ -f "${CONFIG_FILE}" ]; then
  mkdir -p "${OPENCLAW_DIR}/.openclaw"
  CFG_PATH="${CONFIG_FILE}" SNAPSHOT_PATH="${PERSISTENT_CONFIG_SNAPSHOT}" node -e "
    const fs = require('fs');
    const cfgPath = process.env.CFG_PATH;
    const snapshotPath = process.env.SNAPSHOT_PATH;
    let text = fs.readFileSync(cfgPath, 'utf8');
    text = text.replace(/^\s*\/\/.*$/gm, '');
    const c = JSON.parse(text);
    let snapshot = {};
    if (fs.existsSync(snapshotPath)) {
      try {
        snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
      } catch (error) {
        snapshot = {};
      }
    }
    if (c.models && typeof c.models === 'object') {
      snapshot.models = c.models;
    }
    if (c.gateway?.http && typeof c.gateway.http === 'object') {
      snapshot.gateway = Object.assign({}, snapshot.gateway || {}, { http: c.gateway.http });
    }
    if (c.channels && typeof c.channels === 'object') {
      const channels = JSON.parse(JSON.stringify(c.channels));
      delete channels.nodeskclaw;
      if (Object.keys(channels).length > 0) {
        snapshot.channels = channels;
      }
    }
    if (c.agents?.defaults?.model) {
      snapshot.agents = {
        defaults: {
          model: c.agents.defaults.model,
        },
      };
    }
    if (Object.keys(snapshot).length > 0) {
      fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2));
      console.log('[entrypoint] 已记录持久配置快照: ' + snapshotPath);
    }
  "
fi

# ---- 1.1.3. 启动前配置体检与自动修复 ----

if command -v openclaw >/dev/null 2>&1; then
  # 新版本 OpenClaw 对配置校验更严格（插件条目、channel id 等）。
  # 这里进行一次无交互修复，避免因为历史配置差异导致启动失败。
  openclaw doctor --fix >/tmp/openclaw-doctor.log 2>&1 || true
  if [ -s /tmp/openclaw-doctor.log ]; then
    echo "[entrypoint] openclaw doctor --fix 输出:"
    cat /tmp/openclaw-doctor.log
  fi

  # doctor --fix 可能重新写回 plugins/channels 配置，启动前再做一次兜底清理。
  for CFG in "${CONFIG_FILE}" "${RUNTIME_CONFIG}"; do
    if [ -f "${CFG}" ]; then
      CFG_PATH="${CFG}" node -e "
        const fs = require('fs');
        const f = process.env.CFG_PATH;
        let text = fs.readFileSync(f, 'utf8');
        text = text.replace(/^\s*\/\/.*$/gm, '');
        const c = JSON.parse(text);
        let changed = false;

        if (c.plugins) {
          delete c.plugins;
          changed = true;
        }
        if (c.channels?.nodeskclaw) {
          delete c.channels.nodeskclaw;
          if (Object.keys(c.channels).length === 0) delete c.channels;
          changed = true;
        }

        if (changed) {
          fs.writeFileSync(f, JSON.stringify(c, null, 2));
          console.log('[entrypoint] doctor 后再次清理 plugins/channels: ' + f);
        }
      "
    fi
  done
fi

# ---- 1.1.4. 恢复持久配置 ----

SNAPSHOT_SOURCE=""
if [ -f "${PERSISTENT_CONFIG_SNAPSHOT}" ]; then
  SNAPSHOT_SOURCE="${PERSISTENT_CONFIG_SNAPSHOT}"
elif [ -f "${PERSISTENT_CONFIG_SNAPSHOT_LEGACY}" ]; then
  SNAPSHOT_SOURCE="${PERSISTENT_CONFIG_SNAPSHOT_LEGACY}"
fi

if [ -f "${CONFIG_FILE}" ] && [ -n "${SNAPSHOT_SOURCE}" ]; then
  CFG_PATH="${CONFIG_FILE}" SNAPSHOT_PATH="${SNAPSHOT_SOURCE}" node -e "
    const fs = require('fs');
    const cfgPath = process.env.CFG_PATH;
    const snapshotPath = process.env.SNAPSHOT_PATH;
    const snapshot = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
    const current = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    const merged = { ...current, ...snapshot };
    if (current.gateway || snapshot.gateway) {
      merged.gateway = { ...(current.gateway || {}), ...(snapshot.gateway || {}) };
      if ((current.gateway && current.gateway.http) || (snapshot.gateway && snapshot.gateway.http)) {
        merged.gateway.http = {
          ...((current.gateway && current.gateway.http) || {}),
          ...((snapshot.gateway && snapshot.gateway.http) || {}),
        };
      }
    }
    fs.writeFileSync(cfgPath, JSON.stringify(merged, null, 2));
    console.log('[entrypoint] 已恢复持久配置: ' + cfgPath);
  "
fi

if [ -f "${CONFIG_FILE}" ]; then
  CFG_PATH="${CONFIG_FILE}" node -e "
    const fs = require('fs');
    const cfgPath = process.env.CFG_PATH;
    const config = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    const pluginPaths = {
      nodeskclaw: '/root/.openclaw/extensions/openclaw-channel-nodeskclaw',
      learning: '/root/.openclaw/extensions/openclaw-channel-learning',
    };
    let changed = false;
    const channels = config.channels || {};
    for (const [channelId, pluginPath] of Object.entries(pluginPaths)) {
      if (!channels[channelId]) continue;
      const plugins = config.plugins ?? (config.plugins = {});
      const load = plugins.load ?? (plugins.load = {});
      const paths = Array.isArray(load.paths) ? load.paths : (load.paths = []);
      if (!paths.includes(pluginPath)) {
        paths.push(pluginPath);
        changed = true;
      }
      const entries = plugins.entries ?? (plugins.entries = {});
      if (!entries[channelId]) {
        entries[channelId] = { enabled: true };
        changed = true;
      }
    }
    if (changed) {
      fs.writeFileSync(cfgPath, JSON.stringify(config, null, 2));
      console.log('[entrypoint] 已恢复 channel plugin wiring: ' + cfgPath);
    }
  "
fi

# ---- 1.1.1. 运行时配置合并（PVC 持久化配置） ----

RUNTIME_CONFIG="${OPENCLAW_DIR}/.openclaw/openclaw.json"
if [ -f "${RUNTIME_CONFIG}" ]; then
  node -e "
    const fs = require('fs');
    const f = '${RUNTIME_CONFIG}';
    let text = fs.readFileSync(f, 'utf8');
    text = text.replace(/^\s*\/\/.*$/gm, '');
    const c = JSON.parse(text);
    let changed = false;

    // 确保 allowedOrigins 包含 '*' 以支持局域网访问
    if (!c.gateway?.controlUi?.allowedOrigins?.includes('*')) {
      if (!c.gateway) c.gateway = {};
      if (!c.gateway.controlUi) c.gateway.controlUi = {};
      if (!Array.isArray(c.gateway.controlUi.allowedOrigins)) c.gateway.controlUi.allowedOrigins = [];
      c.gateway.controlUi.allowedOrigins.unshift('*');
      changed = true;
      console.log('[entrypoint] 已注入 allowedOrigins: [\"*\"] 到运行时配置');
    }

    // 启用 Host-header origin fallback（OpenClaw 新版对非 loopback 严格校验）
    if (!c.gateway?.controlUi?.dangerouslyAllowHostHeaderOriginFallback) {
      if (!c.gateway) c.gateway = {};
      if (!c.gateway.controlUi) c.gateway.controlUi = {};
      c.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = true;
      changed = true;
      console.log('[entrypoint] 已注入 dangerouslyAllowHostHeaderOriginFallback: true 到运行时配置');
    }

    // 禁用设备身份验证（HTTP 非安全上下文需要）
    if (!c.gateway?.controlUi?.dangerouslyDisableDeviceAuth) {
      if (!c.gateway) c.gateway = {};
      if (!c.gateway.controlUi) c.gateway.controlUi = {};
      c.gateway.controlUi.dangerouslyDisableDeviceAuth = true;
      changed = true;
      console.log('[entrypoint] 已注入 dangerouslyDisableDeviceAuth: true 到运行时配置');
    }

    if (!c.gateway?.http?.endpoints?.chatCompletions?.enabled) {
      if (!c.gateway) c.gateway = {};
      if (!c.gateway.http) c.gateway.http = {};
      if (!c.gateway.http.endpoints) c.gateway.http.endpoints = {};
      c.gateway.http.endpoints.chatCompletions = { enabled: true };
      changed = true;
      console.log('[entrypoint] 已注入 gateway.http.endpoints.chatCompletions.enabled=true 到运行时配置');
    }

    const tools = c.tools ?? (c.tools = {});
    const allow = Array.isArray(tools.allow) ? tools.allow.filter(Boolean) : [];
    if (allow.includes('*')) {
      if (allow.length !== 1 || allow[0] !== '*') {
        tools.allow = ['*'];
        changed = true;
        console.log('[entrypoint] 已规范 tools.allow=[\"*\"] 到运行时配置');
      }
    } else if (allow.length === 0 || (allow.length === 1 && allow[0] === 'exec')) {
      tools.allow = ['*'];
      changed = true;
      console.log('[entrypoint] 已注入 tools.allow=[\"*\"] 到运行时配置');
    } else if (allow.length > 0) {
      tools.allow = allow;
    }
    const exec = tools.exec ?? (tools.exec = {});
    if (!exec.security) {
      exec.security = 'full';
      changed = true;
    }
    if (!exec.ask) {
      exec.ask = 'off';
      changed = true;
    }

    if (c.channels?.feishu && typeof c.channels.feishu === 'object') {
      const feishu = c.channels.feishu;
      if (typeof feishu.streaming !== 'boolean') {
        feishu.streaming = true;
        changed = true;
      }
      if (typeof feishu.blockStreaming !== 'boolean') {
        feishu.blockStreaming = false;
        changed = true;
      }
      const defaultAccount = typeof feishu.defaultAccount === 'string' && feishu.defaultAccount ? feishu.defaultAccount : 'default';
      const account = feishu.accounts?.[defaultAccount];
      if (account && typeof account === 'object') {
        if (typeof account.streaming !== 'boolean') {
          account.streaming = feishu.streaming;
          changed = true;
        }
        if (typeof account.blockStreaming !== 'boolean') {
          account.blockStreaming = feishu.blockStreaming;
          changed = true;
        }
      }
    }

    // 检查 NoDeskClaw 隧道配置环境变量。
    // 若未设置则清理历史残留的 channels.nodeskclaw，避免旧 PVC 配置导致隧道重连失败。
    const NODESKCLAW_INSTANCE_ID = process.env.NODESKCLAW_INSTANCE_ID;
    const NODESKCLAW_API_URL = process.env.NODESKCLAW_API_URL;
    if (!NODESKCLAW_INSTANCE_ID || !NODESKCLAW_API_URL) {
      if (c.channels?.nodeskclaw) {
        delete c.channels.nodeskclaw;
        if (Object.keys(c.channels).length === 0) {
          delete c.channels;
        }
        changed = true;
        console.log('[entrypoint] 已清理运行时配置中的陈旧 NoDeskClaw 通道配置');
      }
    }

    if (changed) {
      fs.writeFileSync(f, JSON.stringify(c, null, 2));
    }
  "
fi

# ---- 1.2. 升级数据修复（兼容旧版目录/文件命名） ----

node /repair-user-data.js

# ---- 1.3. 会话索引修复（兼容旧版会话文件命名） ----

if [ -d "${OPENCLAW_DIR}/agents/main/sessions" ]; then
  node /repair-sessions-index.js
fi

# ---- 2. 凭证注入 ----

if [ -n "${OPENCLAW_CREDENTIALS_JSON:-}" ]; then
  mkdir -p -m 700 "${CREDENTIALS_DIR}"
  echo "${OPENCLAW_CREDENTIALS_JSON}" > "${CREDENTIALS_DIR}/default.json"
  echo "[entrypoint] 凭证已写入: ${CREDENTIALS_DIR}/default.json"
fi

# ---- 2.1. 修复 models.json 中的 api 类型 ----
# OpenClaw 生成的 models.json 可能使用 "openai" 作为 api 类型，
# 但有效值应该是 "openai-completions"。这里修复已生成的 models.json。

MODELS_JSON="${OPENCLAW_DIR}/.openclaw/agents/main/agent/models.json"
if [ -f "${MODELS_JSON}" ]; then
  node -e "
    const fs = require('fs');
    const f = '${MODELS_JSON}';
    let text = fs.readFileSync(f, 'utf8');
    // 修复: \"api\": \"openai\" -> \"api\": \"openai-completions\"
    const fixed = text.replace(/\"api\":\\s*\"openai\"/g, '\"api\": \"openai-completions\"');
    if (fixed !== text) {
      fs.writeFileSync(f, fixed);
      console.log('[entrypoint] 已修复 models.json 中的 api 类型: openai -> openai-completions');
    }
  "
fi

# ---- 3. 清理编译缓存 ----

rm -rf /tmp/jiti/* 2>/dev/null || true

# ---- 3.5 文件权限收紧 ----

chmod 700 "${OPENCLAW_DIR}" 2>/dev/null || true
[ -d "${CREDENTIALS_DIR}" ] && chmod 700 "${CREDENTIALS_DIR}"

# ---- 4. 前台启动 ----

echo "[entrypoint] 启动 OpenClaw Gateway..."
echo "[entrypoint]   端口: ${OPENCLAW_GATEWAY_PORT}"
echo "[entrypoint]   绑定: ${OPENCLAW_GATEWAY_BIND}"
echo "[entrypoint]   日志级别: ${OPENCLAW_LOG_LEVEL}"

# exec 替换当前 shell 进程，让 Node.js 成为 PID 1
exec openclaw gateway --allow-unconfigured --bind lan
