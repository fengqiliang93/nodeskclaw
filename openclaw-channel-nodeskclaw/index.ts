import type { OpenClawPluginApi, OpenClawPluginToolContext } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";
import { nodeskclawPlugin } from "./src/channel.js";
import { setNoDeskClawRuntime } from "./src/runtime.js";
import { startSSEServer } from "./src/sse-server.js";
import { createNoDeskClawTools } from "./src/tools.js";

const WORKSPACE_SESSION_PREFIX = "workspace:";

const plugin = {
  id: "nodeskclaw",
  name: "NoDeskClaw",
  description: "DeskClaw cyber office agent collaboration channel",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setNoDeskClawRuntime(api.runtime);
    api.registerChannel({ plugin: nodeskclawPlugin });
    startSSEServer();
    api.registerTool((ctx: OpenClawPluginToolContext) => {
      const wsId = ctx.sessionKey?.startsWith(WORKSPACE_SESSION_PREFIX)
        ? ctx.sessionKey.slice(WORKSPACE_SESSION_PREFIX.length)
        : undefined;
      return createNoDeskClawTools(api.config, wsId);
    }, {
      optional: true,
      names: [
        "nodeskclaw_blackboard",
        "nodeskclaw_topology",
        "nodeskclaw_performance",
        "nodeskclaw_proposals",
        "nodeskclaw_gene_discovery",
      ],
    });
  },
};

export default plugin;
