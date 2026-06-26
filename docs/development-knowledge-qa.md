# OpsMind 开发知识点问答

本文档把 OpsMind 实际开发过程中的可复用知识整理成面试式问答。回答优先结合项目代码，不把尚未使用的技术描述成项目经验。

当前内容已同步至 M8 Knowledge Agent 工具编排阶段；后续开发任务按 `AGENTS.md` 规则持续增量更新。

## M8 Knowledge Agent 编排

### 前端如何接入基于 Wiki 的可追溯问答？

前端通过 `POST /api/v1/wiki/questions` 提交问题和可选的 `page_ids`，后端返回答案、引用 Wiki 页面和模型元数据。OpsMind 在 `frontend/src/api/wiki.ts` 中定义 `WikiAnswerResponse`、`WikiQuestionCitation` 和 `askWikiQuestion`，页面层只处理表单状态、加载状态、引用跳转和错误提示。

这种拆分让问答页面不直接拼接后端 URL 或解析响应细节。常见风险是前端只展示答案而忽略引用来源；项目中把 `citations` 渲染为可点击页面，用户可以从回答跳回具体 Wiki 页面核对依据。

### OpsMind 的首期 ReAct Agent 为什么没有直接使用 LangChain Agent？

当前统一 `LLMProvider` 只提供标准文本生成接口，OpenAI 兼容实现也没有暴露原生 `tool_calls`。仓库仅安装了 `langchain-text-splitters`，没有完整 LangChain Agent 依赖。

首期因此使用受约束 JSON 决策协议：模型每轮只能返回一个 `tool_call` 或 `final` 对象。编排器解析并校验决策后，通过现有 `ToolRegistry` 和 `execute_tool` 执行工具。这先验证了工具选择、观察反馈、事务审计和终止边界，同时避免为了一个循环立即扩大依赖和抽象层。

这种实现不是自由文本的“Thought/Action/Observation”解析器，也不会保存或展示模型隐藏推理。后续接入支持原生函数调用的 Provider 或 LangChain 时，可以替换决策适配层，保留现有工具、权限和审计实现。

### Knowledge Agent 如何限制写工具和无限循环？

Agent 默认只暴露 `source_parse`、`knowledge_extraction` 和 `wiki_search` 三个只读工具。调用方必须在本次运行中按工具名显式传入 `allowed_write_tools`，才能开放 `wiki_page_update` 或 `page_relationship`；模型不能通过输出参数自行提高权限。写工具内部仍会再次校验操作者和业务权限。

编排器限制最多 1 至 10 轮，默认 5 轮，并记录已经执行的“工具名 + 规范化参数”。完全相同的调用再次出现时立即以 `repeated_tool_call` 停止；达到轮数仍未返回最终答案时以 `step_limit_exceeded` 停止。

工具结果会被序列化并限制长度，系统提示明确把结果标记为不可信数据。工具失败时只向模型反馈工具名和稳定错误码，不传递异常堆栈。每次真实工具调用仍由统一执行器写入成功或失败审计。

### Knowledge Agent API 为什么只做边界编排？

`POST /api/v1/knowledge-agent/runs` 只负责认证当前用户、构造 `LLMProvider`、传入 `ToolContext`、校验本次开放的写工具和映射错误码。真正的工具选择循环仍在 `run_knowledge_agent` 中，真实工具调用仍统一走 `execute_tool`。

这样 API 层不会复制工具权限、事务审计和结果摘要逻辑。调用者可以通过 `max_steps` 和 `max_observation_chars` 控制单次运行边界，但不能绕过工具注册表，也不能开放未列入白名单的写工具。常见排查方式是先看接口返回的稳定错误码，再查 `tool_invocations` 表中的每次工具调用记录。

## M8 Wiki 搜索工具

### Wiki Search Tool 为什么返回摘要而不是完整页面正文？

工具的职责是定位候选 Wiki 页面，而不是直接构建最终问答上下文。返回完整正文会快速占用 Agent 上下文，并可能让一次宽泛搜索读取大量不必要内容。

OpsMind 的搜索结果只包含页面 ID、标题、Slug、页面类型、状态、限长摘要、标签和受限数量的直接关系。Agent 确认候选页面后，再由专门的上下文构建流程按页面和字符预算读取正文。工具调用审计只保存结果数量、页面 ID 和类型分布，不保存摘要或正文。

### SQL `LIKE` 搜索为什么要转义 `%` 和 `_`？

在 SQL `LIKE` 表达式中，`%` 表示任意长度字符，`_` 表示任意单个字符。如果直接把用户或模型输入拼入模式，查询 `%` 会匹配几乎所有页面，绕过关键词搜索的预期边界。

Wiki Search Tool 会转义反斜杠、`%` 和 `_`，再使用显式 `escape` 字符执行 `ILIKE`。因此这些符号按普通文本匹配。查询仍通过 SQLAlchemy 参数绑定发送到数据库，不使用字符串拼接 SQL。

## M8 页面关系工具

### 有向关系和对称关系在存储与去重上有什么区别？

`depends_on`、`belongs_to`、`caused_by` 等关系具有方向，`A depends_on B` 与 `B depends_on A` 表达不同含义，因此数据库按输入方向保存。

`related_to` 和 `similar_to` 在 OpsMind 中按对称关系处理。Page Relationship Tool 会将两个页面 ID 排序后再保存，并在创建前同时检查正向和反向记录。这样可以避免同时出现 `A similar_to B` 和 `B similar_to A` 两条语义重复的数据。

数据库唯一约束只能限制完全相同的 `source_page_id + target_page_id + relation_type`，无法独立阻止反向重复，因此对称关系仍需要应用层规范化。

### 为什么 Page Relationship Tool 要求关系必须关联知识单元的来源页或生成页？

工具参数包含 `knowledge_unit_id`，并且只接受状态为 `applied` 的知识单元。创建的关系会记录该单元所属的 `source_job_id`，形成“页面关系 -> 编译任务 -> 知识单元 -> 来源附件”的追溯链路。

仅记录任务 ID 仍不足以证明关系与候选知识有关，因此工具还要求关系至少一端是知识单元的 `source_page_id` 或 `created_page_id`。这可以阻止模型借用一个无关知识单元，为任意两个页面创建看似可追溯、实际没有来源依据的关系。

## M8 受控 Wiki 写入工具

### Wiki Page Update Tool 为什么只接收 `knowledge_unit_id`，不直接接收页面正文？

`knowledge_unit_id` 指向数据库中已经持久化的候选知识单元。该记录同时关联来源附件、知识编译任务、来源位置和置信度，因此工具可以沿固定链路追溯每次页面写入的知识来源。

如果允许 LLM 在工具参数中直接传入任意正文，内容可能绕过知识提取和审核链路，工具审计也只能证明“写入了什么”，无法证明“内容来自哪里”。OpsMind 因此把工具参数限制为候选单元 ID、明确动作和必要的目标信息。

工具还要求显式选择 `create`、`update` 或 `skip`；更新时必须进一步选择 `append` 或 `replace`。这能避免模型根据模糊参数静默覆盖已有 Wiki 页面。

### 受控写工具如何同时保证权限、版本记录和事务一致性？

`WikiPageUpdateTool` 使用 `ToolContext.actor_user_id` 加载操作者。超级管理员可直接执行；普通用户必须通过用户、角色和权限关联表拥有 `wiki:create` 或 `wiki:update` 权限。

创建或更新页面时，工具会在同一 SQLAlchemy Session 中：

1. 写入 Wiki 页面内容。
2. 创建递增版本号的 `WikiVersion`。
3. 更新 `KnowledgeUnit.apply_status` 和目标页面 ID。
4. 更新编译任务的创建或更新页面计数。
5. 由统一工具执行器写入不包含正文的 `ToolInvocation` 摘要。

工具本身不提交事务，由统一执行器在业务写入和工具调用记录都成功后统一 `commit`。发生校验、权限或数据库错误时，执行器先 `rollback`，再单独记录失败调用，从而避免页面只更新了一半或成功审计与实际数据不一致。

## Python 基础与异步

### 1. Python 装饰器有什么作用？项目中哪里使用了装饰器？

装饰器用于在不修改函数主体的情况下，为函数增加注册、校验、日志、权限等行为。

```python
@decorator
def function():
    pass
```

本质上近似于：

```python
def function():
    pass

function = decorator(function)
```

OpsMind 中常见的装饰器包括：

- `@router.get(...)`、`@router.post(...)`：把函数注册为 FastAPI 路由。
- `@field_validator("question")`：注册 Pydantic 字段校验函数。
- `@dataclass(...)`：让普通类自动获得初始化、比较等数据类能力。
- `@property`：把方法包装成只读属性，例如通过 `usage.total_tokens` 读取 Token 总数。

装饰器的风险是调用链可能变得不直观。自定义装饰器一般应使用 `functools.wraps` 保留原函数名称和文档信息。

### 2. 简单说明 `async`/`await` 的原理。

`async def` 定义协程函数，调用后产生协程对象。事件循环负责调度协程；当代码执行到 `await` 并等待网络、数据库等 I/O 时，会暂时让出执行权，让事件循环处理其他请求。

```python
async def load_data():
    result = await remote_request()
    return result
```

异步的优势主要来自 I/O 等待期间能够处理其他任务，并不意味着 Python 会自动并行执行 CPU 密集计算。CPU 密集任务应考虑进程池、任务队列或独立 Worker。

如果在 `async def` 中直接调用阻塞式数据库驱动、`time.sleep()` 或同步 HTTP 请求，仍然会阻塞事件循环。

### 3. FastAPI 为什么天然支持异步？

FastAPI 建立在 ASGI 规范和 Starlette 之上，通常由 Uvicorn 运行。ASGI 能以事件循环处理并发连接，因此路由可以直接定义为 `async def`。

FastAPI 同时支持：

- `async def` 路由：由事件循环直接执行，适合异步 I/O。
- 普通 `def` 路由：FastAPI 会在线程池中执行，避免同步函数直接阻塞事件循环。

OpsMind 当前 SQLAlchemy 会话和多数服务是同步实现，因此路由主要使用普通 `def`。不能为了形式统一盲目改成 `async def`；只有数据库驱动、HTTP 客户端和完整调用链都支持异步时，异步才能真正发挥作用。

## FastAPI 项目实践

### 4. 你用过哪款 Python Web 框架？讲一下项目里的完整请求流程。

OpsMind 使用 FastAPI，主要原因是类型提示、Pydantic 校验、依赖注入和 OpenAPI 文档支持适合前后端分离 API。

以 Wiki 问答接口为例，完整流程是：

1. `backend/app/api/routes/wiki_qa.py` 创建 `APIRouter`，使用 `@router.post("/questions")` 注册处理函数。
2. `backend/app/main.py` 导入该 Router，并通过 `app.include_router(...)` 注册到 FastAPI 应用。
3. Uvicorn 接收 HTTP 请求并通过 ASGI 交给 FastAPI。
4. FastAPI 根据请求方法和路径匹配 `APIRoute`。
5. `Depends(get_current_user)` 校验 Bearer Token，`Depends(get_db)` 创建数据库会话。
6. Pydantic 把 JSON 请求体解析为 `WikiQuestionRequest`，并执行类型、长度和自定义校验。
7. 路由调用 `answer_wiki_question(...)`，服务层构建 Wiki 上下文并调用 LLM Provider。
8. 服务返回 `WikiAnswerResponse`。
9. FastAPI 根据 `response_model` 校验并序列化响应，最终返回 JSON。

这条链路可以概括为：

```text
HTTP 请求 -> 路由匹配 -> 依赖注入 -> 参数校验 -> 服务逻辑
          -> 响应模型校验 -> JSON 响应
```

### 5. FastAPI 如何接收路径参数、查询参数和请求体？

路径参数写在路由路径中，并通过同名函数参数接收：

```python
@router.get("/pages/{page_id}")
def get_page(page_id: int):
    ...
```

请求 `/pages/10` 时，`page_id` 会被转换并校验为整数。

查询参数是不属于路径的普通参数，可使用 `Query` 增加约束：

```python
@router.get("/pages")
def list_pages(keyword: str | None = Query(default=None, max_length=100)):
    ...
```

对应请求为 `/pages?keyword=redis`。

请求体通常定义为 Pydantic 模型：

```python
class WikiQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    page_ids: list[int] = Field(default_factory=list, max_length=20)


@router.post("/questions")
def ask(payload: WikiQuestionRequest):
    ...
```

此外，OpsMind 文件上传接口使用 `UploadFile` 和 `File(...)` 接收 `multipart/form-data` 文件。

### 6. FastAPI 如何做参数校验？校验失败返回什么？

FastAPI 主要通过 Python 类型提示和 Pydantic 完成参数校验：

- `int`、`str`、`datetime` 等类型负责基础转换和校验。
- `Field(...)` 校验请求体字段长度、范围和默认值。
- `Query(...)`、`Path(...)` 校验查询参数和路径参数。
- `field_validator` 实现空白字符、字段规范化等自定义规则。
- `response_model` 校验并过滤响应字段。

例如 Wiki 问题不能只包含空格：

```python
@field_validator("question")
@classmethod
def normalize_question(cls, value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("question cannot be blank")
    return normalized
```

请求参数校验失败通常返回 `422 Unprocessable Entity`，响应中会包含字段位置和失败原因。

### 7. 前后端联调出现跨域问题怎么处理？CORS 核心参数是什么？

跨域是浏览器的同源策略限制。当协议、域名或端口任意一项不同时，前端请求可能需要后端明确允许。

FastAPI 通常使用 `CORSMiddleware`：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

核心参数：

- `allow_origins`：允许访问后端的前端来源，应优先写明确地址。
- `allow_credentials`：是否允许 Cookie、Authorization 等凭据。
- `allow_methods`：允许的 HTTP 方法。
- `allow_headers`：允许前端发送的请求头。
- `expose_headers`：允许浏览器端 JavaScript 读取的响应头。
- `max_age`：预检请求结果的缓存时间。

OpsMind 当前本地开发使用 Vite 代理，把前端的 `/api` 请求转发到 `http://127.0.0.1:8010`，因此浏览器视角保持同源，后端暂未添加 `CORSMiddleware`。如果以后前后端改为不同域名部署，再按明确来源配置 CORS。生产环境不应随意使用全开放来源，尤其是携带凭据时。

## ORM 与数据库

### 8. Django ORM 常用的增删改查怎么写？如何避免 N+1？

OpsMind 实际使用 SQLAlchemy，不使用 Django ORM。以下是常见 Django ORM 面试知识：

```python
# 增
User.objects.create(username="alice")

# 查
user = User.objects.get(id=1)
users = User.objects.filter(is_active=True)

# 改
User.objects.filter(id=1).update(username="bob")

# 删
User.objects.filter(id=1).delete()
```

N+1 指先查询一批主对象，然后循环访问关联对象时，每条记录又触发一次查询。例如查询 100 篇文章后逐篇读取作者，可能产生 101 次 SQL。

常用解决方法：

- `select_related(...)`：通过 SQL JOIN 加载外键或一对一关系。
- `prefetch_related(...)`：额外执行批量查询，再由 Django 合并多对多或反向关系。
- 使用 Django Debug Toolbar、SQL 日志或查询计数测试识别重复查询。

在 OpsMind 的 SQLAlchemy 中，对应思路是使用 `joinedload`、`selectinload` 或明确 JOIN，而不是在循环中逐条查询关系。

## 接口联调与开发流程

### 9. 前端请求返回 400、401、404、500，分别说明什么？

| 状态码 | 含义 | 常见后端问题 |
| --- | --- | --- |
| `400` | 请求格式合法，但业务语义错误 | 文件类型不支持、参数组合冲突、自关联等 |
| `401` | 未认证或认证凭据无效 | Token 缺失、过期、签名错误、用户被禁用 |
| `404` | 路由或业务资源不存在 | URL 写错、Router 未注册、页面 ID 不存在或已删除 |
| `500` | 后端未处理异常 | 空值错误、数据库异常、配置缺失、第三方服务异常未转换 |

相关状态码还包括：

- `403`：身份有效但权限不足。
- `409`：资源状态冲突，例如 slug 重复。
- `422`：FastAPI/Pydantic 请求参数校验失败。
- `502`：后端作为上游客户端时，上游服务调用失败；OpsMind 的 LLM Provider 异常会映射为该状态码。

排查时应同时查看浏览器 Network 中的请求 URL、请求体、响应体，以及后端日志，不能只看状态码。

### 10. 简单描述一次完整的接口开发流程。

1. **需求梳理**：明确调用者、使用场景、权限、输入、输出、错误码和完成标准。
2. **数据设计**：确认是否需要新表、字段、索引、唯一约束和关联关系；涉及数据库变更时编写迁移。
3. **Schema/DTO**：定义请求体、响应体和字段校验，避免路由直接处理无结构字典。
4. **服务实现**：编写业务逻辑，划分事务边界，处理外部服务错误，避免把复杂逻辑全部堆在路由中。
5. **路由实现**：注册 URL 和 HTTP 方法，接收参数，注入数据库与当前用户，调用服务并映射异常。
6. **注册路由**：在 FastAPI 应用中通过 `include_router` 注册，确认最终路径正确。
7. **自测**：覆盖正常结果、参数错误、未登录、无权限、资源不存在、冲突和外部服务失败。
8. **本地联调**：启动依赖服务，使用真实请求验证数据库、认证、前端代理和响应结构。
9. **前端联调**：核对 URL、方法、字段名称、Token、CORS、错误提示和加载状态。
10. **回归与记录**：运行全量测试，更新接口文档和开发知识问答，再按职责拆分 Git 提交。

OpsMind 的 Wiki 问答接口就是按此过程完成：先定义 Provider 和上下文服务，再编排问答、增加 DTO、接入受保护路由，最后执行针对性测试和全量后端测试。

## 数据建模实践

### 11. Pydantic 已经校验了状态值，为什么数据库还需要 `CheckConstraint`？

Pydantic 只能保护经过当前 API Schema 的输入，数据还可能来自迁移脚本、后台任务、管理工具、其他服务或直接 SQL。如果数据库没有约束，这些入口仍可能写入非法状态。

OpsMind 的故障案例把严重级别限制为 `low`、`medium`、`high`、`critical`，处理状态限制为 `open`、`investigating`、`resolved`、`closed`：

- Pydantic 的 `Literal` 在接口入口快速返回清晰的 `422` 错误。
- 数据库 `CheckConstraint` 作为最后防线，拒绝绕过接口的非法值。

双重校验不是简单重复，而是分别保护应用边界和数据边界。修改合法状态集合时，Schema、模型约束和迁移必须同步更新。

### 12. 故障案例为什么使用软删除，并与生成的 Wiki 页面分开保存？

故障案例保存原始事实，包括现象、原因、排查过程、修复方案和复盘结论；Wiki 页面是对案例进行知识化整理后的可复用知识。两者生命周期和用途不同，不应使用同一条记录替代。

OpsMind 使用可空的 `wiki_page_id` 关联知识化后的页面：

- 创建案例时可以尚未生成 Wiki 页面。
- 知识化成功后再写入页面 ID。
- Wiki 页面删除时通过 `SET NULL` 保留原始故障案例。

案例使用 `deleted_at` 软删除，是为了保留审计和复盘依据。正常查询应统一过滤 `deleted_at IS NULL`，否则已删除案例仍可能出现在列表和 AI 上下文中。

## 认证、权限与审计

### 13. OpsMind 的 JWT 登录和身份校验流程是什么？

用户调用 `/api/v1/auth/login` 提交用户名和密码。后端先按用户名查询用户，再用 bcrypt 校验密码哈希；成功后把用户 ID 写入 JWT 的 `sub`，把过期时间写入 `exp`，使用 `SECRET_KEY` 和指定算法签名。

后续请求通过 `Authorization: Bearer <token>` 携带 JWT。`OAuth2PasswordBearer` 提取 Token，`decode_access_token` 校验签名和过期时间，`get_current_user` 再根据 `sub` 查询用户并检查 `is_active`。

JWT 只证明 Token 由可信后端签发，不适合保存密码、密钥等敏感信息。当前实现每次请求仍查询用户，因此禁用用户后旧 Token 也会立即失效。

### 14. 项目为什么使用 bcrypt，而不是保存可逆加密密码？

密码应使用单向哈希，数据库泄露时攻击者不能直接还原明文。bcrypt 会自动加入随机盐，并通过计算成本提高暴力破解难度。

OpsMind 使用 `bcrypt.hashpw` 生成哈希，使用 `bcrypt.checkpw` 校验。bcrypt 只处理前 72 字节，因此项目在哈希前检查 UTF-8 字节长度，过长密码直接拒绝，避免用户以为完整密码都参与了计算。

生产环境还应配合登录限流、弱密码策略、密钥轮换和 HTTPS。

### 15. FastAPI 的 `Depends` 在 OpsMind 中如何实现认证和 RBAC？

`Depends` 是 FastAPI 的依赖注入机制。OpsMind 将公共逻辑拆成多层依赖：

- `get_db`：为一次请求创建并最终关闭 SQLAlchemy Session。
- `get_current_user`：解析 Token、查询用户并验证状态。
- `get_current_superuser`：在当前用户基础上检查超级管理员标志。
- `require_permission("wiki:update")`：汇总用户角色拥有的权限码并判断是否允许操作。

路由只需声明依赖，不需要重复认证代码。超级管理员会绕过普通权限码检查。Token 无效返回 `401`；身份有效但没有权限返回 `403`。

### 16. 审计日志应该记录什么？为什么通常和业务数据一起提交？

OpsMind 的审计日志记录操作者、动作、资源类型、资源 ID、IP、User-Agent、结果和必要详情。例如创建 Wiki 页面会记录 `wiki.page.create`，知识单元审核会记录具体动作和目标页面。

路由通常先 `db.add` 业务对象和审计日志，再统一 `db.commit()`。这样业务操作和审计记录处于同一事务：业务提交失败时，不会留下“操作成功”的错误审计。

登录失败是特殊情况，没有成功业务数据，但失败记录仍需单独提交。审计详情不能保存密码、Token、API Key 或大段敏感正文。

## SQLAlchemy 与数据库迁移

### 17. SQLAlchemy 2.x 在项目中的常见增删改查怎么写？

OpsMind 使用 SQLAlchemy 2.x 风格：

```python
# 增
page = WikiPage(title="Redis", slug="redis", content="...")
db.add(page)
db.commit()

# 查一条
page = db.scalar(select(WikiPage).where(WikiPage.id == page_id))

# 查多条
pages = db.scalars(select(WikiPage).order_by(WikiPage.updated_at.desc())).all()

# 改
page.title = "Redis 运维"
db.commit()

# 删
db.delete(relationship)
db.commit()
```

Wiki 页面使用软删除，所以删除页面不是 `db.delete(page)`，而是设置 `deleted_at`。

### 18. `flush`、`commit`、`refresh` 分别有什么作用？

- `flush`：把当前 Session 的变更发送给数据库，但不结束事务。常用于先获得自增 ID，再创建版本或审计记录。
- `commit`：提交事务，使修改正式生效；失败时应回滚。
- `refresh`：提交后重新查询当前对象，获得数据库生成的时间、默认值等字段。

OpsMind 创建 Wiki 页面时先 `flush` 获得页面 ID，然后创建版本和审计日志，最后统一 `commit`，再 `refresh` 后返回响应。

### 19. SQLAlchemy 模型和 Alembic 迁移分别解决什么问题？

SQLAlchemy 模型描述应用运行时如何映射数据库表；Alembic 迁移描述已有数据库如何从一个版本升级到另一个版本。只改模型不会自动改变已经存在的 PostgreSQL 表。

OpsMind 的每个迁移通过 `revision` 和 `down_revision` 形成链。新增迁移后应先执行 `alembic heads`，确认只有一个 Head，再审查升级和降级逻辑。当前故障案例迁移已经生成，但尚未执行到本地数据库，因此不能把“迁移文件存在”表述为“表已部署”。

### 20. 外键的 `CASCADE` 和 `SET NULL` 应该如何选择？

当子记录脱离父记录后没有独立意义时使用 `CASCADE`。例如 Wiki 页面删除后，其附件和版本通常随之删除。

当子记录仍有审计或历史价值时使用 `SET NULL`。例如用户删除后，Wiki 页面和审计记录仍应保留，只清空用户引用；故障案例关联的 Wiki 页面删除后，原始案例也应保留。

选择依据是业务生命周期，不是为了省代码。数据库外键行为还要与 ORM 关系和软删除策略保持一致。

## Wiki、附件与知识组织

### 21. 文件上传接口需要做哪些安全校验？OpsMind 当前做了什么？

OpsMind 使用 `UploadFile` 接收 `multipart/form-data`，当前会：

- 使用 `Path(...).name` 去除客户端路径部分。
- 同时检查扩展名和 MIME 类型白名单。
- 拒绝空文件和超过配置上限的文件，过大返回 `413`。
- 使用 UUID 生成存储文件名，避免同名覆盖。
- 按页面 ID 分目录保存，并在数据库记录原文件名、类型、大小和存储路径。

扩展名和 MIME 都可以伪造，因此生产环境还应增加文件签名检测、恶意文件扫描、存储目录隔离和下载响应头控制。数据库写入失败时还需要清理已落盘的孤立文件，这是当前实现可继续改进的地方。

### 22. Wiki 页面为什么需要版本表和软删除？

页面正文会持续更新，版本表用于保留每次修改时的标题、正文、版本号和修改用户，支持追溯与后续对比。OpsMind 创建和更新页面时都会生成 `WikiVersion`。

页面删除使用 `deleted_at`，列表、详情、搜索和问答上下文统一排除已删除页面。这样既避免用户继续看到旧内容，也保留审计和恢复空间。

软删除的难点是每个查询都必须遵守过滤规则，必要时应封装统一查询方法，避免漏过滤。

### 23. Wiki 页面关系如何建模？如何防止重复和自关联？

页面关系使用独立表保存 `source_page_id`、`target_page_id`、`relation_type` 和说明，支持 `depends_on`、`caused_by`、`resolved_by` 等方向性关系。

项目使用两层保护：

- API 在写入前检查来源页和目标页不能相同，并查询是否已有相同关系。
- 数据库使用 `CheckConstraint` 禁止自关联，使用三字段唯一约束禁止重复关系。

关系还保存 `source_type` 和 `source_job_id`，用于区分人工创建与知识编译生成。查询接口支持 incoming、outgoing 和 both 三种方向。

## LLM Wiki 知识编译

### 24. OpsMind 为什么从传统 RAG 调整为 LLM Wiki？

传统 RAG 常直接检索原始文档 chunk，并把片段拼接给模型。OpsMind 的主线改为先把资料整理成可维护的 Wiki 页面，再基于页面、版本和页面关系回答。

核心区别是知识层：

```text
原始附件 -> 解析 -> 候选知识单元 -> 审核/合并 -> Wiki 页面与关系
```

查询时优先定位 Wiki 页面，而不是直接把原始 chunk 当最终知识。ChromaDB 和语义搜索仍可作为页面定位的辅助能力，但不再是知识主体。

### 25. 当前知识编译任务的状态如何流转？是同步还是异步？

当前接口收到编译请求后同步执行：创建任务时直接进入 `parsing`，解析成功后进入 `extracting`，提取结束变为 `ready`，异常则变为 `failed`，并记录错误和结束时间。

虽然模块规划中还有 `pending`、`compiling` 等完整状态，但当前代码尚未引入消息队列和 Worker，也尚未实现自动生成或合并 Wiki 页面。因此面试时应说明这是同步最小闭环，后续才会扩展为异步任务。

### 26. 原始资料解析如何保证来源可追溯？目前支持哪些格式？

解析器把文档转换成 `SourceDocument` 和多个 `SourceSection`。每个 Section 保存字符范围、段落范围、标题和 `source_location`，候选知识单元继续保存该来源位置。

Markdown 按一至三级标题分段，并避免把代码块里的 `#` 误判为标题；TXT 按段落解析。文件使用 `utf-8-sig` 读取，可兼容 UTF-8 BOM。

当前知识编译解析器只支持 `.md` 和 `.txt`。上传接口虽然允许 PDF、DOCX，但它们执行知识编译时会进入失败状态；这两种解析器仍属于待实现能力。

### 27. 当前候选知识单元是如何提取和分类的？

当前版本采用确定性规则打通最小闭环，并未调用 LLM：

- 过滤少于 30 字符的短 Section。
- 过滤日志行比例过高的内容。
- 根据标题和正文关键词分类为概念、系统、流程、规则、术语、事件或故障。
- 根据标题、关键词数量和正文长度计算最高 0.9 的启发式置信度。
- 使用标题和类型去重，并生成摘要和标准化 Markdown 正文。

优点是离线可测试、成本低、结果稳定；缺点是语义理解和合并判断有限。后续接入 LLM 时仍应保留来源位置、置信度和人工审核，而不是直接覆盖 Wiki。

## LLM Provider 与可追溯问答

### 28. 为什么要设计统一的 LLM Provider？

业务层只依赖 `LLMProvider.generate(messages, temperature, max_tokens)`，并接收统一的 `LLMResult`。Provider 负责把内部消息转换为具体模型服务请求，并统一返回内容、模型、Token、耗时和结束原因。

当前有两个实现：

- `FakeLLMProvider`：离线、确定性，用于测试编排。
- `OpenAICompatibleLLMProvider`：调用兼容 `/chat/completions` 的 HTTP 服务。

因此切换 Provider 主要修改环境配置，不需要修改 Wiki 问答业务。Python 的 `Protocol` 用结构化类型约束实现，只要对象提供约定属性和方法即可注入。

### 29. OpenAI 兼容 Provider 如何处理网络错误和不规范响应？

Provider 使用标准库 `urllib` 发送非流式 JSON 请求，支持可选 Bearer API Key 和请求超时。它会校验基础 URL、温度、输出上限以及响应中的 choice、message、content、usage 和 finish reason。

HTTP 错误、连接错误、超时、非法 JSON 和空内容都会转换为 `LLMProviderError`，上层再映射为统一的 `502`，不会向客户端暴露 API Key、上游响应正文或内部异常。

当前没有自动重试，避免重复计费。后续如增加重试，应只针对有限的 429、502、503 等暂时性错误，并设置次数、退避和幂等边界。

### 30. Wiki 问答上下文是如何选择和控制大小的？

用户可以显式传入页面 ID；否则上下文构建器从问题提取中英文关键词，在已发布且未删除的 Wiki 页面标题和正文中匹配并计算相关度。

选中直接页面后，再沿页面关系扩展一层相关页面，并批量加载最新版本号。默认最多 5 页、上下文最多 12000 字符，超过预算会截断并标记，防止提示词无限增长。

当前是数据库关键词匹配和关系扩展，不是 ChromaDB 语义检索。后续增加语义搜索时可以替换“定位页面”步骤，但回答上下文仍应来自 Wiki 页面。

### 31. 项目如何降低模型幻觉、提示注入和伪造引用风险？

系统提示要求模型只能使用提供的 Wiki 内容，知识不足时必须明确说明；上下文前言声明 Wiki 正文只是事实资料，不是模型指令，以降低正文中的提示注入风险。

如果没有匹配页面，服务不会调用模型，而是直接返回知识不足。模型引用采用 `[Wiki:页面ID]`，服务会检查引用 ID 是否属于当前上下文，越界引用直接判为失败。响应还返回结构化页面标题和 slug。

这不是绝对安全：当前只拒绝越界引用，没有强制每个事实都带引用，也不能证明引用内容真正支持结论。更严格的实现可以要求结构化输出，并逐条校验声明与来源。

## 测试、前端联调与基础设施

### 32. 如何在不调用真实模型和外部网络的情况下测试 LLM 功能？

OpsMind 通过依赖注入和 Fake 实现隔离外部服务：问答函数允许传入自定义 Provider；Provider HTTP 测试用内存假响应替换 `urlopen`；上下文测试使用 SQLite 内存数据库构造页面、版本和关系。

测试覆盖正常回答、知识不足、Provider 失败、空回答、越界引用、请求结构和 Token 元数据。这样测试快速、稳定、无费用，也不会泄露真实密钥。

单元测试通过不等于真实模型兼容性已经验证，发布前仍需在受控环境做一次真实 Provider 联调。

### 33. Docker Compose 在本地开发环境中解决什么问题？

OpsMind 使用 Compose 统一启动 PostgreSQL、Redis 和 ChromaDB，并通过环境变量配置端口和数据库账号。命名卷保存数据，容器重启后数据不会因容器删除而自动消失。

Compose 解决依赖服务版本和启动方式一致的问题，但不会自动运行后端迁移、种子数据或应用服务。执行删除卷等操作会丢失数据，因此不属于普通启动命令。

### 34. 前端开发代理如何解决接口联调问题？

Vite 开发服务器监听 5173 端口，并把 `/api` 请求代理到后端 8010 端口。前端代码可以请求相对路径，浏览器看到的仍是同一来源，因此本地开发通常不会触发 CORS。

代理只在 Vite 开发服务器中生效。生产部署需要由 Nginx 等网关统一代理，或者在后端配置严格的 CORS 来源。认证请求仍需由前端在 `Authorization` 请求头中携带 Bearer Token。

### 35. 故障案例 CRUD 如何处理权限、删除和审计？

OpsMind 为故障案例单独定义 `incident:read`、`incident:create`、`incident:update` 和 `incident:delete` 权限。普通用户默认可以查询、新建和编辑，管理员额外拥有删除权限，避免复用 Wiki 权限导致职责边界模糊。

删除接口只设置 `deleted_at`，列表和详情查询统一排除已删除记录。创建、编辑和删除分别写入审计动作，并记录资源 ID；编辑审计还保存本次修改的字段名，但不复制可能包含敏感故障信息的完整字段值。

接口还会检查解决时间不能早于发生时间，列表支持关键词、系统、严重级别、状态和发生时间范围过滤。软删除查询条件、组合时间校验和权限种子数据是后续新增接口时容易遗漏的检查点。

### 36. 为什么 Wiki 页面需要独立的页面类型字段？

分类和标签适合用户自定义组织内容，页面类型用于表达稳定的知识语义。OpsMind 当前把页面类型限制为 `concept`、`system`、`process`、`rule`、`term`、`event` 和 `incident`，并同时在 Pydantic、SQLAlchemy 和数据库检查约束中校验。

历史页面迁移后默认使用 `concept`，避免新增非空字段破坏已有数据。列表和关键词搜索支持按页面类型过滤，后续页面关系、问答上下文和知识编译可以据此采用不同处理策略。

### 37. 故障案例如何幂等地发布成 Wiki 页面？

首版使用固定 Markdown 模板把基本信息、现象、原因、排查过程、修复方案和复盘结论整理成 `incident` 页面，不调用 LLM。这样输出可测试、可追溯，也不会因模型变化产生不可预测的页面改写。

首次发布使用 `incident-{案例ID}` 作为稳定 Slug，创建页面后把 ID 写回案例的 `wiki_page_id`；再次发布只更新该页面，并新增 `WikiVersion`。页面、版本、案例关联和审计在同一事务中提交，案例行锁用于降低并发重复创建风险。

如果稳定 Slug 已被其他页面占用，或关联页面已删除，接口返回 `409`，不会覆盖不属于该案例的内容。当前模板会整体重建正文，因此人工直接修改生成页可能在下次发布时被覆盖；后续若支持人工与自动内容合并，需要明确字段所有权和冲突处理策略。

### 38. 故障案例如何构建系统、原因、解决方案和相似故障关系？

已发布案例可以确定性生成或复用三类页面，并建立页面关系：故障页通过 `belongs_to` 指向共享系统页，通过 `caused_by` 指向该案例的原因页，通过 `resolved_by` 指向解决流程页。生成页使用稳定 Slug，已有自动关系作为页面归属依据，重复执行只更新变化的页面并新增版本。

相似故障首版不调用向量模型：先要求标准化系统名完全一致，再计算标题与现象字符集合的 Jaccard 相似度，系统匹配占一半分值，综合分达到 `0.62` 才创建 `similar_to`。关系方向按页面 ID 排序，避免 A 到 B 和 B 到 A 各生成一条记录；说明字段保留相似度分数。

这套规则可解释、离线可测试，但字符集合会忽略词序和语义，短文本也可能产生偏高分数。后续可以用 Wiki 页面语义向量替换候选排序，同时保留系统过滤、阈值、人工复核和关系来源记录。

### 39. 前端如何组织故障案例的记录与知识化操作？

前端把故障案例封装成独立 `IncidentWorkspace` 组件，API 请求集中在 `api/incidents.ts`。组件维护列表筛选、当前详情、编辑表单和各操作的加载状态，避免把更多业务继续堆入根 `App.vue`。

用户先保存结构化案例，再显式执行“发布 Wiki”和“构建关系”。界面不会在普通保存时自动触发知识化操作，避免一次编辑意外覆盖生成页面；案例已关联页面时会提示重新发布，并允许跳转到 Wiki 编辑器查看版本和关系。

前端按钮可见性只能改善交互，不能替代后端鉴权。OpsMind 的故障接口仍要求 Bearer Token 和对应权限，无令牌访问返回 `401`，发布和关系构建还同时检查故障编辑及 Wiki 创建、更新权限。

## LLM 工具编排与审计

### 40. OpsMind 如何定义和安全执行 LLM 知识工具？

知识工具统一实现 `KnowledgeTool` 协议，声明工具名、说明、Pydantic 输入模型、执行函数和结果摘要函数。`ToolRegistry` 只注册允许调用的本地知识工具，模型提供的工具名必须在注册表中，像 `shell` 这样的未知工具会被拒绝并记录为 `tool_not_found`。

执行器把一次工具调用作为事务边界：成功时把工具副作用和成功审计一起提交；失败时先回滚工具副作用，再写入失败审计。审计表保存工具名、调用用户、脱敏参数、结果摘要、状态、错误码和耗时，不保存 Source Parse 返回的资料正文。

Source Parse Tool 只接收附件 ID 和输出上限，从数据库加载文件信息。实际路径解析后必须位于 `UPLOAD_STORAGE_DIR`，避免 LLM 或被污染的附件记录读取任意本机文件。输出限制章节数和单节字符数，并保留 `source_location` 与 `truncated`，使后续工具知道结果是否完整。

### 41. Knowledge Extraction Tool 为什么只返回候选结果而不直接写 Wiki？

Knowledge Extraction Tool 接收附件 ID，通过安全解析器取得章节，再复用现有确定性分类器生成候选知识单元。输出包含标题、类型、摘要、受限正文、来源位置、置信度和合并提示，并通过 `max_units`、`max_content_chars` 和 `truncated` 控制上下文规模。

该工具只读，不创建编译任务、知识单元数据库记录或 Wiki 页面。提取和写入分离后，Agent 可以先检查候选结果，再显式调用受控写工具；失败或低质量提取不会直接污染正式知识层。

工具审计只记录候选总数、返回数量、类型分布和截断状态，不记录候选正文。当前提取仍基于关键词和启发式置信度，不应描述为 LLM 语义理解；后续替换提取算法时可以保持相同工具契约。
