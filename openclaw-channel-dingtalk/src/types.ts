export type DingTalkAccountConfig = {
  clientId: string;
  clientSecret: string;
  robotCode?: string;
  agentId?: string;
  corpId?: string;
  dmPolicy?: string;
  groupPolicy?: string;
  enabled?: boolean;
};

export type ResolvedDingTalkAccount = {
  accountId: string;
  enabled: boolean;
  configured: boolean;
  clientId: string;
  clientSecret: string;
  robotCode: string;
  corpId: string;
};

export type DingTalkStreamEndpoint = {
  endpoint: string;
  ticket: string;
};

export type DingTalkRobotMessage = {
  conversationId: string;
  chatbotCorpId: string;
  chatbotUserId: string;
  msgId: string;
  senderNick: string;
  senderStaffId: string;
  senderCorpId: string;
  sessionWebhook: string;
  sessionWebhookExpiredTime: number;
  createAt: number;
  conversationType: "1" | "2";
  atUsers: Array<{ dingtalkId: string; staffId?: string }>;
  text: { content: string };
  msgtype: string;
};

export type DingTalkStreamFrame = {
  specVersion: string;
  type: string;
  headers: Record<string, string>;
  data: string;
};

export type SessionWebhookEntry = {
  webhook: string;
  expiredTime: number;
  conversationId: string;
  senderStaffId: string;
};
