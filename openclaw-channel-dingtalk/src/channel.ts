import type { ChannelPlugin, OpenClawConfig } from "openclaw/plugin-sdk";
import type { DingTalkAccountConfig, ResolvedDingTalkAccount } from "./types.js";
import { getDingTalkRuntime } from "./runtime.js";
import { sendTextMessage, sendMarkdownMessage } from "./send.js";

const CHANNEL_KEY = "dingtalk";
const DEFAULT_ACCOUNT_ID = "default";

function getChannelSection(cfg: OpenClawConfig): Record<string, unknown> | undefined {
  return (cfg as Record<string, unknown>).channels?.[CHANNEL_KEY] as
    | Record<string, unknown>
    | undefined;
}

function resolveAccount(
  cfg: OpenClawConfig,
  accountId?: string | null,
): ResolvedDingTalkAccount {
  const section = getChannelSection(cfg);
  const accounts = (section?.accounts ?? {}) as Record<string, DingTalkAccountConfig>;
  const id = accountId ?? DEFAULT_ACCOUNT_ID;
  const raw = accounts[id];

  if (!raw) {
    return {
      accountId: id,
      enabled: false,
      configured: false,
      clientId: "",
      clientSecret: "",
      robotCode: "",
      corpId: "",
    };
  }

  return {
    accountId: id,
    enabled: raw.enabled !== false,
    configured: Boolean(raw.clientId && raw.clientSecret),
    clientId: raw.clientId ?? "",
    clientSecret: raw.clientSecret ?? "",
    robotCode: raw.robotCode ?? raw.clientId ?? "",
    corpId: raw.corpId ?? "",
  };
}

export { resolveAccount };

export const dingtalkPlugin: ChannelPlugin<ResolvedDingTalkAccount> = {
  id: CHANNEL_KEY,
  meta: {
    id: CHANNEL_KEY,
    label: "DingTalk",
    selectionLabel: "DingTalk (钉钉)",
    docsPath: "/channels/dingtalk",
    blurb: "DingTalk enterprise messaging via Stream protocol.",
    aliases: ["ding"],
  },
  capabilities: {
    chatTypes: ["direct", "channel"],
  },
  config: {
    listAccountIds: (cfg) => {
      const section = getChannelSection(cfg);
      return Object.keys((section?.accounts ?? {}) as Record<string, unknown>);
    },
    resolveAccount: (cfg, accountId) => resolveAccount(cfg, accountId),
    isConfigured: (account) => account.configured,
    isEnabled: (account) => account.enabled,
    describeAccount: (account) => ({
      accountId: account.accountId,
      enabled: account.enabled,
      configured: account.configured,
    }),
  },
  outbound: {
    deliveryMode: "direct",
    sendText: async ({ cfg, to, text, accountId }) => {
      const account = resolveAccount(cfg, accountId);
      const result = await sendTextMessage(account, to, text);

      getDingTalkRuntime().channel.activity.record({
        channel: CHANNEL_KEY,
        accountId: account.accountId,
        direction: "outbound",
      });

      return result;
    },
    sendMedia: async ({ cfg, to, text, mediaUrl, accountId }) => {
      const account = resolveAccount(cfg, accountId);
      const body = mediaUrl ? `${text || ""}\n[${mediaUrl}]`.trim() : (text || "");
      const result = await sendMarkdownMessage(account, to, body);

      getDingTalkRuntime().channel.activity.record({
        channel: CHANNEL_KEY,
        accountId: account.accountId,
        direction: "outbound",
      });

      return result;
    },
  },
  status: {
    buildAccountSnapshot: ({ account }) => ({
      accountId: account.accountId,
      enabled: account.enabled,
      configured: account.configured,
    }),
  },
};
