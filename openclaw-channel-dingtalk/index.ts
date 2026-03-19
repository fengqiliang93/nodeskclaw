import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";
import { dingtalkPlugin, resolveAccount } from "./src/channel.js";
import { setDingTalkRuntime } from "./src/runtime.js";
import { DingTalkStreamClient } from "./src/stream.js";
import { storeSessionWebhook } from "./src/send.js";
import type { DingTalkRobotMessage, ResolvedDingTalkAccount } from "./src/types.js";

const CHANNEL_KEY = "dingtalk";
const GATEWAY_PORT_DEFAULT = 3000;

let streamClient: DingTalkStreamClient | null = null;

function getGatewayToken(): string {
  return process.env.GATEWAY_TOKEN || process.env.OPENCLAW_GATEWAY_TOKEN || "";
}

function getGatewayPort(): number {
  return parseInt(process.env.OPENCLAW_GATEWAY_PORT ?? "", 10) || GATEWAY_PORT_DEFAULT;
}

async function routeInboundMessage(
  msg: DingTalkRobotMessage,
  account: ResolvedDingTalkAccount,
): Promise<void> {
  if (msg.sessionWebhook) {
    storeSessionWebhook({
      webhook: msg.sessionWebhook,
      expiredTime: msg.sessionWebhookExpiredTime,
      conversationId: msg.conversationId,
      senderStaffId: msg.senderStaffId,
    });
  }

  const text = msg.text?.content?.trim();
  if (!text) return;

  const gatewayPort = getGatewayPort();
  const token = getGatewayToken();
  const url = `http://localhost:${gatewayPort}/v1/chat/completions`;

  const sessionKey = `dingtalk:${msg.conversationId}:${msg.senderStaffId}`;
  const replyTarget = `${msg.conversationId}:${msg.senderStaffId}`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-OpenClaw-Session-Key": sessionKey,
      },
      body: JSON.stringify({
        model: "gpt-4",
        messages: [{ role: "user", content: text }],
        stream: true,
      }),
    });

    if (!resp.ok || !resp.body) {
      console.error("[dingtalk] Gateway returned", resp.status);
      return;
    }

    let fullResponse = "";
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") continue;
        try {
          const parsed = JSON.parse(data);
          const delta = parsed.choices?.[0]?.delta?.content;
          if (delta) fullResponse += delta;
        } catch {}
      }
    }

    if (fullResponse.trim()) {
      const { sendTextMessage } = await import("./src/send.js");
      await sendTextMessage(account, replyTarget, fullResponse.trim());
    }
  } catch (err) {
    console.error("[dingtalk] Failed to route message to gateway:", err);
  }
}

const plugin = {
  id: "dingtalk",
  name: "DingTalk",
  description: "DingTalk channel plugin via Stream protocol",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setDingTalkRuntime(api.runtime);
    api.registerChannel({ plugin: dingtalkPlugin });

    const accounts = dingtalkPlugin.config.listAccountIds(api.config);
    for (const accountId of accounts) {
      const account = resolveAccount(api.config, accountId);
      if (!account.configured || !account.enabled) continue;

      if (streamClient) {
        streamClient.stop();
      }

      streamClient = new DingTalkStreamClient(account, routeInboundMessage);
      streamClient.start().catch((err) => {
        console.error("[dingtalk] Failed to start Stream client:", err);
      });

      console.log(`[dingtalk] Stream client started for account "${accountId}"`);
      break;
    }
  },
};

export default plugin;
