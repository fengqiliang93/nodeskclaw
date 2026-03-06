# Gene Templates

## 状态

**这些模板已迁移到 GeneHub Registry，不再作为启动时 seed 数据使用。**

- 上传脚本：`scripts/upload_seeds_to_genehub.py`
- 迁移时间：2026-03-06
- 原 seed 机制（`main.py` 迁移 27 / 33）已移除

本目录保留 JSON 文件作为参考备份。如需修改基因内容，请直接在 GeneHub 上操作。

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
├── meta_gene_akr_decomposer.json    # AKR 分解元基因（O -> KR -> Task）
├── genome_self_management.json      # 自管理基因组（捆绑 5 个 MCP 工具基因）
├── workflow_genome_example.json     # 内容创作流水线基因组（含拓扑推荐）
└── workflow_step_template.json      # 工作流步骤基因的 manifest 模板（不入库）
```

## 分类

| 类型 | 文件 | slug | GeneHub 状态 |
|------|------|------|-------------|
| MCP 工具基因 | mcp_blackboard_tools.json | nodeskclaw-blackboard-tools | 已上传 |
| MCP 工具基因 | mcp_topology_awareness.json | nodeskclaw-topology-awareness | 已上传 |
| MCP 工具基因 | mcp_performance_reader.json | nodeskclaw-performance-reader | 已上传 |
| MCP 工具基因 | mcp_proposals.json | nodeskclaw-proposals | 已上传 |
| MCP 工具基因 | mcp_gene_discovery.json | nodeskclaw-gene-discovery | 已上传 |
| 元基因 | meta_gene_ai_hc.json | ai-hc-recruiter | 已上传 |
| 元基因 | meta_gene_reorg.json | self-reorg | 已上传 |
| 元基因 | meta_gene_culture.json | team-culture-concise | 已上传 |
| 元基因 | meta_gene_self_improve.json | self-improvement | 已上传 |
| 元基因 | meta_gene_innovation.json | innovation-scout | 已上传 |
| 元基因 | meta_gene_akr_decomposer.json | akr-decomposer | 已上传 |
| 基因组 | genome_self_management.json | nodeskclaw-self-management | 已上传 |
| 基因组 | workflow_genome_example.json | content-creation-pipeline | 未上传（引用的步骤基因不存在） |
| 模板 | workflow_step_template.json | -- | 不入库 |
