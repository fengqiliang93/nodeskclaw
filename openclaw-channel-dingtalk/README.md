# openclaw-channel-dingtalk

OpenClaw Channel 插件 -- 通过钉钉 Stream 协议收发消息。

## 功能

- 通过 DingTalk Stream 协议接收机器人消息（单聊 + 群聊 @机器人）
- 通过 sessionWebhook 回复消息，过期后回退到 Robot batchSend API
- 支持 text 和 markdown 消息格式

## 目录结构

```
openclaw-channel-dingtalk/
  openclaw.plugin.json   # 插件元数据
  package.json           # 零 npm 运行时依赖
  index.ts               # 插件入口
  README.md
  src/
    types.ts             # 类型定义
    runtime.ts           # PluginRuntime 持有者
    stream.ts            # DingTalk Stream 协议实现（fetch + WebSocket）
    send.ts              # 消息发送（sessionWebhook + Robot API）
    channel.ts           # ChannelPlugin 接口实现
```

## 配置

在 OpenClaw 的 `openclaw.json` 中配置 `channels.dingtalk`：

```json
{
  "channels": {
    "dingtalk": {
      "accounts": {
        "default": {
          "clientId": "your-app-client-id",
          "clientSecret": "your-app-client-secret",
          "enabled": true
        }
      }
    }
  }
}
```

配置项说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| clientId | 是 | 钉钉应用 Client ID |
| clientSecret | 是 | 钉钉应用 Client Secret |
| robotCode | 否 | 机器人 Code，默认等于 clientId |
| corpId | 否 | 企业 ID |
| enabled | 否 | 是否启用，默认 true |

## 部署

插件由 DeskClaw 后端自动部署到 OpenClaw 实例的 `.openclaw/extensions/openclaw-channel-dingtalk/` 目录。
通过 Channel 配置页面保存的凭证会写入实例的 `openclaw.json`。

## 技术方案

插件使用 Node.js 内置 `fetch` 和 `WebSocket` API 自行实现 DingTalk Stream 协议，
不依赖 `dingtalk-stream` npm 包（因为插件通过文件复制部署，不执行 `npm install`）。

Stream 协议流程：
1. POST `/v1.0/gateway/connections/open` 获取 WebSocket endpoint + ticket
2. 连接 WebSocket，发送 ticket 完成认证
3. 响应心跳 ping
4. 接收 TOPIC_ROBOT 消息回调
5. 通过 WebSocket 返回 ACK
