# M3 文档解析与索引设计

## 目标

M3 的目标是把 Wiki 附件中的真实文件转化为可检索的文本片段，并为后续语义检索和 AI 问答提供稳定的数据基础。

核心流程：

```text
Attachment Uploaded -> Create Index Job -> Parse File -> Chunk Text -> Embed Chunks -> Write ChromaDB -> Mark Ready
```

## 文件解析策略

首期支持 M2 已允许上传的 4 类文件：

| 类型 | 扩展名 | 解析策略 |
| --- | --- | --- |
| Markdown | `.md` | 直接按 UTF-8 文本读取，保留标题和列表文本 |
| TXT | `.txt` | 直接按 UTF-8 文本读取 |
| PDF | `.pdf` | 使用 PDF 解析库提取每页文本，保留页码 |
| DOCX | `.docx` | 使用 DOCX 解析库提取段落和表格文本 |

首期原则：

- 解析失败不影响原附件记录，只把索引任务标记为 `failed`。
- PDF 和 DOCX 只提取文本，不处理图片 OCR。
- 文件路径来自 `wiki_attachments.storage_path`。
- 解析结果需要保留来源位置，例如页码、段落序号或字符范围。

## 文本切分策略

默认切分参数：

```text
chunk_size = 900
chunk_overlap = 120
```

含义：

- 每个片段目标长度约 900 个字符。
- 相邻片段重叠约 120 个字符，减少上下文断裂。
- 先按标题、段落、空行切分；段落过长时再按字符窗口切分。
- 空白片段、过短噪音片段应丢弃。

片段编号从 `0` 开始：

```text
chunk_index = 0, 1, 2, ...
```

后续引用来源时使用：

```text
page_id + attachment_id + chunk_index + source_location
```

## 索引任务状态

新增索引任务状态：

```text
pending -> processing -> ready
pending -> processing -> failed
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| `pending` | 附件已上传，等待解析和索引 |
| `processing` | 正在解析、切分、Embedding 或写入 ChromaDB |
| `ready` | 全部片段已经写入 ChromaDB，可参与语义检索 |
| `failed` | 解析、Embedding 或写入向量库失败 |

建议新增 PostgreSQL 表 `document_index_jobs`：

| 字段 | 用途 |
| --- | --- |
| `id` | 索引任务 ID |
| `page_id` | 所属 Wiki 页面 |
| `attachment_id` | 所属附件 |
| `status` | `pending`、`processing`、`ready`、`failed` |
| `chunk_count` | 成功写入的片段数量 |
| `error_message` | 失败原因摘要 |
| `started_at` | 开始处理时间 |
| `finished_at` | 完成或失败时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

首期可以用 API 同步触发索引，后续再迁移到 worker 或队列。

## ChromaDB 元数据

每个向量片段写入 ChromaDB 时，必须保存可追溯元数据：

```json
{
  "document_id": "attachment:{attachment_id}:chunk:{chunk_index}",
  "page_id": 1,
  "attachment_id": 2,
  "index_job_id": 3,
  "title": "页面标题",
  "filename": "runbook.txt",
  "chunk_index": 0,
  "source_path": "backend/storage/uploads/1/example.txt",
  "source_type": "txt",
  "source_location": "chars:0-900"
}
```

设计原则：

- `document_id` 必须稳定，重复索引同一附件时可以先删除旧片段再写入新片段。
- `source_location` 用于后续引用定位。
- `title` 和 `filename` 用于检索结果展示。
- PostgreSQL 保存任务状态，ChromaDB 保存向量片段和片段元数据。

## Embedding Provider

首期采用统一适配层，不把业务逻辑绑定到某个模型。

建议接口：

```python
class EmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...
```

默认策略：

- 开发阶段先实现 `FakeEmbeddingProvider`，根据文本生成确定性向量，用于打通 ChromaDB 写入、查询和测试流程。
- 后续再新增 `OpenAIEmbeddingProvider` 或本地模型 Provider。
- 业务服务只依赖 `EmbeddingProvider` 接口，不直接调用具体模型 SDK。

这样可以先验证解析、切分、状态和 ChromaDB 写入闭环，再替换真实 Embedding 模型。

## API 规划

建议新增接口：

```text
POST /api/v1/wiki/attachments/{attachment_id}/index
GET  /api/v1/wiki/attachments/{attachment_id}/index
GET  /api/v1/wiki/pages/{page_id}/index-jobs
```

用途：

- `POST /attachments/{attachment_id}/index`：创建并执行索引任务。
- `GET /attachments/{attachment_id}/index`：查看某个附件最近一次索引状态。
- `GET /pages/{page_id}/index-jobs`：查看页面下所有附件索引状态。

权限：

- 创建索引需要 `wiki:update`。
- 查看索引状态需要 `wiki:read`。

## 实施顺序

1. 新增 `document_index_jobs` 模型和迁移。
2. 新增文件解析服务，先支持 `.md` 和 `.txt`。
3. 新增文本切分服务。
4. 新增 Embedding Provider 适配层和 `FakeEmbeddingProvider`。
5. 新增 ChromaDB 写入服务。
6. 新增索引 API 和状态查询 API。
7. 补 PDF、DOCX 解析依赖和解析器。
8. 前端展示附件索引状态。

## 当前取舍

- 先实现同步索引，不立即引入 worker，降低首期复杂度。
- 先用 Fake Embedding 打通流程，不立即依赖外部模型或密钥。
- PDF 和 DOCX 解析放在基础 `.md`、`.txt` 流程打通之后补齐。
- ChromaDB 元数据必须从第一版就完整设计，避免后续引用来源不可追溯。
