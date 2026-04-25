# 训练数据导出设计（最终版）

## 一、核心原则

### SFT数据
- **数据源**：transcript.jsonl（最终对话内容）
- **用途**：监督学习，学习正确的回复
- **包含**：所有被接受或编辑后的turns

### RLHF数据
- **数据源**：transcript.jsonl + draft-history.jsonl
- **用途**：偏好学习，学习好坏对比
- **包含**：chosen（transcript）vs rejected（draft-history）
- **预留**：feedback_label字段用于结构化标签

---

## 二、数据格式

### 2.1 SFT格式

```json
{
  "prompt": {
    "system": "You are a professional therapist...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."},
      {"role": "assistant", "content": "[THERAPIST]: Tell me more..."}
    ],
    "instruction": "validate their feelings"
  },
  "completion": "That sounds really challenging. I hear the frustration in what you're describing.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "turn_id": "uuid",
    "timestamp": "2026-04-25T10:30:00Z",
    "source": "accepted",  // "accepted" or "edited"
    "model": "claude-haiku-4-5-20251001"
  }
}
```

**构建逻辑**：
1. 遍历transcript.jsonl中的所有turns
2. 过滤出agent生成的turns（source = "agent_accept" or "agent_edit"）
3. 通过draft_id找到对应的draft，获取source_instruction
4. 重建conversation_window（当前turn之前的对话历史）
5. 组装为SFT样本

### 2.2 RLHF格式

```json
{
  "prompt": {
    "system": "You are a professional therapist...",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."}
    ],
    "instruction": "explore their anxiety"
  },
  "chosen": "Can you help me understand what specifically triggers this anxiety?",
  "rejected": "Let's talk about your childhood experiences with failure.",
  "feedback_label": null,  // 预留字段，用于结构化标签
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "chosen_source": "accepted",  // "accepted" or "edited"
    "rejected_draft_id": "uuid",
    "rejection_reason": "too directive, jumped to conclusions",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

**构建逻辑**：
1. 遍历draft-history.jsonl中的rejected drafts
2. 找到同一turn_number的transcript turn作为chosen
3. 如果没有对应的transcript turn，跳过（说明最终没有提交任何内容）
4. 重建conversation_window
5. 组装为RLHF样本

**特殊情况 - Edited drafts**：
```json
{
  "prompt": {...},
  "chosen": "That sounds really challenging. I hear the frustration.",  // final_content
  "rejected": "That sounds difficult.",  // original draft
  "feedback_label": null,
  "metadata": {
    "chosen_source": "edited",
    "rejection_reason": "too brief, lacks empathy"
  }
}
```

---

## 三、数据关联逻辑

### 3.1 Turn和Draft的关联

**transcript.jsonl中的turn**：
```json
{
  "id": "turn_uuid",
  "speaker": "therapist",
  "source": "agent_accept",  // or "agent_edit"
  "content": "...",
  "draft_id": "draft_uuid",  // 关联到draft
  "original_draft": "...",  // 如果是edited，这里是原始draft
  "timestamp": "..."
}
```

**draft-history.jsonl中的draft**：
```json
{
  "id": "draft_uuid",
  "speaker": "therapist",
  "content": "...",
  "source_instruction": "explore their anxiety",
  "outcome": "rejected",  // or "accepted", "edited"
  "final_content": "...",  // 如果是edited
  "conversation_window": {"start_turn": 0, "end_turn": 4},
  "timestamp": "..."
}
```

### 3.2 匹配策略

**SFT数据**：
```python
for turn in transcript:
    if turn.source in ["agent_accept", "agent_edit"]:
        draft = find_draft_by_id(turn.draft_id)
        if draft:
            sft_sample = {
                "prompt": build_prompt(turn, draft),
                "completion": turn.content,
                "metadata": {...}
            }
```

**RLHF数据**：
```python
for draft in draft_history:
    if draft.outcome == "rejected":
        # 找到同一turn的accepted/edited turn
        turn = find_turn_by_turn_number(draft.turn_number)
        if turn:
            rlhf_sample = {
                "prompt": build_prompt(turn, draft),
                "chosen": turn.content,
                "rejected": draft.content,
                "feedback_label": None,
                "metadata": {...}
            }
    elif draft.outcome == "edited":
        # edited也可以作为RLHF对
        rlhf_sample = {
            "prompt": build_prompt(draft),
            "chosen": draft.final_content,
            "rejected": draft.content,
            "feedback_label": None,
            "metadata": {...}
        }
```

---

## 四、Feedback Label设计

### 4.1 预留字段

```json
{
  "feedback_label": null,  // 当前为null，未来可以是字符串或数组
  "metadata": {
    "rejection_reason": "too directive, jumped to conclusions"  // 原始文本
  }
}
```

### 4.2 未来扩展

**结构化标签示例**：
```json
{
  "feedback_label": "too_directive",  // 单个标签
  // 或
  "feedback_label": ["too_directive", "jumped_to_conclusions"],  // 多个标签
  // 或
  "feedback_label": {
    "category": "technique_error",
    "subcategory": "premature_interpretation",
    "severity": "high"
  }
}
```

**标签分类建议**：
- `too_directive` - 过于指导性
- `jumped_to_conclusions` - 过早下结论
- `lacks_empathy` - 缺乏共情
- `too_brief` - 过于简短
- `off_topic` - 偏离主题
- `inappropriate_technique` - 技术使用不当
- `poor_timing` - 时机不当

---

## 五、Context重建

### 5.1 System Prompt

**简化版本**（推荐）：
```python
def build_system_prompt(side: str) -> str:
    other = "client" if side == "therapist" else "therapist"
    return (
        f"You are the {side} in a structured therapeutic dialogue "
        f"with a {other}. A human controller directs you via brief instructions."
    )
```

**完整版本**（可选）：
```python
def build_system_prompt(dialogue_dir: Path, side: str) -> str:
    # 读取配置文件
    side_md = dialogue_dir / side / f"{side.upper()}.md"
    if side_md.exists():
        return side_md.read_text()
    else:
        return build_simple_system_prompt(side)
```

### 5.2 Messages重建

**基于conversation_window**：
```python
def build_messages(turn: Turn, transcript: list[Turn]) -> list[dict]:
    # 找到当前turn在transcript中的位置
    turn_index = transcript.index(turn)
    
    # 取前N个turns作为context（例如6个）
    window_size = 6
    start_index = max(0, turn_index - window_size)
    context_turns = transcript[start_index:turn_index]
    
    messages = []
    for t in context_turns:
        role = "assistant" if t.speaker == turn.speaker else "user"
        messages.append({
            "role": role,
            "content": f"[{t.speaker.upper()}]: {t.content}"
        })
    
    return messages
```

**基于draft的conversation_window**：
```python
def build_messages_from_draft(draft: Draft, transcript: list[Turn]) -> list[dict]:
    if draft.conversation_window:
        start = draft.conversation_window["start_turn"]
        end = draft.conversation_window["end_turn"]
        context_turns = transcript[start:end+1]
    else:
        # 如果没有conversation_window，使用默认窗口
        context_turns = transcript[-6:]
    
    messages = [...]
    return messages
```

---

## 六、CLI命令

### 6.1 基本命令

```bash
# 导出SFT数据
empathy export session_001 --format sft --output training_data/

# 导出RLHF数据
empathy export session_001 --format rlhf --output training_data/

# 同时导出两种格式
empathy export session_001 --format sft,rlhf --output training_data/
```

### 6.2 高级选项

```bash
# 预览（不写入文件）
empathy export session_001 --format rlhf --preview

# 只包含rejected（RLHF）
empathy export session_001 --format rlhf --include rejected

# 包含rejected和edited（RLHF）
empathy export session_001 --format rlhf --include rejected,edited

# 批量导出
empathy export --all --format sft,rlhf --output training_data/
```

### 6.3 输出文件

```
training_data/
├── session_001_sft.jsonl       # SFT数据
├── session_001_rlhf.jsonl      # RLHF数据
└── session_001_stats.json      # 统计信息
```

**stats.json示例**：
```json
{
  "dialogue_id": "session_001",
  "sft_samples": 25,
  "rlhf_samples": 10,
  "rejected_drafts": 8,
  "edited_drafts": 2,
  "total_turns": 30,
  "export_timestamp": "2026-04-25T10:30:00Z"
}
```

---

## 七、实现计划

### Phase 1：核心功能
1. **TrainingDataExporter类**
   - `load_data()` - 加载transcript和draft-history
   - `build_sft_samples()` - 构建SFT样本
   - `build_rlhf_samples()` - 构建RLHF样本
   - `export()` - 导出到文件

2. **Context重建**
   - `build_system_prompt()` - 简化版system prompt
   - `build_messages()` - 基于conversation_window重建messages

3. **CLI命令**
   - `empathy export` - 基本导出命令
   - 支持 `--format sft/rlhf`
   - 支持 `--output` 指定输出路径

### Phase 2：增强功能
1. 批量导出（`--all`）
2. 预览功能（`--preview`）
3. 过滤选项（`--include`）
4. 统计报告（stats.json）

### Phase 3：高级功能
1. 完整版system prompt重建
2. 质量控制和验证
3. Feedback label结构化
4. 自动导出配置

---

## 八、示例输出

### 8.1 SFT样本

```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue with a client. A human controller directs you via brief instructions.",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling really anxious lately, especially before big meetings."},
      {"role": "assistant", "content": "[THERAPIST]: Thank you for sharing that. Can you tell me more about what happens when you feel this anxiety?"}
    ],
    "instruction": "validate their feelings"
  },
  "completion": "That sounds really challenging. I hear the frustration in what you're describing.",
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 3,
    "turn_id": "turn_uuid_003",
    "timestamp": "2026-04-25T10:28:00Z",
    "source": "accepted",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

### 8.2 RLHF样本（rejected）

```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue with a client. A human controller directs you via brief instructions.",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling really anxious lately."},
      {"role": "assistant", "content": "[THERAPIST]: Thank you for sharing that."},
      {"role": "user", "content": "[CLIENT]: My heart races and I start thinking everyone will judge me."}
    ],
    "instruction": "explore the catastrophizing pattern"
  },
  "chosen": "I notice you mentioned thinking everyone will judge you. What evidence do you have for that thought?",
  "rejected": "Let's talk about your childhood experiences with failure and how they might relate to this.",
  "feedback_label": null,
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 5,
    "timestamp": "2026-04-25T10:30:00Z",
    "chosen_source": "accepted",
    "rejected_draft_id": "draft_uuid_005",
    "rejection_reason": "too directive, jumped to conclusions without exploring current experience",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

### 8.3 RLHF样本（edited）

```json
{
  "prompt": {
    "system": "You are the therapist in a structured therapeutic dialogue with a client. A human controller directs you via brief instructions.",
    "messages": [
      {"role": "user", "content": "[CLIENT]: I've been feeling anxious..."}
    ],
    "instruction": "validate their feelings"
  },
  "chosen": "That sounds really challenging. I hear the frustration in what you're describing.",
  "rejected": "That sounds difficult.",
  "feedback_label": null,
  "metadata": {
    "dialogue_id": "session_001",
    "turn_number": 3,
    "timestamp": "2026-04-25T10:28:00Z",
    "chosen_source": "edited",
    "rejected_draft_id": "draft_uuid_003",
    "rejection_reason": "too brief, lacks empathy",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

---

## 九、关键设计决策

### ✅ 已确认

1. **SFT数据源**：transcript.jsonl（最终对话内容）
2. **RLHF数据源**：transcript.jsonl + draft-history.jsonl
3. **Feedback label**：预留null字段，未来可扩展
4. **输出格式**：JSONL（每行一个对象）
5. **Metadata**：默认包含
6. **System prompt**：简化版本（Phase 1），完整版本（Phase 3）
7. **Context重建**：基于conversation_window或默认窗口大小

### 📋 待实现

1. TrainingDataExporter类
2. CLI export命令
3. 测试和验证
4. 文档更新

---

## 十、下一步

确认此设计后，将开始实现：
1. `empathy/utils/export.py` - TrainingDataExporter类
2. `empathy/cli/main.py` - export命令
3. 单元测试
4. 集成测试

是否开始实现？
