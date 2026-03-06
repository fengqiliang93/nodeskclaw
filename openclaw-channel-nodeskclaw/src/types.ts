export type NoDeskClawAccountConfig = {
  enabled?: boolean;
  apiUrl?: string;
  workspaceId: string;
  instanceId: string;
  apiToken: string;
};

export type NoDeskClawChannelConfig = {
  accounts?: Record<string, NoDeskClawAccountConfig>;
};

export type ResolvedNoDeskClawAccount = {
  accountId: string;
  enabled: boolean;
  configured: boolean;
  apiUrl: string;
  workspaceId: string;
  instanceId: string;
  apiToken: string;
};

export type CollaborationPayload = {
  workspace_id: string;
  source_instance_id: string;
  target: string;
  text: string;
  depth: number;
};
