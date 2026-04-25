# 训练数据导出格式确认

## 一、导出目标

从draft-history.jsonl和transcript.jsonl中提取训练数据，用于：
1. **RLHF (Reinforcement Learning from Human Feedback)** - 强化学习微调
2. **DPO (Direct Preference Optimization)** - 直接偏好优化
3. **SFT (Supervised Fine-Tuning)** - 监督微调

---

## 二、数据来源

### 2.1 draft-history.jsonl
包含所有agent生成的drafts及用户反馈：
```json
{
  "id": "uuid",
  "speaker": "therapist",
  "content": "Let's talk about your childhood...",
  "source_instruction": "explore their anxiety",
  "outcome": "rejected",  // accepted, rejected, edited, pending
  "timestamp": "2026-04-25T10:30:00Z",
  "final_content": null,  // 如果是edited，这里是编辑后的内容
  "conversation_window": {"start_turn": 0, "end_turn": 5},
  "api_usage": {"input_tokens": 1500, "output_tokens": 150, ...},
  "rejection_reason": "too directive",  // 可选
  "model": "claude-haiku-4-5-20251001"
}
```

### 2.2 transcript.jsonl
包含最终提交到对话中的turns：
```json
{
  "id": "uuid",
  "speaker": "client",
  "source": "human",
  "content": "I've been feeling anxious lately...",
  "timestamp": "2026-04-25T10:29:00Z"
}
```

---

## 三、导出格式

### 3.1 RLHF/DPO格式（推荐用于偏好学习）

**用途**：训练模型理解"好"和"坏"的回复之间的差异

**数据结构**：
```json
{
  "prompt": {
    "system": "You are a professional therapist in a structured dialogue...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious lately..."},
      {"role": "assistant", "content": "[THERAPIST]: Tell me more about that..."}
    ],
    "instruction": "explore their anxiety"
  },
  "chosen": "Can you help me understand what specifically triggers this anxiety?",
  "rejected": "Let's talk about your childhood experiences with failure.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "model": "claude-haiku-4-5-20251001",
    "feedback_type": "rejected",
    "rejection_reason": "too directive, jumped to conclusions"
  }
}
```

**字段说明**：
- `prompt`: 完整的输入上下文（system + messages + instruction）
- `chosen`: 好的回复（accepted或edited后的版本）
- `rejected`: 坏的回复（rejected的draft）
- `metadata`: 元数据（用于追踪和分析）

**构建逻辑**：
1. **rejected类型**：
   - chosen = 下一个accepted的draft（如果有）
   - rejected = 当前rejected的draft
   
2. **edited类型**：
   - chosen = edited后的final_content
   - rejected = 原始的draft content

### 3.2 SFT格式（仅包含好的样本）

**用途**：监督学习，只学习正确的回复

**数据结构**：
```json
{
  "prompt": {
    "system": "You are a professional therapist...",
    "messages": [...],
    "instruction": "explore their anxiety"
  },
  "completion": "Can you help me understand what specifically triggers this anxiety?",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "model": "claude-haiku-4-5-20251001",
    "feedback_type": "accepted"
  }
}
```

**包含的样本**：
- outcome = "accepted" 的drafts
- outcome = "edited" 的drafts（使用final_content）

---

## 四、Context重建逻辑

### 4.1 System Prompt重建

需要重建完整的system prompt，包括：
1. Role preamble（角色描述）
2. Scene background（场景背景）
3. Guidelines/Knowledge（指南和知识）

**问题**：这些信息存储在哪里？
- 选项1：从dialogue_dir读取配置文件（therapist/THERAPIST.md, client/CLIENT.md）
- 选项2：从BaseAgent的配置中读取
- 选项3：简化版本，只包含基本的role preamble

**建议**：使用选项1，从配置文件重建完整的system prompt

### 4.2 Messages重建

使用draft的`conversation_window`字段：
```python
window_start = draft.conversation_window["start_turn"]
window_end = draft.conversation_window["end_turn"]
history = transcript[window_start:window_end+1]

messages = [
    {
        "role": "assistant" if turn.speaker == draft.speaker else "user",
        "content": f"[{turn.speaker.upper()}]: {turn.content}"
    }
    for turn in history
]
```

### 4.3 完整Context示例

```python
{
  "system": "You are a professional therapist...\n\n## Scene background\n\n...\n\n## Your guidelines\n\n...",
  "messages": [
    {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."},
    {"role": "assistant", "content": "[THERAPIST]: Tell me more..."},
    {"role": "user", "content": "[CLIENT]: It happens before meetings..."}
  ],
  "instruction": "explore their anxiety"
}
```

---

## 五、过滤和选项

### 5.1 包含的反馈类型

```python
include_types = ["rejected", "edited"]  # 默认
# 或
include_types = ["rejected"]  # 仅rejected
# 或
include_types = ["edited"]  # 仅edited
```

### 5.2 质量控制

**可选的过滤条件**：
1. 排除pending状态的drafts
2. 排除没有conversation_window的drafts（旧数据）
3. 排除没有rejection_reason的rejected drafts（可选）
4. 最小/最大token长度限制

### 5.3 输出格式

**文件格式**：
- JSONL（每行一个JSON对象）- 推荐，便于流式处理
- JSON（单个数组）- 适合小数据集

**文件命名**：
```
training_data/
├── session_001_rlhf.jsonl
├── session_001_sft.jsonl
└── session_001_metadata.json  # 汇总统计
```

---

## 六、CLI命令设计

### 6.1 基本命令

```bash
# 导出单个对话（RLHF格式）
empathy export session_001 --format rlhf --output training_data/

# 导出为SFT格式
empathy export session_001 --format sft --output training_data/

# 导出多个对话（使用通配符）
empathy export session_* --format rlhf --output training_data/
```

### 6.2 高级选项

```bash
# 预览导出结果（不写入文件）
empathy export session_001 --preview

# 只包含rejected类型
empathy export session_001 --include rejected

# 包含rejected和edited
empathy export session_001 --include rejected,edited

# 指定输出文件名
empathy export session_001 --output training_data/my_data.jsonl

# 包含metadata
empathy export session_001 --with-metadata

# 排除metadata
empathy export session_001 --no-metadata
```

### 6.3 批量导出

```bash
# 导出项目中所有对话
empathy export --all --format rlhf --output training_data/

# 按日期范围导出
empathy export --after 2026-04-01 --before 2026-04-30 --output training_data/
```

---

## 七、需要确认的问题

### 7.1 System Prompt重建

**问题**：如何重建完整的system prompt？

**选项**：
- A. 从dialogue_dir读取配置文件（therapist/THERAPIST.md等）
- B. 存储在draft中（需要扩展Draft模型）
- C. 简化版本，只包含基本的role preamble

**建议**：选项A，从配置文件重建

### 7.2 RLHF的chosen样本来源

**问题**：对于rejected的draft，如何找到对应的chosen样本？

**选项**：
- A. 使用下一个accepted的draft（同一turn）
- B. 使用最终提交到transcript的turn
- C. 手动标注（不自动生成）

**建议**：选项B，使用transcript中的turn

### 7.3 Edited样本的处理

**问题**：edited的draft应该如何处理？

**选项**：
- A. chosen=final_content, rejected=original draft
- B. 只使用final_content作为SFT样本
- C. 两者都包含

**建议**：选项A，作为RLHF对

### 7.4 输出格式

**问题**：默认使用JSONL还是JSON？

**选项**：
- A. JSONL（每行一个对象）- 便于流式处理
- B. JSON（单个数组）- 更易读

**建议**：选项A，JSONL

### 7.5 Metadata包含

**问题**：是否默认包含metadata？

**选项**：
- A. 默认包含（便于追踪）
- B. 默认不包含（减小文件大小）
- C. 可配置

**建议**：选项A，默认包含

---

## 八、实现优先级

### Phase 1（核心功能）
1. TrainingDataExporter类
2. RLHF格式导出
3. 基本CLI命令（单个对话导出）
4. Context重建逻辑

### Phase 2（增强功能）
1. SFT格式导出
2. 批量导出
3. 预览功能
4. 过滤选项

### Phase 3（高级功能）
1. 质量控制
2. 统计报告
3. 自动导出（会话结束时）
4. 导出配置（config.yaml）

---

## 九、示例输出

### 9.1 RLHF样本示例

```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue with a client. A human controller directs you via brief instructions...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling really anxious lately, especially before big meetings."},
      {"role": "assistant", "content": "[THERAPIST]: Thank you for sharing that. Can you tell me more about what happens when you feel this anxiety?"},
      {"role": "user", "content": "[CLIENT]: My heart races and I start thinking everyone will judge me."}
    ],
    "instruction": "explore the catastrophizing pattern"
  },
  "chosen": "I notice you mentioned thinking everyone will judge you. What evidence do you have for that thought?",
  "rejected": "Let's talk about your childhood experiences with failure and how they might relate to this.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "model": "claude-haiku-4-5-20251001",
    "feedback_type": "rejected",
    "rejection_reason": "too directive, jumped to conclusions without exploring current experience"
  }
}
```

### 9.2 SFT样本示例

```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling really anxious lately..."}
    ],
    "instruction": "validate their feelings"
  },
  "completion": "That sounds really challenging. I hear the frustration in what you're describing.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 3,
    "timestamp": "2026-04-25T10:28:00Z",
    "model": "claude-haiku-4-5-20251001",
    "feedback_type": "accepted"
  }
}
```

---

## 十、请确认

请确认以下设计决策：

1. **System Prompt重建**：从dialogue_dir配置文件读取？
2. **RLHF chosen来源**：使用transcript中的turn？
3. **Edited处理**：作为RLHF对（chosen=final, rejected=original）？
4. **输出格式**：默认JSONL？
5. **Metadata**：默认包含？
6. **实现优先级**：先实现Phase 1核心功能？

如有调整需求，请说明。
