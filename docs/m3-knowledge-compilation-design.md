# M3 LLM Wiki 知识编译设计

## 目标

M3 的目标不再是把上传附件切分成 chunk、生成 embedding 并写入 ChromaDB。新的目标是把 Wiki 附件和原始资料转化为可维护的结构化 Wiki 知识层。

核心流程：

```text
Attachment Uploaded
-> Create Compilation Job
-> Parse Source
-> Extract Knowledge Units
-> Normalize and Merge
-> Generate or Update Wiki Pages
-> Build Page Relationships
-> Record Knowledge Revision
```

本阶段关注的是：

- 知识如何形成
- 知识如何组织
- 知识如何更新
- 知识如何沉淀
- 知识之间如何建立关联

而不是如何从大量原始文本中实时检索片段。

## 文件解析策略

首期支持 M2 已允许上传的 4 类文件：

| 类型 | 扩展名 | 解析策略 |
| --- | --- | --- |
| Markdown | `.md` | 直接按 UTF-8 文本读取，保留标题、列表和代码块边界 |
| TXT | `.txt` | 直接按 UTF-8 文本读取，保留段落边界 |
| PDF | `.pdf` | 使用 PDF 解析库提取每页文本，保留页码 |
| DOCX | `.docx` | 使用 DOCX 解析库提取段落、标题和表格文本 |

首期原则：

- 解析失败不影响原附件记录，只把知识编译任务标记为 `failed`。
- PDF 和 DOCX 先只提取文本，不处理图片 OCR。
- 文件路径来自 `wiki_attachments.storage_path`。
- 解析结果需要保留来源位置，例如页码、段落序号或字符范围。
- 原始资料解析结果只作为知识提炼输入，不作为最终查询资产。

## 知识单元提取

LLM Wiki 的中间产物不是 chunk，而是候选知识单元。

建议知识单元包含：

| 字段 | 用途 |
| --- | --- |
| `title` | 候选知识标题 |
| `type` | `concept`、`system`、`process`、`rule`、`term`、`event`、`incident` 等 |
| `summary` | 知识摘要 |
| `content` | 结构化正文草稿 |
| `source_attachment_id` | 来源附件 |
| `source_location` | 来源页码、段落或字符范围 |
| `confidence` | LLM 对提取结果的置信度 |
| `merge_hint` | 可能应合并到的已有 Wiki 页面 |

提取时可以把长文本按段落或章节分批送入 LLM，但这些分批片段只是处理窗口，不应被设计为系统核心资产。

## Wiki 页面生成与更新策略

每个候选知识单元进入页面决策流程：

```text
Knowledge Unit
-> Match Existing Wiki Pages
-> Decide Create / Update / Merge / Skip
-> Generate Page Draft
-> Record Revision
```

页面决策：

| 决策 | 含义 |
| --- | --- |
| `create` | 没有合适页面，创建新 Wiki 页面 |
| `update` | 已有页面存在，但需要补充新内容 |
| `merge` | 候选知识与已有页面重复或高度重叠，合并并保留修订记录 |
| `skip` | 信息噪音、重复或置信度不足，暂不进入 Wiki |

Wiki 页面应优先沉淀为这些类型：

- 概念页
- 人物页
- 系统页
- 流程页
- 规则页
- 术语页
- 事件页
- 故障页

## 页面关系

知识编译任务需要尽量维护页面之间的关系，而不只是生成孤立页面。

建议首期支持关系类型：

| 关系 | 含义 |
| --- | --- |
| `references` | 页面 A 引用页面 B |
| `depends_on` | 页面 A 依赖页面 B |
| `belongs_to` | 页面 A 归属于页面 B |
| `related_to` | 页面 A 与页面 B 相关 |
| `similar_to` | 页面 A 与页面 B 相似 |
| `caused_by` | 故障或事件由某原因导致 |
| `resolved_by` | 故障或问题由某方案解决 |

页面关系用于后续 Wiki 浏览、影响分析、相似案例发现和基于 Wiki 的问答。

## 知识编译任务状态

新增任务状态：

```text
pending -> parsing -> extracting -> compiling -> ready
pending -> parsing/extracting/compiling -> failed
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| `pending` | 附件已上传，等待知识编译 |
| `parsing` | 正在解析原始资料 |
| `extracting` | 正在提取候选知识单元 |
| `compiling` | 正在生成或更新 Wiki 页面及页面关系 |
| `ready` | 知识编译完成 |
| `failed` | 解析、提取、页面生成或关系构建失败 |

建议新增 PostgreSQL 表 `knowledge_compilation_jobs`：

| 字段 | 用途 |
| --- | --- |
| `id` | 编译任务 ID |
| `page_id` | 任务关联的 Wiki 页面，可为空 |
| `attachment_id` | 任务处理的附件 |
| `status` | `pending`、`parsing`、`extracting`、`compiling`、`ready`、`failed` |
| `knowledge_unit_count` | 提取出的候选知识单元数量 |
| `created_page_count` | 新建 Wiki 页面数量 |
| `updated_page_count` | 更新 Wiki 页面数量 |
| `relationship_count` | 新建或更新页面关系数量 |
| `error_message` | 失败原因摘要 |
| `started_at` | 开始处理时间 |
| `finished_at` | 完成或失败时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

建议新增表 `knowledge_units` 保存候选知识单元，便于人工复核和后续调试。

建议新增表 `wiki_page_relationships` 保存页面关系。

建议复用或扩展现有 Wiki 版本记录，保存每次 LLM 生成、更新和合并的修订来源。

## 搜索能力的位置

本项目不排斥搜索，但搜索应服务于 Wiki。

推荐顺序：

1. 先实现 Wiki 页面标题、摘要、正文、标签和类型的关键词搜索。
2. 再实现基于页面关系的关联页面发现。
3. 如果需要语义能力，只对 Wiki 页面或知识单元建立辅助向量索引。
4. 不把原始附件 chunk 检索作为主问答路线。

如果未来使用 ChromaDB，元数据应围绕 Wiki 页面设计：

```json
{
  "document_id": "wiki_page:{page_id}:revision:{revision_id}",
  "page_id": 1,
  "revision_id": 3,
  "page_type": "system",
  "title": "支付系统巡检流程",
  "summary": "支付系统日常巡检的步骤、指标和异常处理方式",
  "tags": "payment,runbook,inspection"
}
```

## API 规划

建议新增接口：

```text
POST /api/v1/wiki/attachments/{attachment_id}/compile
GET  /api/v1/wiki/attachments/{attachment_id}/compile
GET  /api/v1/wiki/pages/{page_id}/compilation-jobs
GET  /api/v1/wiki/knowledge-units
POST /api/v1/wiki/knowledge-units/{unit_id}/apply
GET  /api/v1/wiki/pages/{page_id}/relationships
```

用途：

- `POST /attachments/{attachment_id}/compile`：创建并执行知识编译任务。
- `GET /attachments/{attachment_id}/compile`：查看某个附件最近一次知识编译状态。
- `GET /pages/{page_id}/compilation-jobs`：查看页面相关编译任务。
- `GET /knowledge-units`：查看候选知识单元，支持人工复核。
- `POST /knowledge-units/{unit_id}/apply`：将候选知识单元应用到 Wiki 页面。
- `GET /pages/{page_id}/relationships`：查看页面关系。

权限：

- 创建知识编译任务需要 `wiki:update`。
- 应用候选知识单元需要 `wiki:update`。
- 查看编译状态、知识单元和页面关系需要 `wiki:read`。

## 实施顺序

1. 将旧的“索引任务”命名和文档统一调整为“知识编译任务”。
2. 新增 `knowledge_compilation_jobs` 模型和迁移。
3. 新增原始文件解析服务，先支持 `.md` 和 `.txt`。
4. 新增候选知识单元 schema、模型和存储表。
5. 设计 LLM 知识提取 Prompt 与返回 JSON 结构。
6. 新增 Wiki 页面创建、更新、合并的决策服务。
7. 新增页面关系模型与关系构建服务。
8. 新增知识编译 API 和状态查询 API。
9. 前端展示知识编译状态、候选知识单元和页面关系。
10. 后续再补 PDF、DOCX 解析和可选的 Wiki 页面语义搜索。

## 当前取舍

- 先打通 `.md`、`.txt` 到 Wiki 页面草稿的最小闭环。
- 先保留人工复核入口，避免 LLM 自动覆盖重要知识。
- ChromaDB 和 Embedding 暂不作为 M3 主目标。
- 重点保证 Wiki 页面、知识单元、页面关系和修订记录的数据结构清晰。
