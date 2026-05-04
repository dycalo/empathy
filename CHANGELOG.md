# Changelog

## 2026-05-04

### 系统工具重构

#### speak
- 终端标记格式从 `__TERMINAL_SPEAK__:content` 迁移为 XML 标记 `<terminal_speak>content</terminal_speak>`
- 增加空内容校验

#### listen（已移除）
- 删除 `listen` 工具。该功能已由 `ContextBuilder.build_messages()` 通过完整 transcript 提供，工具调用完全冗余
- 从所有文档、测试、agent prompt 中清理引用

#### context / session 简化
- `ContextBuilder` 移除对话窗口（window）管理，改为传递**完整 transcript**
- `DialogueSession` 移除 window 单例和相关状态管理
- Agent 自行决定关注范围，不再依赖外部 summary 注入

### 长期记忆迁移：dialogue-level → user-level + Neo4j

#### 存储层（新增）
- `empathy/storage/memory_models.py` — `Memory` 数据模型
- `empathy/storage/memory_repo.py` — 仓库抽象 + `InMemoryMemoryRepository`（测试/降级用）
- `empathy/storage/neo4j_repo.py` — `Neo4jMemoryRepository`
  - 图模型：`(:User {user_id})-[:HAS_MEMORY]->(:Memory)`
  - 自动 schema：唯一约束 + Lucene 全文索引
  - 单例工厂 `get_memory_repository()`：根据 `NEO4J_URI` 环境变量自动选择后端

#### memory_manage 工具重写
- 不再使用 JSON 文件存储（`<dialogue_dir>/.empathy/<side>/memories/` 已废弃）
- `create_memory_manage_tool(user_id)` — `user_id` 为 `None` 时工具不注册
- 所有操作通过仓库层执行，用户隔离由闭包 `user_id` 保证

#### user_id 传播
- `dialogue.yaml` 中的 `client_id` / `therapist_id` 作为 user-level 记忆的键
- `resolve_user_id()` 从配置解析 → 注入 `LangChainAgent` → 注入 `ToolRegistry` → 条件注册 memory 工具
- 同一用户的记忆在所有对话间共享

#### CLI 对话过滤
- 启动时若指定 `--client-id` / `--therapist-id`，对话列表只显示匹配该用户（或未分配）的对话
- 未指定时保持原有行为（显示全部）

#### 依赖
- 新增 `neo4j>=5.0`

### 文档
- 更新 README、architecture、tools 文档，移除 listen 引用，更新 memory_manage 说明
