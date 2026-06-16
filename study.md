# OpsMind 学习记录

本文件记录 OpsMind 开发过程中的关键学习点。内容按模块和日期精简归档，重点保留“做了什么、为什么做、涉及哪些文件、如何验证、下一步是什么”。

## 2026-06-05：M1 用户登录与 JWT 身份校验

### 当前目标

让 OpsMind 具备基础登录能力：用户提交用户名和密码，后端校验成功后返回 JWT；之后请求通过 `Authorization: Bearer <access_token>` 携带身份。

这是权限系统入口。后续 Wiki 写操作、系统配置、用户管理和审计日志，都依赖“当前用户是谁”。

### 涉及文件

- `backend/app/core/config.py`：JWT、数据库等配置。
- `backend/app/core/security.py`：密码哈希、密码校验、Token 创建和解析。
- `backend/app/api/deps.py`：数据库会话、当前用户、管理员和权限检查依赖。
- `backend/app/api/routes/auth.py`：登录接口和当前用户接口。
- `backend/app/schemas/auth.py`：登录请求、Token 响应和用户响应结构。
- `backend/app/scripts/create_admin.py`：创建或更新本地管理员。
- `.env.example`：JWT 和管理员环境变量示例。
- `backend/app/main.py`：注册认证路由。

### 关键学习点

- JWT 的 `sub` 字段保存用户 ID，`exp` 控制过期时间。
- `SECRET_KEY` 用于签名和校验 Token，生产环境必须换成强随机值。
- `bcrypt` 用于密码哈希，不保存明文密码，也不能反推出原始密码。
- FastAPI 的 `Depends(...)` 可把“取 Token、取数据库会话、查当前用户”组织成可复用依赖。
- Pydantic Schema 用于接口输入输出校验，`Field(...)` 可设置长度限制。

### 验证方法与结果

执行过语法和轻量运行检查：

```powershell
backend\.venv\Scripts\python.exe -m compileall backend\app
```

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token; h=get_password_hash('secret'); assert verify_password('secret', h); assert decode_access_token(create_access_token('1')) == '1'; print([r.path for r in app.routes if 'auth' in r.path])"
```

结果确认：

- Python 语法检查通过。
- 密码哈希和校验可用。
- JWT 可签发和解析。
- `/api/v1/auth/login`、`/api/v1/auth/me` 已注册。

### 遇到的问题

`passlib` 与当前 `bcrypt 5.0.0` 组合出现兼容问题。处理方式是移除 `passlib.context.CryptContext`，直接使用 `bcrypt` 完成哈希和校验。

## 2026-06-06：根据模块计划判断下一步

### 当前目标

根据 `docs/module-plan.md` 和仓库实际状态判断下一步，而不是凭印象推进。

### 涉及文件

- `docs/module-plan.md`：模块路线图。
- `backend/app/main.py`：健康检查和路由注册。
- `backend/app/api/routes/auth.py`：认证接口。
- `backend/app/models/`：用户、角色、权限、审计等模型。
- `backend/migrations/versions/`：数据库迁移。
- `deploy/docker-compose.yml`：本地 PostgreSQL、Redis、ChromaDB。
- `.env.example`：环境变量模板。
- `frontend/src/`：前端接入状态。

### 关键命令

```powershell
Get-Content -Path .\docs\module-plan.md -Encoding UTF8
Get-ChildItem -Force | Select-Object Name,Mode,Length,LastWriteTime
rg -n "health|/api/v1/health|FastAPI|APIRouter" backend/app
rg -n "User|Role|Permission|Audit|login|password|JWT|oauth|auth|token" backend/app backend/migrations
```

### 验证结果

- M0 工程骨架已经存在。
- M1 认证、权限和审计相关代码已经开始实现。
- 本地服务编排和环境变量模板存在。
- 下一步应优先做 M1 本地数据库联调，而不是重复创建目录或重复实现基础认证代码。

## 2026-06-06：更新本地数据库联调授权规则

### 当前目标

根据用户授权，更新 `AGENTS.md`：本地开发联调中的常规服务启动、迁移、种子数据、管理员初始化和接口验证，可由 AI 助手直接执行。

### 涉及文件

- `AGENTS.md`：仓库级协作规则。
- `study.md`：学习记录。

### 关键边界

AI 助手可直接执行：

- 启动、停止、重启本地 Docker Compose 服务。
- 执行已有本地数据库迁移。
- 执行已有种子数据脚本。
- 创建或更新本地开发管理员。
- 启动本地后端服务并调用健康检查、登录接口和当前用户接口验证。

仍需用户明确授权或亲自处理：

- Git 操作。
- 依赖升级。
- 删除或重置数据。
- 清空 Docker 数据卷。
- 修改生产或远程环境。
- 部署发布。

## 2026-06-06：完成 M1 本地联调与前端登录状态

### 当前目标

把 M1 从“代码存在”推进到“本地端到端可验证”，并让前端具备登录状态展示。

### 涉及文件

- `deploy/docker-compose.yml`：启动本地基础服务。
- `backend/migrations/versions/`：应用数据库迁移。
- `backend/app/scripts/seed_auth.py`：初始化角色和权限。
- `backend/app/scripts/create_admin.py`：创建或更新管理员。
- `frontend/src/`：前端登录和身份状态相关页面或组件。

### 关键命令

```powershell
docker compose -f .\deploy\docker-compose.yml --env-file .\.env up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.seed_auth
.\.venv\Scripts\python.exe -m app.scripts.create_admin
```

### 验证结果

- 本地 PostgreSQL、Redis、ChromaDB 可启动。
- 数据库迁移可执行到最新版本。
- 角色、权限和管理员可初始化。
- 登录接口和当前用户接口可完成本地联调。
- 前端可通过本地代理访问后端认证接口。

## 2026-06-06：补齐 M1 权限验证和审计日志

### 当前目标

验证普通用户和管理员在受保护接口上的权限差异，并确认关键操作会写入审计日志。

### 学习重点

- 401 表示未认证：请求没有合法身份。
- 403 表示已认证但无权限：用户身份有效，但权限不足。
- 权限码如 `wiki:read`、`wiki:create`、`wiki:update`、`wiki:delete` 用于描述具体操作能力。
- 审计日志用于记录“谁在什么时候做了什么”，后续排查和合规都依赖它。

### 验证结果

- 未登录访问受保护接口返回 401。
- 普通用户可执行授权范围内的操作。
- 普通用户执行删除等高权限操作返回 403。
- 管理员可执行管理类操作。
- 登录、创建、更新、删除等关键操作能写入审计日志。

## 2026-06-06：实现 M2 Wiki 与文档管理基础闭环

### 当前目标

实现 Wiki 分类、标签、页面、版本和附件元数据的基础 CRUD，并验证权限和审计链路。

### 涉及文件

- `backend/app/api/routes/wiki.py`：Wiki 相关接口。
- `backend/app/models/`：Wiki 分类、标签、页面、版本、附件等模型。
- `backend/app/schemas/`：Wiki 请求和响应结构。
- `backend/migrations/versions/`：Wiki 相关表结构迁移。
- `frontend/src/`：前端 Wiki 页面列表或基础入口。

### 验证结果

接口联调创建了分类、标签、Wiki 页面、页面更新、附件元数据和版本记录。关键结果：

```json
{
  "unauthenticated_list": 401,
  "user_delete": 403,
  "updated_status": "published",
  "version_count": 2,
  "admin_delete": "ok"
}
```

含义：

- 未登录访问 Wiki 页面列表返回 401。
- 普通用户可创建和更新页面。
- 页面创建和更新后生成版本记录。
- 普通用户删除页面返回 403。
- 管理员删除页面成功。
- 审计日志记录了 Wiki 相关操作。

### 下一步

M2 基础 CRUD 可用，但附件接口当时还只是记录 JSON 元数据，尚未接收真实文件内容。

## 2026-06-06：实现 Wiki 真实文件上传接口

### 当前目标

把 Wiki 附件接口从“记录 JSON 元数据”升级为“接收真实文件内容”。接口保持：

```text
POST /api/v1/wiki/pages/{page_id}/attachments
```

请求体改为 `multipart/form-data`，文件字段名为 `file`。

### 涉及文件

- `backend/app/api/routes/wiki.py`：文件上传、类型校验、大小校验、文件保存和附件记录创建。
- `backend/app/core/config.py`：上传目录和最大上传大小配置。
- `backend/requirements.txt`：新增 `python-multipart`。
- `.env.example`：上传目录和大小限制示例。
- `backend/storage/uploads/`：本地上传文件保存目录。

### 关键学习点

- `UploadFile` 和 `File(...)` 来自 FastAPI，用于处理 `multipart/form-data` 文件上传。
- `python-multipart` 是 FastAPI 解析表单文件所需依赖。
- `UPLOAD_STORAGE_DIR` 控制落盘目录，默认 `backend/storage/uploads`。
- `MAX_UPLOAD_BYTES` 控制最大上传大小，默认 20 MB。
- `uuid4().hex` 用于生成随机存储文件名，避免同名覆盖。
- 数据库继续保存原文件名、MIME 类型、大小、存储路径、上传用户和页面 ID。

### 验证方法与结果

执行过：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install python-multipart==0.0.20
.\backend\.venv\Scripts\python.exe -m compileall .\backend\app
```

结果：

- 语法检查通过。
- FastAPI 应用可导入。
- 上传工具逻辑可生成落盘路径并保存 `.txt` 测试文件。

首次完整接口联调未完成，原因是 Docker daemon 当时未就绪。

## 2026-06-06：检查 Docker 中为什么没有 opsmind 名称

### 当前目标

解释 Docker Desktop 中为什么没有直接叫 `opsmind` 的容器。

### 涉及文件

- `deploy/docker-compose.yml`：定义本地 PostgreSQL、Redis、ChromaDB 服务。

### 关键学习点

Docker Compose 默认容器名通常由“Compose 项目名 + 服务名 + 序号”组成。当前 Compose 文件位于 `deploy/`，服务名是：

```text
postgres
redis
chromadb
```

因此容器名可能显示为：

```text
deploy-postgres-1
deploy-redis-1
deploy-chromadb-1
```

没看到 `opsmind` 不代表 OpsMind 容器不存在，只是项目名不是 `opsmind`。

### 关键命令

```powershell
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
docker compose -f .\deploy\docker-compose.yml --env-file .\.env ps
```

### 验证结果

看到过 `deploy-postgres-1`、`deploy-redis-1`、`deploy-chromadb-1`，它们是 OpsMind 本地基础服务。`localmind-*` 容器属于另一个项目。

## 2026-06-06：明确“核心实现”和“基础操作”的协作边界

### 当前目标

根据用户说明更新 `AGENTS.md`：用户亲自处理核心业务和关键技术判断，AI 助手负责基础工程操作和前端实现。

### 涉及文件

- `AGENTS.md`：协作约束。
- `study.md`：学习记录。

### 关键边界

用户重点负责：

- API 路由设计与编写。
- 服务端业务逻辑。
- 认证和权限模型。
- 数据库表的业务含义。
- 核心业务设计和关键技术判断。

AI 助手可代为完成：

- 数据库表构建和迁移执行。
- 种子数据和本地管理员初始化。
- 本地服务启停。
- 命令执行、环境检查、配置调整。
- 格式化、构建、测试。
- 前端目录内的开发、修改和验证。

仍不默认代办：

- Git 操作。
- 依赖升级。
- 数据删除或重置。
- 清空数据卷。
- 生产或远程环境修改。
- 部署发布。

## 2026-06-06：完成 Wiki 文件上传接口本地联调

### 当前目标

补齐 M2 真实文件上传验证：启动本地服务，执行迁移和初始化，再通过接口完成登录、创建页面、上传 `.txt` 文件和读取附件列表。

### 涉及文件

- `deploy/docker-compose.yml`：本地 PostgreSQL、Redis、ChromaDB。
- `backend/migrations/versions/`：数据库迁移。
- `backend/app/scripts/seed_auth.py`：权限和角色初始化。
- `backend/app/scripts/create_admin.py`：本地管理员初始化。
- `backend/app/api/routes/wiki.py`：真实文件上传接口。
- `backend/storage/uploads/`：上传文件落盘目录。

### 关键命令

```powershell
docker compose -f .\deploy\docker-compose.yml --env-file .\.env up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.seed_auth
.\.venv\Scripts\python.exe -m app.scripts.create_admin
```

### 验证结果

本地服务已启动：

```text
deploy-postgres-1   Up   0.0.0.0:5433->5432/tcp
deploy-redis-1      Up   0.0.0.0:6380->6379/tcp
deploy-chromadb-1   Up   0.0.0.0:8001->8000/tcp
```

迁移和初始化成功：

```text
alembic upgrade head 成功
Seeded auth roles and permissions.
Created or updated admin user: admin
```

上传接口验证成功：

```json
{
  "health": "ok",
  "page_id": 2,
  "attachment_id": 2,
  "filename": "opsmind-upload-test-20260606164019.txt",
  "content_type": "text/plain",
  "size_bytes": 39,
  "storage_path": "backend\\storage\\uploads\\2\\b67018ce020742e48afde7dc7507154f.txt",
  "attachment_count": 1
}
```

含义：

- 后端健康检查返回 `ok`。
- 管理员登录成功。
- 成功创建测试 Wiki 页面。
- 成功上传真实 `.txt` 文件。
- 附件列表能读到 1 条记录。
- 数据库中的 `storage_path` 指向实际落盘文件。

### 下一步

M2 真实文件上传已经通过本地联调。下一项核心任务可进入 M3：设计文档解析与索引方案，包括文件类型解析、文本切分、索引任务状态流转，以及 ChromaDB 元数据字段。

## 2026-06-06：精简学习记录

### 当前目标

按用户要求精简根目录 `study.md`，把原先约 55KB 的长篇过程记录整理成按模块归档的摘要。

### 涉及文件

- `study.md`：删除重复解释，保留关键学习点、涉及文件、验证命令、验证结果和下一步。

### 本次执行的命令

```powershell
Get-ChildItem -Force | Select-Object Name,Length,LastWriteTime
Get-Content -Path .\study.md -Raw
Get-Content -Path .\study.md -Raw -Encoding UTF8
Select-String -Path .\study.md -Pattern '^## ' -Encoding UTF8 | Select-Object LineNumber,Line
```

说明：

- `Get-ChildItem` 用于确认根目录文件和 `study.md` 大小。
- `Get-Content -Raw` 用于读取完整文件内容。
- `-Encoding UTF8` 用于避免中文被终端按错误编码显示。
- `Select-String` 用于列出二级标题，确认原始记录的主题结构。

### 验证方法

精简后应确认：

- 文件仍为 UTF-8 中文内容。
- 每个已完成模块仍能看出目标、文件、验证方式和结果。
- 不再保留大量重复的命令拆解和库函数逐行解释。

## 2026-06-06：确定 M3 文档解析与索引设计

### 当前目标

用户授权 AI 助手决定 M3 核心方案。本次新增 `docs/m3-indexing-design.md`，明确文档解析、文本切分、索引任务状态、ChromaDB 元数据、Embedding Provider 和实施顺序。

### 涉及文件

- `docs/m3-indexing-design.md`：M3 文档解析与索引设计文档。
- `study.md`：记录本次设计决策和原因。

### 关键决策

- `.md` 和 `.txt` 先按 UTF-8 文本读取，优先打通最小闭环。
- `.pdf` 后续用 PDF 解析库按页提取文本，保留页码。
- `.docx` 后续用 DOCX 解析库提取段落和表格文本。
- 默认切分参数为 `chunk_size = 900`、`chunk_overlap = 120`。
- 索引状态流转为 `pending -> processing -> ready / failed`。
- ChromaDB 元数据必须包含 `page_id`、`attachment_id`、`chunk_index`、`source_path`、`source_location` 等可追溯字段。
- 首期先实现 `FakeEmbeddingProvider`，用于打通解析、切分、状态和 ChromaDB 写入流程；真实 OpenAI 或本地 Embedding Provider 后续再接入。
- 首期同步触发索引，不立即引入 worker 或队列。

### 为什么这样设计

先用 `.md`、`.txt` 和 Fake Embedding 可以避免一开始被 PDF/DOCX 解析依赖、模型密钥、网络、费用和向量维度问题卡住。M3 的第一目标是验证完整链路：附件文件能被读取、切分、写入 ChromaDB，并能通过索引状态告诉前端是否成功。

### 验证方法

本次是设计文档变更，没有运行接口测试。验证方式是检查 `docs/m3-indexing-design.md` 是否覆盖：

- 支持文件类型。
- 文本切分参数。
- 索引任务表设计。
- ChromaDB 元数据字段。
- Embedding Provider 抽象。
- API 规划。
- 实施顺序。

### 下一步

按设计先实施 `.md` 和 `.txt` 的最小闭环：新增索引任务表、文本解析服务、切分服务、Fake Embedding、ChromaDB 写入服务和索引状态 API。PDF 与 DOCX 在最小闭环通过后再补。

## 2026-06-06：调整核心后端任务的指导方式

### 当前目标

用户要求：对需要用户亲自完成的核心后端任务，AI 助手不要直接给代码，而是说明大致思路、在哪创建哪些文件、每个文件里按什么思路填写代码。本次已更新 `AGENTS.md`。

### 涉及文件

- `AGENTS.md`：新增核心后端任务的回答方式约束。
- `study.md`：记录本次协作规则调整。

### 规则含义

以后用户询问“下一步”“怎么写”“大致思路”时，如果任务属于 API 路由、服务端业务逻辑、认证/权限模型等核心后端实现，AI 助手默认只说明：

- 需要创建或修改哪些文件。
- 每个文件的职责是什么。
- 文件内部按什么顺序组织内容。
- 关键对象之间的数据怎么流转。
- 如何验证是否写对。
- 哪些地方容易出错。

除非用户明确说“给代码”“帮我写代码”“直接改文件”，否则不直接输出完整代码。

### 下一步

后续 M3 索引任务 API 的指导应按这个规则执行：先说明 `routes`、`schemas`、`services`、`models` 的文件分工和填写思路，由用户完成核心代码后，AI 再代办迁移、联调和验证。

## 2026-06-06：将后端 schema/DTO 移出用户核心任务

### 当前目标

用户说明 schema 没有头绪，不希望以后亲自写。已更新 `AGENTS.md`：后端 Pydantic schema、请求/响应结构类、DTO 和接口字段整理不属于用户当前亲自完成的核心范围，默认由 AI 助手代为编写和维护。

### 涉及文件

- `AGENTS.md`：调整职责划分和后端协助方式。
- `study.md`：记录本次协作规则变化。

### 规则含义

以后推进后端任务时：

- 用户继续负责 API 路由、服务端业务逻辑、认证/权限模型、数据库表业务含义和关键技术判断。
- AI 助手默认负责 schema/DTO，包括字段来源梳理、Pydantic 类、响应结构和必要的字段校验。
- 如果用户问核心实现怎么写，AI 仍默认只给文件组织和填写思路，不直接给完整核心代码。
- 如果只是 schema/DTO，AI 可以直接创建或修改文件。

### 下一步

M3 索引任务中，`backend/app/schemas/document_index.py` 后续由 AI 助手直接编写；用户只需要关注路由入口和服务端状态流转逻辑。

## 2026-06-06：补齐 M3 索引任务响应 schema

### 当前目标

根据新的协作规则，后端 schema/DTO 默认由 AI 助手编写。本次删除拼写错误的空文件 `backend/app/schemas/documen_index.py`，新增正确文件 `backend/app/schemas/document_index.py`。

### 涉及文件

- `backend/app/schemas/document_index.py`：定义 `DocumentIndexJobResponse`。
- `study.md`：记录本次 schema 整理。

### 关键点

`DocumentIndexJobResponse` 描述索引任务接口返回给前端的数据结构，字段包括：

- `id`：索引任务 ID。
- `page_id`：任务所属 Wiki 页面。
- `attachment_id`：任务处理的附件。
- `status`：`pending`、`processing`、`ready`、`failed`。
- `chunk_count`：成功写入向量库的片段数量。
- `error_message`：失败原因，成功时为空。
- `started_at`、`finished_at`：任务开始和结束时间。
- `created_at`、`updated_at`：任务记录创建和更新时间。

### 下一步

用户继续完成核心后端部分：`backend/app/api/routes/wiki_index.py` 和 `backend/app/services/document_index.py` 的路由入口与状态流转思路。AI 后续再补模型、迁移、注册、运行和接口验证。

## 2026-06-16：纠正 LLM Wiki 项目方向

### 当前目标

根据桌面文件 `llmwiki修正.md` 纠正项目方向：OpsMind 不再按传统 RAG 路线推进，而是统一为 LLM Wiki / Knowledge Compilation 知识编译路线。

### 涉及文件

- `README.md`：重写项目定位、核心能力和计划架构。
- `docs/project-design.md`：重写项目目标、功能范围、技术架构、核心流程和路线图。
- `docs/module-plan.md`：将 M3 之后的模块从“文档解析、索引、检索、RAG 问答”调整为“知识编译、页面关系、Wiki 搜索、基于 Wiki 的问答”。
- `docs/m3-knowledge-compilation-design.md`：替换旧的 M3 索引设计，明确资料解析、知识单元提取、Wiki 页面生成、页面关系和知识修订流程。
- `AGENTS.md`：把协作边界中的 Agent/RAG 核心实现调整为 LLM Wiki 知识编译核心实现。

### 关键纠正

旧方向：

```text
文档 -> Chunk -> Embedding -> ChromaDB -> Top-K 检索 -> LLM 回答
```

新方向：

```text
原始资料 -> LLM 理解 -> 知识提炼 -> Wiki 页面生成/更新 -> 页面关系 -> 知识修订
```

查询时优先：

```text
用户问题 -> 定位相关 Wiki 页面 -> 基于 Wiki 页面和页面关系回答
```

而不是：

```text
用户问题 -> 检索原始 chunk -> 拼接上下文 -> LLM 回答
```

### 后续原则

- Wiki 是经过 LLM 整理后的知识层，不是原始文档切片集合。
- 搜索能力服务于 Wiki 页面定位，不再把原始 chunk 检索作为项目主体。
- ChromaDB、Embedding 和语义搜索可以作为 Wiki 页面搜索的辅助能力，但不再是 M3 主线。
- 后续命名优先使用 `knowledge_compilation`、`knowledge_unit`、`wiki_page_relationship`、`knowledge_revision` 等概念。
- 旧的 `document_index`、`wiki_index`、`chunk` 等命名如果已经出现在代码或 schema 中，后续应按实际改造节奏逐步迁移，避免继续扩散。
