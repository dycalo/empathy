# Empathy 🧠💬

Empathy 是一个可控的 Agent 心理情感支持对话生成与实验框架。通过两端（Client / Therapist）人在回路（Human-in-the-Loop）的命令行界面，结合强大的大语言模型（LLMs），辅助研究人员、心理咨询师或剧本作者生成、评估并干预心理咨询对话。

本项目借鉴了前沿的 Agent 工程设计模式（例如 Claude Code 的多层级系统指令与上下文协议），将系统状态与角色技能彻底解耦，大幅提升了对模型行为的约束力和动态扩展性。

## 🌟 核心特性

- **两端三层级架构（Global / User / Dialogue）**
  - **Global 层**：管理最底层的规则与全局可用的动态技能（如社会背景、职业底线原则）。
  - **User 层（原型库）**：你可以预先设定多个来访者（Client）与咨询师（Therapist）的原型配置，针对不同的“人格设定”、“工作风格”进行独立配置。
  - **Dialogue 层**：基于具体的咨询场景或突发事件快速覆盖参数，指定当前 Session 使用的 User 原型。

- **三模模块解耦设计（STATE, SKILL, MCP）**
  - **STATE 静态状态注入**：基于 XML 结构，分别将 Global/User/Dialogue 层的角色设定静态注入系统，彻底解决模型“身份遗忘”的问题。
  - **SKILL 动态能力调用**：摒弃长篇大论的 System Prompt！系统将自动读取启用技能（如 `ptsd_reaction` 或 `cbt_framework`）的 Markdown 头文件（Frontmatter），动态装载为 Tool 提供给 Agent。仅在条件触发时，Agent 才会按需调用并获取完整的设定内容，保持上下文的轻量与高效。
  - **MCP 模型上下文协议（Model Context Protocol）**：支持在不同层级以 `mcp.json` 形式级联配置并启动原生 MCP Servers，轻松外接如蓝牙心率带、面部表情分析等外部数据源。

## 📂 架构概览与配置结构

系统强依赖于文件目录结构来组织原型与对话。默认配置文件位于用户目录 `~/.empathy/` 及当前工作区的 `dialogues/`。

```text
~/.empathy/
├── global/                            # Global 层（物理资产存储与最底层设定）
│   ├── client/
│   │   ├── CLIENT.md                  # 静态：通用社会关系定义
│   │   ├── skills/                    # 动态能力：所有 BEHAVIOR.md (如 ptsd.md)
│   │   └── mcp.json                   # 外部接口：所有可用的 MCP Servers
│   └── therapist/
│       ├── THERAPIST.md               # 静态：心理咨询师职业底线
│       ├── skills/                    # 动态能力：所有 THERAPY.md
│       └── mcp.json
│
└── users/                             # User 层（角色原型库）
    ├── client_alice/                  # 来访者原型 A
    │   ├── CLIENT.md                  # 静态：具体的人格、性格设定
    │   └── config.yaml                # 动态配置：开启的 SKILL 和 MCP (继承自 Global)
    └── therapist_bob/                 # 咨询师原型 B
        ├── THERAPIST.md               # 静态：倾听/表达的工作风格
        └── config.yaml

<项目目录>/dialogues/session_001/         # Dialogue 层（具体的对话实例）
├── client/
│   └── CLIENT.md                      # 静态：当前面临的现实处境与突发事件
├── therapist/
│   └── THERAPIST.md                   # 静态：本次咨询的重点与目标
└── dialogue.yaml                      # 核心配置：指定使用哪些 User 原型、覆盖哪些设定
```

## 🚀 部署说明

### 前置要求
- Python 3.9+
- 推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖，或者使用 pip/poetry。

### 安装依赖

克隆本仓库并在项目根目录下执行安装：

```bash
# 如果使用 uv (推荐)
uv venv
source .venv/bin/activate
uv pip sync uv.lock

# 或者标准 pip 安装
pip install -e .
```

### 配置大模型 API 密钥

目前框架已通过 Anthropic API 实现，请配置环境变量：

```bash
export EMPATHY_API_KEY="sk-ant-api03-xxxx..."
# 可选：配置覆盖默认调用的模型
# export EMPATHY_MODEL="claude-3-7-sonnet-20250219"
# 可选：如果你使用代理或中转服务
# export EMPATHY_BASE_URL="https://api.your-proxy.com"
```

## 📖 使用说明

### 1. 初始化你的第一场对话 (Dialogue)

在开始运行前，你需要准备对应层级的文件结构。这里以跑通一个最小示例为例：

1. **设置 Global 技能池**：创建 `~/.empathy/global/client/skills/defense.md`
    ```markdown
    ---
    name: defense_mechanism
    type: behavior
    description: 当感觉到被心理咨询师指责时，表现出极强的防御机制。
    ---
    表现形式：
    1. 说话带刺，转移话题。
    2. 否认自己的问题，试图指出咨询师逻辑的漏洞。
    3. 拒绝直接回答关于内心感受的提问。
    ```

2. **创建一个 User 原型**：创建 `~/.empathy/users/client_demo/config.yaml`
    ```yaml
    enabled_skills:
      - defense_mechanism
    ```

3. **创建你的对话场景 (Dialogue)**：在当前项目的 `dialogues/session_001/dialogue.yaml`
    ```yaml
    client_id: client_demo
    therapist_id: therapist_default
    ```
   可以在 `dialogues/session_001/client/CLIENT.md` 中补充具体的情境：
   ```text
   我最近失业了，我觉得这全是管理层的错，但大家都在怪我。
   ```

### 2. 启动命令行界面 (CLI)

确保你在项目根目录下，执行主程序启动当前对话会话：

```bash
python -m empathy.cli.main --dialogue-dir dialogues/session_001
```

你将进入双端互动的 CLI 界面。作为**人在回路的控制器（Controller）**，你可以：
- 直接向 Client 或 Therapist 下达指令（如：“表现得更加焦虑”、“尝试使用 CBT 引导她”）。
- 模型根据指令生成草稿（Draft）后，由你决定 **批准（Accept）**、**修改（Edit）** 还是 **拒绝并重试（Reject）**。
- 一旦某端的话语被批准，这句对话将会正式进入转录（Transcript）并展示给另一端。

在对话过程中，当 Agent 判定条件满足时，会自动通过系统底层的 **Tool Calling** 读取 `defense_mechanism` 的详情指导自己的下一步发言！

## 🤝 贡献指南

1. 这个项目使用了非常严格的模块化组件，核心逻辑在 `empathy/extensions/`。
2. 添加任何新的文件读取或者解析规则时，请运行 `uv run pytest tests/`，确保三层级的合并与覆盖没有被破坏。

## 📜 许可证

MIT License
