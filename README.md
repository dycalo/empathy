# Empathy 🧠💬

Empathy 是一个可控的 Agent 心理情感支持对话生成与实验框架。通过两端（Client / Therapist）人在回路（Human-in-the-Loop）的命令行界面，结合大语言模型（LLMs），辅助研究人员、心理咨询师或剧本作者生成、评估并干预心理咨询对话。

## 🌟 核心特性

- **两端三层级架构（Global / User / Dialogue）**
  - **Global 层**：管理最底层的规则与全局可用的动态技能（如社会背景、职业底线原则）
  - **User 层（原型库）**：预先设定来访者（Client）与咨询师（Therapist）的原型配置
  - **Dialogue 层**：基于具体的咨询场景快速覆盖参数

- **三模模块解耦设计（STATE, SKILL, MCP）**
  - **STATE**：将角色设定静态注入系统，解决模型"身份遗忘"问题
  - **SKILL**：将技能以 Markdown frontmatter 形式按需动态装载为 Tool
  - **MCP**：支持级联配置原生 MCP Servers，接入外部数据源

- **人在回路控制**：每条发言均可 Accept / Edit / Reject，完整保存训练信号

- **上下文窗口管理**：自动对超出窗口的历史轮次生成摘要，保持长对话连贯性

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
```

---

## 🚀 快速开始

### 第一步：启动交互式 TUI（人工控制模式）

在项目目录下，以 therapist 身份开始：

```bash
python -m empathy.cli.main start --side therapist
```

首次运行时会提示创建新对话。在另一个终端以 client 身份加入：

```bash
python -m empathy.cli.main start --side client
```

两端均连接后，对话即可开始。

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

### 管理对话列表

```bash
# 列出所有对话（start 命令会显示对话选择菜单）
python -m empathy.cli.main start --side therapist

# 删除指定对话
python -m empathy.cli.main delete <dialogue-id>
python -m empathy.cli.main delete <dialogue-id> --force  # 跳过确认
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
    │   └── summary.json     # 历史轮次压缩摘要
    └── client/
        └── summary.json
```

`draft-history.jsonl` 中的数据包含原始草稿、编辑后内容及结果标注，可直接用于模型微调或偏好学习（RLHF）。

---

## 🤝 贡献指南

1. 运行测试确保不破坏三层级合并逻辑：
   ```bash
   .venv/bin/python -m pytest tests/ -v
   ```

2. 核心逻辑位置：
   - `empathy/agents/` — Agent 系统提示与 API 调用
   - `empathy/modes/` — 会话管理与 auto 模式
   - `empathy/extensions/` — 技能、配置、MCP 加载
   - `empathy/cli/` — TUI 与命令行入口
   - `empathy/storage/` — 转录、草稿、状态持久化

---

## 📜 许可证

MIT License
