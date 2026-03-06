# Gene Templates

## 用途

存放预制的基因/基因组模板 JSON，后端启动时自动 seed 到数据库。

## 目录结构

```
gene_templates/
├── README.md
├── mcp_blackboard_tools.json        # 黑板工具基因（任务 CRUD + 工作循环）
├── mcp_topology_awareness.json      # 拓扑感知基因（工位、邻居查询）
├── mcp_performance_reader.json      # 效能数据读取基因
├── mcp_proposals.json               # 提案/审批基因
├── mcp_gene_discovery.json          # 基因发现/安装基因
├── meta_gene_ai_hc.json             # AI HC 招聘元基因
├── meta_gene_reorg.json             # 自组织重构元基因
├── meta_gene_culture.json           # 团队文化元基因
├── meta_gene_self_improve.json      # 自我改进元基因
├── meta_gene_innovation.json        # 创新探索元基因
├── meta_gene_akr_decomposer.json   # AKR 分解元基因（O -> KR -> Task）
├── genome_self_management.json      # 自管理基因组（捆绑 5 个 MCP 工具基因）
├── workflow_genome_example.json     # 内容创作流水线基因组（含拓扑推荐）
└── workflow_step_template.json      # 工作流步骤基因的 manifest 模板（不入库）
```

## 分类

| 类型 | 文件 | slug | 说明 |
|------|------|------|------|
| MCP 工具基因 | mcp_blackboard_tools.json | nodeskclaw-blackboard-tools | 任务创建/更新/归档 + 工作循环指令 |
| MCP 工具基因 | mcp_topology_awareness.json | nodeskclaw-topology-awareness | 工位拓扑感知 |
| MCP 工具基因 | mcp_performance_reader.json | nodeskclaw-performance-reader | 效能数据读取 |
| MCP 工具基因 | mcp_proposals.json | nodeskclaw-proposals | 提案审批流程 |
| MCP 工具基因 | mcp_gene_discovery.json | nodeskclaw-gene-discovery | 基因搜索与安装 |
| 元基因 | meta_gene_ai_hc.json | ai-hc-recruiter | AI 招聘决策 |
| 元基因 | meta_gene_reorg.json | self-reorg | 自组织重构 |
| 元基因 | meta_gene_culture.json | team-culture-concise | 团队文化塑造 |
| 元基因 | meta_gene_self_improve.json | self-improvement | 自我改进循环 |
| 元基因 | meta_gene_innovation.json | innovation-scout | 创新探索能力 |
| 元基因 | meta_gene_akr_decomposer.json | akr-decomposer | AKR 分解（O -> KR -> Task） |
| 基因组 | genome_self_management.json | nodeskclaw-self-management | 捆绑全部 5 个 MCP 工具基因 |
| 基因组 | workflow_genome_example.json | content-creation-pipeline | 线性内容创作流水线 |
| 模板 | workflow_step_template.json | — | 工作流步骤 manifest 模板（不入库） |

## Seed 机制

后端 `main.py` 启动时（迁移 33）自动批量 seed：
- 新模板：插入到 `genes` / `genomes` 表
- 已有模板：更新 `manifest` / `description` / `tags`
- `workflow_step_template.json` 不参与 seed
