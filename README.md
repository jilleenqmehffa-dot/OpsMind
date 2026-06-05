# OpsMind

OpsMind 是面向企业运维团队的智能知识管理平台。项目计划整合 Wiki、检索增强生成（RAG）和 Agent 工具调用能力，将分散的运维文档、故障案例与内部规范转化为可检索、可追溯、可复用的知识资产。

> 当前状态：规划阶段，业务代码尚未提交。

## 核心能力

- 管理 Markdown、PDF、DOCX 和 TXT 等格式的运维文档
- 提供关键词检索、语义检索和 AI 辅助检索
- 基于企业知识库回答运维问题，并展示引用来源
- 自动生成文档摘要、知识提炼和新人学习路径
- 沉淀故障现象、原因分析、排查过程和修复方案
- 通过 ReAct Agent 调用知识检索与文档总结工具

## 计划架构

```text
User
  |
Vue 3 Frontend
  |
FastAPI API Gateway
  |
LangChain Agent Layer
  |
ReAct Agent
  |
Tool Calling
  +-- Wiki Search
  +-- ChromaDB Search
  +-- Document Summary
  +-- LLM Provider
```

计划采用 PostgreSQL 存储业务数据，Redis 提供缓存与限流能力，ChromaDB 存储向量数据。

## 项目文档

- [项目设计文档](docs/project-design.md)：需求、架构、开发约定、部署规划和路线图
- [模块实施计划](docs/module-plan.md)：按照模块列出开发顺序、任务和完成标准
- [AI 协作约束](AGENTS.md)：后端由用户亲自实施，前端由 AI 助手直接完成

## 开发状态

当前仓库尚未提交可运行代码。进入实现阶段后，本节将补充依赖安装、配置示例、启动方式、测试命令和构建流程。
