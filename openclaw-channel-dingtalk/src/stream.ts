import type {
  DingTalkStreamEndpoint,
  DingTalkStreamFrame,
  DingTalkRobotMessage,
  ResolvedDingTalkAccount,
} from "./types.js";

const DINGTALK_API = "https://api.dingtalk.com";
const OPEN_CONNECTION_PATH = "/v1.0/gateway/connections/open";
const ROBOT_TOPIC = "/v1.0/im/bot/messages/get";
const PING_TOPIC = "/v1.0/gateway/connections/ping";

const RECONNECT_BASE_MS = 3_000;
const RECONNECT_MAX_MS = 60_000;

type MessageHandler = (msg: DingTalkRobotMessage, account: ResolvedDingTalkAccount) => void;

export class DingTalkStreamClient {
  private account: ResolvedDingTalkAccount;
  private ws: WebSocket | null = null;
  private onMessage: MessageHandler;
  private stopped = false;
  private reconnectAttempt = 0;

  constructor(account: ResolvedDingTalkAccount, onMessage: MessageHandler) {
    this.account = account;
    this.onMessage = onMessage;
  }

  async start(): Promise<void> {
    this.stopped = false;
    this.reconnectAttempt = 0;
    await this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.ws) {
      try { this.ws.close(); } catch {}
      this.ws = null;
    }
  }

  private async connect(): Promise<void> {
    if (this.stopped) return;

    try {
      const endpoint = await this.openConnection();
      this.setupWebSocket(endpoint);
      this.reconnectAttempt = 0;
    } catch (err) {
      console.error("[dingtalk-stream] Failed to open connection:", err);
      this.scheduleReconnect();
    }
  }

  private async openConnection(): Promise<DingTalkStreamEndpoint> {
    const resp = await fetch(`${DINGTALK_API}${OPEN_CONNECTION_PATH}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: this.account.clientId,
        clientSecret: this.account.clientSecret,
        subscriptions: [
          { type: "EVENT", topic: "*" },
          { type: "CALLBACK", topic: ROBOT_TOPIC },
        ],
      }),
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`DingTalk gateway returned ${resp.status}: ${text}`);
    }

    const body = (await resp.json()) as { endpoint: string; ticket: string };
    if (!body.endpoint || !body.ticket) {
      throw new Error("DingTalk gateway missing endpoint/ticket");
    }

    return { endpoint: body.endpoint, ticket: body.ticket };
  }

  private setupWebSocket(ep: DingTalkStreamEndpoint): void {
    const url = `${ep.endpoint}?ticket=${encodeURIComponent(ep.ticket)}`;

    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      console.log("[dingtalk-stream] WebSocket connected");
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const frame = JSON.parse(String(event.data)) as DingTalkStreamFrame;
        this.handleFrame(frame, ws);
      } catch (err) {
        console.error("[dingtalk-stream] Failed to parse frame:", err);
      }
    };

    ws.onerror = (event: Event) => {
      console.error("[dingtalk-stream] WebSocket error:", event);
    };

    ws.onclose = () => {
      console.log("[dingtalk-stream] WebSocket closed");
      this.ws = null;
      if (!this.stopped) {
        this.scheduleReconnect();
      }
    };
  }

  private handleFrame(frame: DingTalkStreamFrame, ws: WebSocket): void {
    const topic = frame.headers?.topic;
    const messageId = frame.headers?.messageId;

    if (topic === PING_TOPIC || frame.type === "SYSTEM") {
      this.sendAck(ws, messageId);
      return;
    }

    if (frame.type === "CALLBACK" && topic === ROBOT_TOPIC) {
      try {
        const msg = JSON.parse(frame.data) as DingTalkRobotMessage;
        this.onMessage(msg, this.account);
      } catch (err) {
        console.error("[dingtalk-stream] Failed to parse robot message:", err);
      }
      this.sendAck(ws, messageId);
      return;
    }

    if (messageId) {
      this.sendAck(ws, messageId);
    }
  }

  private sendAck(ws: WebSocket, messageId?: string): void {
    if (ws.readyState !== WebSocket.OPEN) return;

    const ack = {
      code: 200,
      headers: messageId ? { contentType: "application/json", messageId } : {},
      message: "OK",
      data: JSON.stringify({ response: "OK" }),
    };

    try {
      ws.send(JSON.stringify(ack));
    } catch (err) {
      console.error("[dingtalk-stream] Failed to send ACK:", err);
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;

    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempt),
      RECONNECT_MAX_MS,
    );
    this.reconnectAttempt++;

    console.log(`[dingtalk-stream] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempt})`);
    setTimeout(() => this.connect(), delay);
  }
}
