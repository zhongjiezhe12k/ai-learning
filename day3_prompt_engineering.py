"""
Day 3 - Prompt 工程实战：结构化输出 + 思维链（CoT）

今天掌握三个核心技能：
  1. 角色设定 —— 用 system prompt 精准控制 AI 的行为和风格
  2. 结构化输出 —— 让 AI 返回 JSON，而不是自由文本
  3. 思维链（CoT）—— 让 AI 像人类一样「先思考，再回答」

这三个技能组合起来 = 你能让 AI 做任何你想要的格式和逻辑。
"""

import json

# API Key 已迁移到 .env → config.py（不再硬编码）
from config import client, MODEL, get_client
# 想切到 DeepSeek？取消下面注释：
# client, MODEL = get_client("deepseek")


# ============================================================
# 实验 1：角色设定 —— system prompt 就是 AI 的「人设」
# ============================================================
print("=" * 60)
print("实验 1：角色设定 —— 同一问题，三种人设，三种回答")
print("=" * 60)

# 三种不同的 system prompt，问同一个问题
personas = {
    "📋 严谨的资深工程师": (
        "你是一位有 15 年经验的资深软件工程师。回答问题时使用专业术语，"
        "注重最佳实践、性能和可维护性。语气正式、精确。"
    ),
    "🎨 热情的创业导师": (
        "你是一位充满激情的创业导师，说话风趣幽默，喜欢用比喻和故事来解释概念。"
        "你总是用「兄弟/姐妹」称呼对方，回复结尾爱发 emoji。"
    ),
    "⚡ 极简效率狂": (
        "你是一个极度追求效率的助手。回复永远不超过 3 句话。"
        "不要寒暄、不要客套、不要解释为什么——只给答案本身。"
    ),
}

question = "Python 中，list 和 tuple 有什么区别？"

for label, system_prompt in personas.items():
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
    )
    print(f"\n{label}：")
    print(f"   {r.choices[0].message.content}")

print("""
📌 关键认知：
   system prompt 不是「建议」—— AI 会非常认真地遵守它。
   你设定的角色、语气、规则，AI 都会尽力执行。
   这就是为什么同一个问题，不同的 system prompt 能产出完全不同的回答。
""")


# ============================================================
# 实验 2：结构化输出 —— 让 AI 返回 JSON
# ============================================================
print("=" * 60)
print("实验 2：结构化输出 —— 把 AI 的回复变成程序可读的数据")
print("=" * 60)
print("""
为什么要 JSON 输出？
  ❌ 自由文本："我认为这个候选人匹配度大概是 75 分左右吧..."
  ✅ JSON：     {"score": 75, "strengths": [...], "gaps": [...]}

JSON 输出可以直接被你的代码读取、计算、存储、展示。
这是「AI 应用开发」和「跟 AI 聊天」的分水岭。
""")

# ----------------------------------------------------------
# 2.1 基础版：直接在 prompt 里要求 JSON
# ----------------------------------------------------------
print("-" * 40)
print("2.1 基础版：prompt 里直接要 JSON")

jd_text = """
职位：Python 后端开发实习生
要求：熟悉 Python、Django/Flask、MySQL、Redis、Docker
加分：有 GitHub 开源项目、了解 AI/LLM API 调用
"""

resume_text = """
黄畅，嘉应学院软件工程 2027 届
技能：Python、Java、C、MySQL、Git
项目：校园二手交易平台（Django + MySQL）
"""

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "system",
            "content": (
                "你是一个专业的简历评估助手。"
                "你的输出必须是纯 JSON 格式，不要有任何其他文字。"
                "JSON 结构：{\"score\": 数字1-100, \"strengths\": [字符串数组], "
                "\"gaps\": [字符串数组], \"suggestion\": \"一句话建议\"}"
            ),
        },
        {
            "role": "user",
            "content": f"评估这份简历和 JD 的匹配度：\n\n=== JD ===\n{jd_text}\n=== 简历 ===\n{resume_text}",
        },
    ],
    temperature=0.1,  # 结构化输出用低温，保证稳定
)

raw = r.choices[0].message.content
print(f"\nAI 原始返回：\n{raw}")

# 关键步骤：解析 JSON，变成 Python 对象
try:
    result = json.loads(raw)
    print(f"\n✅ 解析成功！")
    print(f"   匹配度：{result['score']}/100")
    print(f"   优势：{', '.join(result['strengths'])}")
    print(f"   短板：{', '.join(result['gaps'])}")
    print(f"   建议：{result['suggestion']}")
except json.JSONDecodeError:
    print("❌ JSON 解析失败，AI 没有返回纯 JSON")


# ----------------------------------------------------------
# 2.2 进阶版：用 JSON Schema 精确约束输出结构
# ----------------------------------------------------------
print("\n" + "-" * 40)
print("2.2 进阶版：JSON Schema —— 更精确的约束")

# 当你需要复杂、嵌套的结构时，直接在 prompt 里写 JSON 示例
complex_prompt = """
你是一个课程评估专家。请严格按照下面的 JSON 格式输出，不要有任何其他文字：

{
  "course_name": "课程名称",
  "overall_score": 85,
  "dimensions": {
    "内容质量": {"score": 90, "comment": "评分理由"},
    "实践性":   {"score": 80, "comment": "评分理由"},
    "性价比":   {"score": 85, "comment": "评分理由"}
  },
  "pros": ["优点1", "优点2"],
  "cons": ["缺点1", "缺点2"],
  "verdict": "推荐 / 不推荐 / 观望"
}

请评估这门课：吴恩达《Machine Learning Specialization》Coursera
"""

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你只输出 JSON，没有任何额外文字。"},
        {"role": "user", "content": complex_prompt},
    ],
    temperature=0.1,
)

raw = r.choices[0].message.content
print(f"\nAI 返回：\n{raw}")

try:
    result = json.loads(raw)
    dims = result["dimensions"]
    print(f"\n✅ 解析成功！{result['course_name']}")
    print(f"   总分：{result['overall_score']}")
    for dim, detail in dims.items():
        print(f"   {dim}：{detail['score']}分 — {detail['comment']}")
    print(f"   结论：{result['verdict']}")
except json.JSONDecodeError:
    print("❌ JSON 解析失败")

print("""
📌 结构化输出的三个技巧：
   1. temperature 设低（0.0~0.2）→ 输出更稳定、格式更可靠
   2. system prompt 里明确写「纯 JSON，不要任何其他文字」
   3. 在 prompt 里给 JSON 示例 → AI 会照着你的结构填空
""")


# ============================================================
# 实验 3：思维链（Chain of Thought）—— 让 AI 先思考再回答
# ============================================================
print("=" * 60)
print("实验 3：思维链（CoT）—— 「先想清楚，再说答案」")
print("=" * 60)

# ----------------------------------------------------------
# 3.1 对比实验：直接回答 vs 思维链
# ----------------------------------------------------------
print("\n" + "-" * 40)
print("3.1 直接回答（没有 CoT）")

hard_question = "一个房间里有 3 个灯泡和 3 个开关。你只能在房间外操作开关，只能进房间一次。如何确定哪个开关控制哪个灯泡？"

r = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": hard_question}],
    temperature=0.0,
)
print(f"\n❌ 没有 CoT 的回答：\n{r.choices[0].message.content}")

print("\n" + "-" * 40)
print("3.2 思维链回答（加了 CoT 提示）")

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": f"{hard_question}\n\n请一步一步思考，先分析问题，再给出答案。格式：\n【分析】...\n【推理步骤】...\n【最终答案】...",
        },
    ],
    temperature=0.0,
)
print(f"\n✅ 有 CoT 的回答：\n{r.choices[0].message.content}")

# ----------------------------------------------------------
# 3.2 CoT 实战：让 AI 分析一段代码
# ----------------------------------------------------------
print("\n" + "-" * 40)
print("3.3 CoT 实战：代码审查")

buggy_code = """
def find_max(nums):
    max_num = 0
    for n in nums:
        if n > max_num:
            max_num = n
    return max_num

def calculate_average(scores):
    total = 0
    for s in scores:
        total += s
    return total / len(scores)

def process_data(data):
    results = {}
    for item in data:
        name = item["name"]
        value = item["value"] * 2
        results[name] = value
    return results
"""

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {
            "role": "system",
            "content": (
                "你是一个资深的代码审查专家。分析代码时，请按照以下步骤思考：\n"
                "1. 逐函数阅读，理解其意图\n"
                "2. 找出潜在 bug 或边界条件问题\n"
                "3. 给出修复建议\n"
                "请在【分析过程】中展示你的推理，在【结论】中汇总所有问题。"
            ),
        },
        {
            "role": "user",
            "content": f"请审查这段代码：\n```python\n{buggy_code}\n```",
        },
    ],
    temperature=0.2,
)
print(f"\n{r.choices[0].message.content}")

print("""
📌 思维链（CoT）的核心技巧：
   1. 在 prompt 末尾加「请一步一步思考」—— 最简单的 CoT 触发词
   2. 指定思考结构：先分析 → 再推理 → 最后结论
   3. 在 system prompt 里定义推理步骤，AI 会严格遵守
   4. CoT 在数学、逻辑、代码审查、复杂决策场景提升明显
""")


# ============================================================
# 实验 4：综合实战 —— 可复用的 Prompt 模板
# ============================================================
print("=" * 60)
print("实验 4：综合实战 —— 一个可复用的 Prompt 模板")
print("=" * 60)
print("""
下面这个模板结合了 Day 3 的三个核心技能：
  ✅ 角色设定（system prompt 定义专家人设）
  ✅ 结构化输出（JSON 格式，可直接被代码消费）
  ✅ 思维链（让 AI 先分析再打分）
""")

# 这就是一个「可复用的 Prompt 模板」
EVALUATION_TEMPLATE = """
你是一个资深的 {role} 招聘专家，拥有 10 年以上的技术招聘经验。

## 你的任务
根据下面的 JD（职位描述）和候选人简历，评估匹配度。

## 评估步骤（请严格按顺序思考）
1. 【关键词提取】从 JD 中提取核心要求和加分项
2. 【逐项对比】将简历中的技能/经验与每一项要求对比
3. 【差距分析】找出简历中没有覆盖到的要求
4. 【综合评分】基于以上分析给出 1-100 的分数

## 输出格式（必须是纯 JSON，不要任何其他文字）
{{
  "match_score": 数字,
  "level": "strong_match / potential / not_recommended",
  "keyword_analysis": {{
    "matched": ["匹配的技能"],
    "partial": ["部分匹配的技能"],
    "missing": ["缺失的技能"]
  }},
  "strengths": ["候选人的 3 个核心优势"],
  "improvement_areas": ["最重要的 3 个改进方向"],
  "verdict": "一句话总结，不超过 50 字"
}}

---

【JD】
{jd}

【简历】
{resume}
"""

# 用模板填充
filled_prompt = EVALUATION_TEMPLATE.format(
    role="Python 后端开发",
    jd="""
Python 后端开发实习生
要求：Python、Django/Flask、MySQL、Redis、Docker、Git
加分：有 GitHub 开源项目、了解 AI/LLM API 调用、有 CI/CD 经验
""",
    resume="""
黄畅，嘉应学院软件工程 2027 届
技能：Python、Java、C、MySQL、Git、Linux 基础
项目：校园二手交易平台（Django + MySQL + Docker 部署）
证书：英语四级
""",
)

r = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你只输出 JSON，没有任何额外文字。严格遵循用户指定的 JSON 格式。"},
        {"role": "user", "content": filled_prompt},
    ],
    temperature=0.1,
)

raw = r.choices[0].message.content
print(f"\nAI 原始返回：\n{raw}\n")

try:
    result = json.loads(raw)
    print("✅ 结构化解析结果：")
    print(f"   匹配度：{result['match_score']}/100")
    print(f"   等级：{result['level']}")
    print(f"   匹配技能：{', '.join(result['keyword_analysis']['matched'])}")
    print(f"   部分匹配：{', '.join(result['keyword_analysis']['partial'])}")
    print(f"   缺失技能：{', '.join(result['keyword_analysis']['missing'])}")
    print(f"   优势：{'; '.join(result['strengths'])}")
    print(f"   改进方向：{'; '.join(result['improvement_areas'])}")
    print(f"   结论：{result['verdict']}")
except json.JSONDecodeError as e:
    print(f"❌ JSON 解析失败：{e}")
    print("💡 如果 AI 没返回纯 JSON，尝试：换 qwen-max 模型，或者把 temperature 设成 0")


# ============================================================
# 课后练习
# ============================================================
print("\n" + "=" * 60)
print("📝 Day 3 总结：你今天掌握了什么？")
print("=" * 60)
print("""
   ✅ 角色设定     → system prompt 定义 AI 的身份、语气、规则
   ✅ 结构化输出   → 让 AI 返回 JSON，程序可以直接 parse
   ✅ 思维链 CoT   → 让 AI 展示推理过程，答案更准、更可解释
   ✅ 三者组合     → 一个 prompt 同时用上三种技术，威力翻倍

🎯 你已经会写「能用的 AI 应用」了，不只是「跟 AI 聊天」

🔜 Day 4-6 预告：AI 简历分析器
   用今天学的 JSON 输出 + 明天的 Streamlit = 第一个有 UI 的 AI 应用！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛠️ 课后作业（选做）

  1. 改 EVALUATION_TEMPLATE 里的 role，换成「前端开发」试试
  2. 给实验 3.1 的灯泡问题用 DeepSeek 跑一遍，对比两个模型的推理
  3. 自己设计一个 JSON 输出结构，让 AI 帮你分析任意一段文字的情感
  4. 把 EVALUATION_TEMPLATE 保存成独立的 prompt 文件，以后复用

💡 提示：temperature 调试小技巧
   - JSON 输出不稳定？→ temperature 降到 0.0，换 qwen-max
   - 答案太死板？→ temperature 升到 0.5~0.7
   - CoT 推理不够深？→ 在 system prompt 里加「请深度思考每一步」
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


# ============================================================
# Bonus：零-shot CoT vs Few-shot CoT
# ============================================================
print("=" * 60)
print("🎁 Bonus：零样本 CoT vs 少样本 CoT")
print("=" * 60)
print("""
两种 CoT 策略：

零样本 CoT（Zero-shot CoT）：
  只加一句「Let's think step by step」→ 不需要给例子
  适用：通用问题、逻辑推理、大部分场景

少样本 CoT（Few-shot CoT）：
  在 prompt 里给 1-3 个「问题 → 推理过程 → 答案」的完整示例
  AI 会模仿你的推理模式
  适用：格式要求严格、领域专业化、需要特定推理路径

Day 3 我们用的是零样本 CoT——最简单也最常用。
当你需要非常特定的输出格式时，可以考虑少样本 CoT。
""")
