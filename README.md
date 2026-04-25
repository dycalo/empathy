# Empathy 🧠💬

Empathy 是一个可控的 Agent 心理情感支持对话生成与实验框架。通过两端（Client / Therapist）人在回路（Human-in-the-Loop）的命令行界面，结合大语言模型（LLMs），辅助研究人员、心理咨询师或剧本作者生成、评估并干预心理咨询对话。

## 🌟 核心特性

- **两端三层级架构（Global / User / Dialogue）**
  - **Global 层**：管理最底层的规则与全局可用的动态技能（如社会背景、职业底线原则）
  - **User 层（原型库）**：预先设定来访者（Client）与咨询师（Therapist）的原型配置
  - **Dialogue 层**：基于具体的咨询场景快速覆盖参数

- **双 Agent 系统（BaseAgent / LangChainAgent）**
  - **BaseAgent**：轻量级实现，直接调用 Anthropic API
  - **LangChainAgent**：基于 LangChain 的增强实现，支持 ReAct 推理、工具编排和自动重试
  - 通过 `--use-langchain` 标志灵活切换

- **完整的系统工具集**
  - **speak**：提交对话轮次（终端工具）
  - **listen**：读取对话历史（支持 recent/all/range/search）
  - **record**：therapist 维护临床记录（assessment/progress_note/treatment_plan/observation）
  - **emotion_state**：client 追踪情绪状态（情绪/强度/触发因素/身体感受）
  - **memory_manage**：长期记忆管理（关键事件/模式/关系/洞察）

- **自动状态管理（控制论闭环）**
  - **Client 情感状态自动更新**：每轮对话前自动分析 therapist 的话对 client 情感的影响，生成新的情感状态并注入到 prompt
  - **Therapist 临床观察自动生成**：每轮对话前自动分析 client 的回应，生成临床观察（来访者表现、情绪变化、治疗联盟、干预效果）并注入到 prompt
  - **可配置开关**：通过环境变量 `EMPATHY_CLINICAL_OBSERVATION=0` 禁用 therapist 自动观察功能

- **三模模块解耦设计（STATE, SKILL, MCP）**
  - **STATE**：角色设定
  - **SKILL**：角色技能
  - **MCP**：外部数据接入（完整的 MCP 客户端实现，支持异步工具调用）

- **人在回路控制**：每条发言均可 Accept / Edit / Reject，完整保存训练信号

- **上下文窗口管理**：自动对超出窗口的历史轮次生成摘要，保持长对话连贯性

- **增强的可观测性**：完整的回调处理器，追踪工具调用、错误统计和执行日志

---

## 📦 安装

### 前置要求

- Python 3.9+
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

### 安装步骤

```bash
git clone <repo-url>
cd empathy

# 使用 uv（推荐）
uv venv && source .venv/bin/activate
uv pip sync uv.lock

# 或使用 pip
pip install -e .
```

### 配置 API Key

```bash
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."

# 可选：指定模型（默认 claude-haiku-4-5-20251001）
export EMPATHY_MODEL="claude-sonnet-4-5"

# 可选：使用代理或中转服务
export EMPATHY_BASE_URL="https://api.your-proxy.com"

# 可选：禁用 therapist 自动临床观察（默认启用）
export EMPATHY_CLINICAL_OBSERVATION=0
```

---

## 🚀 快速开始

### 第一步：启动交互式 TUI（人工控制模式）

在项目目录下，以 therapist 身份开始：

```bash
# 使用 LangChain Agent（默认，推荐）
python -m empathy.cli.main start --side therapist

# 或使用轻量级 BaseAgent
python -m empathy.cli.main start --side therapist --no-langchain
```

首次运行时会提示创建新对话。在另一个终端以 client 身份加入：

```bash
python -m empathy.cli.main start --side client
```

两端均连接后，对话即可开始。

**LangChain Agent 优势**（默认启用）：
- 自动工具编排和 ReAct 推理
- 内置重试机制（最多 3 次，指数退避）
- 更强的错误处理和降级能力
- 完整的执行统计和日志追踪

### 第二步：在 TUI 中生成发言

TUI 分为两个面板：
- **左侧**：控制面板（指令输入、草稿确认、日志）
- **右侧**：对话转录（实时更新）

在左侧指令框中输入任意指令，例如：

```
hi
```
```
继续对话
```
```
表现出更多的焦虑情绪
```

Agent 会根据指令生成草稿，然后显示确认选项。

---

## 📖 详细使用说明

### 交互式 TUI 模式（`start` 命令）

```bash
python -m empathy.cli.main start \
  --side therapist \          # 必填：therapist 或 client
  --project /path/to/proj \   # 可选：项目目录（默认当前目录）
  --client-id my_client \     # 可选：预设 client 原型 ID
  --therapist-id my_therapist # 可选：预设 therapist 原型 ID
  --use-langchain             # 可选：使用 LangChain Agent（默认启用）
  --no-langchain              # 可选：使用轻量级 BaseAgent
```

#### 指令输入方式

在指令框中，你可以输入：

| 输入类型 | 示例 | Agent 行为 |
|----------|------|------------|
| 简短问候 | `hi`、`hello` | 生成开场问候语 |
| 继续指令 | `continue`、`go ahead` | 自然延续对话 |
| 主题词 | `anxiety`、`reflect` | 以该词为主题发言 |
| 具体指令 | `ask about childhood` | 按指令内容生成 |
| 斜杠命令 | `/done`、`/help` | 执行系统命令 |

#### 草稿确认选项

Agent 生成草稿后，可用以下操作：

| 按键 | 操作 |
|------|------|
| `a` | **Accept** — 直接采纳草稿，提交到转录 |
| `e` | **Edit** — 手动编辑草稿后提交 |
| `r` | **Reject** — 拒绝草稿，重新输入指令 |
| `h` | **Type yourself** — 跳过 Agent，直接键入发言内容 |
| `Tab` | **Refine** — 将当前指令返回到输入框，便于修改后重试 |
| `↑`/`↓` | 在选项间移动 |
| `Enter` | 确认当前选中项 |

#### 楼层系统（Floor System）

楼层控制哪一端当前可以发言，防止两端同时写入：

- 进入 TUI 后，系统会自动尝试获取楼层
- 当前拥有楼层时，可以输入指令和生成草稿
- 输入 `/done` 释放楼层，让另一端开始发言
- 状态栏底部实时显示楼层持有方

```
therapist │ floor: MINE │ turn: 3 │ model: claude-haiku-4-5-20251001 │ skills: 2
```

### 自动模式（`run` 命令）

无需人工确认，自动轮流生成指定轮次：

```bash
python -m empathy.cli.main run \
  dialogues/session_001 \    # 对话目录路径
  --turns 20 \               # 生成轮次（默认 10）
  --model claude-haiku-4-5-20251001  # 使用的模型
```

自动模式适合快速生成大量对话数据，所有发言均标记为 `AGENT_AUTO` 来源。

### TUI 斜杠命令参考

在指令框中输入 `/` 后按 `Tab` 可自动补全命令。

| 命令 | 说明 |
|------|------|
| `/done` | 释放楼层，让另一端发言 |
| `/quit` | 退出当前 session |
| `/help` | 列出所有可用命令 |
| `/status` | 查看楼层和轮次状态 |
| `/context` | 查看上下文信息（已接受/编辑/拒绝的草稿数） |
| `/context clear` | 重置上下文提示（Agent 下次调用时重新读取历史） |
| `/agent` | 查看当前 Agent 信息（模型、知识量等） |
| `/agent model <id>` | 动态切换模型，立即生效 |
| `/skills` | 列出当前加载的技能 |
| `/session` | 查看完整 session 信息 |
| `/feedback` | 查看最近被拒绝或编辑的草稿（用于 few-shot 学习） |
| `/feedback stats` | 显示草稿接受率、拒绝率、编辑率统计 |
| `/feedback clear` | 清除草稿历史（需确认） |
| `/tools` | 查看 API 使用统计（token 使用、延迟等） |
| `/emotion` | 查看 client 当前情感状态（client 专用） |
| `/observation` | 查看 therapist 当前临床观察（therapist 专用） |

### 管理对话列表

```bash
# 列出所有对话（start 命令会显示对话选择菜单）
python -m empathy.cli.main start --side therapist

# 删除指定对话
python -m empathy.cli.main delete <dialogue-id>
python -m empathy.cli.main delete <dialogue-id> --force  # 跳过确认
```

### 导出训练数据

Empathy 支持将对话数据导出为标准的训练格式，用于模型微调或 RLHF（Reinforcement Learning from Human Feedback）训练。

#### 导出格式

**SFT（Supervised Fine-Tuning）格式**：
- 数据源：`transcript.jsonl`（最终对话内容）
- 用途：监督学习，学习正确的回复
- 包含：所有被接受或编辑后的 turns

**RLHF 格式**：
- 数据源：`transcript.jsonl` + `draft-history.jsonl`
- 用途：偏好学习，学习好坏对比
- 包含：chosen（transcript）vs rejected（draft-history）
- 预留：`feedback_label` 字段用于结构化标签

#### 导出命令

```bash
# 导出 SFT 数据
python -m empathy.cli.main export session_001 --format sft

# 导出 RLHF 数据
python -m empathy.cli.main export session_001 --format rlhf

# 同时导出两种格式
python -m empathy.cli.main export session_001 --format sft,rlhf --output ./data

# 预览模式（不写入文件）
python -m empathy.cli.main export session_001 --format rlhf --preview

# 只包含被拒绝的草稿（RLHF）
python -m empathy.cli.main export session_001 --format rlhf --include rejected

# 包含被拒绝和编辑的草稿（RLHF）
python -m empathy.cli.main export session_001 --format rlhf --include rejected,edited
```

#### 输出文件

```
training_data/
├── session_001_sft.jsonl       # SFT 数据
├── session_001_rlhf.jsonl      # RLHF 数据
└── session_001_stats.json      # 统计信息
```

#### 数据格式示例

**SFT 格式**：
```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."},
      {"role": "assistant", "content": "[THERAPIST]: Tell me more..."}
    ],
    "instruction": "validate their feelings"
  },
  "completion": "That sounds really challenging. I hear the frustration.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 3,
    "timestamp": "2026-04-25T10:28:00Z",
    "source": "accepted",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

**RLHF 格式**：
```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."}
    ],
    "instruction": "explore their anxiety"
  },
  "chosen": "Can you help me understand what specifically triggers this anxiety?",
  "rejected": "Let's talk about your childhood experiences with failure.",
  "feedback_label": null,
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "chosen_source": "accepted",
    "rejected_draft_id": "uuid",
    "rejection_reason": "too directive, jumped to conclusions",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

---

## 📂 配置结构

系统采用三层级配置，下层设置会覆盖上层：

```
~/.empathy/                              # ← Global 层（全局默认）
├── global/
│   ├── client/
│   │   ├── CLIENT.md                   # 通用 client 知识/规则
│   │   ├── skills/                     # 全局可用技能
│   │   └── mcp.json                    # 全局 MCP 配置
│   └── therapist/
│       ├── THERAPIST.md                # 通用 therapist 知识/规则
│       ├── skills/
│       └── mcp.json
└── users/                              # ← User 层（角色原型）
    ├── client_alice/
    │   ├── CLIENT.md                   # Alice 的个性化设定
    │   └── config.yaml                 # 启用的技能和 MCP
    └── therapist_bob/
        ├── THERAPIST.md
        └── config.yaml

<project>/dialogues/session_001/        # ← Dialogue 层（具体对话）
├── client/
│   └── CLIENT.md                       # 本次 session 特有情境
├── therapist/
│   └── THERAPIST.md                    # 本次咨询重点
└── dialogue.yaml                       # 指定使用的原型 ID
```

### dialogue.yaml 示例

```yaml
client_id: client_alice      # 使用 ~/.empathy/users/client_alice/
therapist_id: therapist_bob  # 使用 ~/.empathy/users/therapist_bob/
```

### config.yaml 示例（User 层）

```yaml
llm:
  model: claude-sonnet-4-5   # 覆盖默认模型

enabled_skills:
  - defense_mechanism
  - anxiety_response

enabled_mcp_servers:
  - heart_rate_monitor
```

### MCP 工具集成

Empathy 支持通过 Model Context Protocol (MCP) 集成外部工具。MCP 服务器配置在 `mcp.json` 文件中：

```json
{
  "mcpServers": {
    "time": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-time"],
      "env": {}
    }
  }
}
```

**MCP 工具加载流程**：
1. 系统启动时异步连接所有配置的 MCP 服务器
2. 从每个服务器获取工具列表
3. 工具名称格式：`{server_name}_{tool_name}`（如 `time_get_current_time`）
4. LangChain Agent 可以像调用系统工具一样调用 MCP 工具

**启用 MCP 服务器**：
在 `config.yaml` 中添加：
```yaml
enabled_mcp_servers:
  - time
  - weather
```

---

## 🛠️ 系统工具（LangChain Agent）

使用 `--use-langchain` 标志时，Agent 可以主动调用以下系统工具来增强对话生成能力：

### 1. speak（终端工具）

**功能**：提交对话轮次，触发人在回路确认流程

**使用场景**：Agent 准备好回应时调用此工具

**参数**：
- `content`：对话内容

**示例**：
```python
speak(content="我理解你现在感到很焦虑，能具体说说是什么让你有这种感觉吗？")
```

### 2. listen（对话历史查询）

**功能**：读取对话历史的特定部分

**使用场景**：需要回顾之前的对话内容时

**参数**：
- `scope`：查询范围（recent/all/range/search）
- `limit`：返回轮次数（默认 5）
- `start_turn`/`end_turn`：范围查询的起止轮次
- `keyword`：搜索关键词
- `speaker`：过滤说话者（therapist/client/both）

**示例**：
```python
# 查看最近 3 轮对话
listen(scope="recent", limit=3)

# 搜索包含"焦虑"的对话
listen(scope="search", keyword="焦虑")

# 查看第 5-10 轮对话
listen(scope="range", start_turn=5, end_turn=10)
```

### 3. record（临床记录 - therapist 专用）

**功能**：therapist 维护临床记录

**使用场景**：记录评估、进展笔记、治疗计划、观察

**参数**：
- `action`：操作类型（create/read/update/list）
- `record_type`：记录类型（assessment/progress_note/treatment_plan/observation）
- `content`：记录内容
- `record_id`：记录 ID（更新/读取时使用）

**示例**：
```python
# 创建初始评估
record(
    action="create",
    record_type="assessment",
    content="来访者表现出中度焦虑症状，主要与工作压力相关..."
)

# 列出所有进展笔记
record(action="list", record_type="progress_note")
```

**存储位置**：`<dialogue_dir>/.empathy/therapist/records/`

### 4. emotion_state（情绪状态 - client 专用）

**功能**：client 追踪和更新情绪状态

**使用场景**：表达当前情绪、记录情绪变化

**参数**：
- `action`：操作类型（update/read/history）
- `primary_emotion`：主要情绪
- `intensity`：强度（1-10）
- `triggers`：触发因素列表
- `physical_sensations`：身体感受列表
- `thoughts`：相关想法

**示例**：
```python
# 更新当前情绪状态
emotion_state(
    action="update",
    primary_emotion="anxious",
    intensity=7,
    triggers=["即将到来的演讲", "害怕被评判"],
    physical_sensations=["胸闷", "心跳加速"],
    thoughts="大家都会觉得我很无能"
)

# 查看情绪历史
emotion_state(action="history")
```

**存储位置**：`<dialogue_dir>/.empathy/client/emotion-states/`

### 5. memory_manage（长期记忆管理）

**功能**：存储和检索关键事件、模式、关系动态、洞察

**使用场景**：记录重要信息以便后续对话使用

**参数**：
- `action`：操作类型（store/retrieve/search/update/delete）
- `memory_type`：记忆类型（key_event/pattern/relationship/insight）
- `content`：记忆内容
- `memory_id`：记忆 ID
- `query`：搜索查询
- `importance`：重要性（1-10，默认 5）

**示例**：
```python
# 存储模式识别
memory_manage(
    action="store",
    memory_type="pattern",
    content="来访者在讨论工作时倾向于灾难化思维",
    importance=8
)

# 搜索相关记忆
memory_manage(
    action="search",
    query="工作焦虑"
)
```

**存储位置**：`<dialogue_dir>/.empathy/<side>/memories/`

### 工具调用流程

LangChain Agent 使用 ReAct 模式自动决定何时调用哪些工具：

1. **therapist 典型流程**：
   ```
   listen(查看最近对话) → record(记录观察) → memory_manage(存储模式) → speak(回应)
   ```

2. **client 典型流程**：
   ```
   emotion_state(更新情绪) → listen(回顾讨论) → memory_manage(记录洞察) → speak(回应)
   ```

3. **错误处理**：
   - 工具调用失败时自动重试（最多 3 次）
   - 重试失败后降级到 BaseAgent
   - 所有错误都会记录到日志

---

## 🔧 技能（Skills）配置

技能以 Markdown frontmatter 格式存储，按需动态装载给 Agent。

### 创建技能

在 `~/.empathy/global/client/skills/` 中新建文件，例如 `defense.md`：

```markdown
---
name: defense_mechanism
type: behavior
description: 当感受到被指责时，表现出强烈的防御机制。
enabled: true
mode: manual   # manual（手动触发）或 always（每轮自动注入）
trigger: /defense
---

表现形式：
1. 说话带刺，转移话题
2. 否认自己的问题，指出对方逻辑漏洞
3. 拒绝直接回答关于内心感受的提问
```

### 使用技能

- `mode: always`：每次生成草稿时自动注入
- `mode: manual`：在指令框输入 trigger（如 `/defense`）手动激活
- 也可在指令中直接描述（如"使用 CBT 框架引导"）

### 通过 CLI 管理配置

```bash
# 查看和管理 config 子命令
python -m empathy.cli.main config --help
```

---

## 📊 数据存储

每个对话目录下保存完整的对话数据：

```
dialogues/session_001/
├── transcript.jsonl         # 最终对话转录（每轮一行 JSON）
├── draft-history.jsonl      # 所有草稿及处理结果（接受/编辑/拒绝）
└── .empathy/
    ├── state.json           # 楼层状态
    ├── therapist/
    │   ├── summary.json     # 历史轮次压缩摘要
    │   ├── records/         # 临床记录（LangChain Agent 手动工具）
    │   │   ├── assessments/
    │   │   ├── progress_notes/
    │   │   ├── treatment_plans/
    │   │   └── observations/
    │   ├── observations/    # 自动临床观察（系统自动生成）
    │   │   ├── current.json
    │   │   └── history.jsonl
    │   └── memories/        # 长期记忆（LangChain Agent）
    │       ├── key_events/
    │       ├── patterns/
    │       ├── relationships/
    │       ├── insights/
    │       └── index.json
    └── client/
        ├── summary.json
        ├── emotion-states/  # 情绪状态追踪（系统自动生成 + Agent 手动工具）
        │   ├── current.json
        │   └── history.jsonl
        └── memories/        # 长期记忆（LangChain Agent）
            ├── key_events/
            ├── patterns/
            ├── relationships/
            ├── insights/
            └── index.json
```

`draft-history.jsonl` 中的数据包含原始草稿、编辑后内容及结果标注，可直接用于模型微调或偏好学习（RLHF）。

**draft-history.jsonl 格式**：
```json
{
  "id": "draft_uuid",
  "speaker": "therapist",
  "content": "Let's talk about your childhood...",
  "source_instruction": "explore their anxiety",
  "outcome": "rejected",
  "final_content": null,
  "timestamp": "2026-04-25T10:30:00Z",
  "conversation_window": {
    "start_turn": 1,
    "end_turn": 4
  },
  "api_usage": {
    "input_tokens": 1500,
    "output_tokens": 150,
    "cached_tokens": 800,
    "latency_ms": 2500
  },
  "rejection_reason": "too directive, jumped to conclusions",
  "model": "claude-haiku-4-5-20251001"
}
```

**扩展字段说明**：
- `conversation_window`：草稿生成时的对话窗口范围（用于重建 context）
- `api_usage`：API 调用的 token 统计和延迟
- `rejection_reason`：用户可选标注的拒绝原因
- `model`：使用的模型名称

**LangChain Agent 新增存储**：
- `records/`：therapist 的临床记录（手动工具），按类型分类存储
- `observations/`：therapist 的自动临床观察（系统自动生成），包含当前观察和历史记录
- `emotion-states/`：client 的情绪状态追踪（系统自动生成 + 手动工具），包含当前状态和历史记录
- `memories/`：两端共享的长期记忆系统，支持快速检索和搜索

---

## 🔄 自动状态管理（控制论闭环）

Empathy 实现了基于控制论的自动状态管理系统，模拟真实心理咨询中的动态反馈循环。

### Client 情感状态自动更新

**触发时机**：每次 client 准备生成回应前

**工作流程**：
1. 读取 therapist 最新一轮对话
2. 调用 LLM 分析 therapist 的话对 client 情感的影响
3. 考虑因素：
   - 验证水平（therapist 是否认可 client 的感受）
   - 挑战水平（therapist 是否质疑 client 的想法）
   - 探索深度（therapist 是否邀请更深入的分享）
   - 情感基调（therapist 的温暖程度）
   - Client 的人格特质和行为模式（从 active_skills 获取）
4. 生成新的情感状态（情绪、强度、触发因素、身体感受、想法）
5. 注入到 client agent 的 prompt 中

**存储位置**：`.empathy/client/emotion-states/`
- `current.json`：当前情感状态
- `history.jsonl`：历史情感状态记录

**示例状态**：
```json
{
  "timestamp": "2026-04-25T10:30:00Z",
  "turn_number": 5,
  "primary_emotion": "anxious",
  "intensity": 6,
  "secondary_emotions": ["sad"],
  "triggers": ["work pressure", "fear of judgment"],
  "physical_sensations": ["chest tightness", "rapid heartbeat"],
  "thoughts": "Maybe I can talk about this",
  "change_direction": "decreasing",
  "reasoning": "Therapist's validation reduced anxiety slightly"
}
```

### Therapist 临床观察自动生成

**触发时机**：每次 therapist 准备生成回应前

**工作流程**：
1. 读取 client 最新一轮对话
2. 读取 client 当前情感状态（如果可用）
3. 调用 LLM 生成临床观察
4. 分析维度：
   - Client 表现（情绪和行为呈现）
   - 情绪变化（改善/恶化/稳定）
   - 治疗联盟（强/建立中/紧张）
   - 干预效果（active_skills 的效果评估）
   - 临床关注点（下次干预的重点）
   - 风险因素（自杀意念、自伤等）
5. 注入到 therapist agent 的 prompt 中

**存储位置**：`.empathy/therapist/observations/`
- `current.json`：当前临床观察
- `history.jsonl`：历史观察记录

**示例观察**：
```json
{
  "timestamp": "2026-04-25T10:32:00Z",
  "turn_number": 6,
  "client_presentation": "anxious but engaged",
  "emotional_shift": "improving",
  "therapeutic_alliance": "establishing",
  "intervention_effectiveness": "active_listening helped client open up",
  "clinical_focus": ["explore work-related stress", "validate emotional experience"],
  "risk_factors": [],
  "reasoning": "Client responded positively to validation, showing increased openness"
}
```

### 配置选项

**禁用 therapist 自动观察**：
```bash
export EMPATHY_CLINICAL_OBSERVATION=0
```

**注意**：
- Client 情感状态自动更新无法禁用（核心功能）
- 自动状态仅对 agent 可见，不会显示在对话转录中
- 状态通过 prompt 注入影响 agent 行为，形成闭环反馈



## 🤝 贡献指南

1. 运行测试确保不破坏三层级合并逻辑：
   ```bash
   .venv/bin/python -m pytest tests/ -v
   ```

2. 核心逻辑位置：
   - `empathy/agents/` — Agent 系统提示与 API 调用
     - `base.py` — BaseAgent 实现（轻量级）
     - `langchain_agent.py` — LangChain Agent 实现（增强版）
     - `callbacks.py` — LangChain 回调处理器
     - `tools/` — 系统工具实现（speak/listen/record/emotion_state/memory_manage）
   - `empathy/modes/` — 会话管理与 auto 模式
   - `empathy/extensions/` — 技能、配置、MCP 加载
   - `empathy/cli/` — TUI 与命令行入口
   - `empathy/storage/` — 转录、草稿、状态持久化

3. 测试覆盖：
   - 单元测试：`tests/test_tools.py`（工具测试）
   - 并发测试：`tests/test_concurrency.py`（文件锁测试）
   - 集成测试：`tests/test_langchain_agent.py`（Agent 测试）
   - MCP 测试：`tests/test_mcp_integration.py`（MCP 集成测试）

4. 依赖管理：
   - 使用 `uv` 管理依赖
   - 添加新依赖后运行 `uv pip compile pyproject.toml -o requirements.txt`
   - 主要依赖：`langchain>=0.1.0`, `langchain-anthropic>=0.1.0`, `tenacity>=8.0`, `mcp>=0.9.0`

---

## 📜 许可证

MIT License
