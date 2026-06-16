# OpsMind

OpsMind 是面向企业运维团队的 LLM Wiki 知识管理平台。项目目标不是构建传统 RAG 系统，而是利用大语言模型把分散的运维资料持续整理、归纳、融合和维护为结构化 Wiki 知识库，让知识能够沉淀、演化和复用。

> 当前状态：规划与本地开发阶段，项目方向已统一为 LLM Wiki / Knowledge Compilation。

## 核心定位

OpsMind 选择的是：

```text
LLM Wiki = Knowledge Compilation = 知识编译系统
```

而不是：

```text
RAG = Retrieval-Augmented Generation = 检索增强系统
```

原始文档、聊天记录、故障记录和技术资料不是系统最终沉淀的核心资产。系统要长期维护的核心资产是经过 LLM 整理后的结构化 Wiki 页面、页面关系、知识修订记录和可复用的运维知识网络。

## 核心能力

- 管理 Markdown、PDF、DOCX、TXT 等原始资料和附件
- 从原始资料中提炼概念页、系统页、流程页、规则页、术语页、事件页和故障页
- 持续维护 Wiki 页面内容、版本、关系、标签和修订记录
- 基于 Wiki 知识层回答运维问题，并展示关联页面和知识来源
- 沉淀故障现象、原因分析、排查过程、修复方案和复盘结论
- 提供面向 Wiki 页面和知识关系的搜索能力
- 在需要时使用 LLM 工具辅助知识提炼、页面更新、关系发现和问答

## 计划架构

```text
User
  |
Vue 3 Frontend
  |
FastAPI API Gateway
  |
Knowledge Compilation Layer
  |
LLM Provider / Agent Tools
  |
+-- Source Document Parser
+-- Knowledge Extraction
+-- Wiki Page Maintenance
+-- Page Relationship Builder
+-- Wiki Search
```

计划采用 PostgreSQL 存储用户、权限、Wiki 页面、知识关系、修订记录和业务数据；Redis 提供会话缓存、任务状态、热点页面缓存和限流能力。ChromaDB、Embedding 与语义检索可以作为 Wiki 页面搜索的辅助能力，但不再作为项目主体。

## 项目文档

- [项目设计文档](docs/project-design.md)：项目定位、功能范围、架构、开发约定和路线图
- [模块实施计划](docs/module-plan.md)：按照模块列出开发顺序、任务和完成标准
- [M3 LLM Wiki 知识编译设计](docs/m3-knowledge-compilation-design.md)：资料解析、知识提炼、Wiki 页面生成和维护流程
- [AI 协作约束](AGENTS.md)：用户与 AI 助手的职责边界

## 开发状态

当前已完成项目骨架、基础认证权限、Wiki 与附件管理等本地开发工作。后续开发以“构建和维护 Wiki 知识层”为主线推进。
