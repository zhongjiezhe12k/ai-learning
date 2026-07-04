"""
Day 4 - AI 简历分析器（CLI 版）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
你的第一个 AI 应用：输入 JD + 简历 → AI 输出匹配度评分和改进建议

Day 1-3 学到的技能全部用上：
  ✅ API 调用（Day 1）
  ✅ 消息角色 + Temperature 控制（Day 2）
  ✅ 结构化 JSON 输出（Day 3）
  ✅ 思维链 CoT 推理（Day 3）

用法：
  python day4_resume_analyzer.py                    # 交互式输入 JD
  python day4_resume_analyzer.py --jd jd.txt        # 从文件读取 JD
  python day4_resume_analyzer.py --demo             # 用内置示例 JD 演示
"""
from ai_utils import chat_with_retry, MODEL
import json
import sys
import os

# API Key 已迁移到 .env → config.py（不再硬编码）
# 想切到 DeepSeek？修改 config.py 中的默认平台，或用 get_client("deepseek")


# ============================================================
# 你的简历（⚠️ 随时改这里，改成你自己的真实信息）
# ============================================================
MY_RESUME = """
## 黄畅

### 教育背景
- 嘉应学院 · 软件工程 · 本科 · 2027 届

### 技术技能
- 编程语言：Python、Java、C
- 后端框架：Django
- 数据库：MySQL、Redis（基础）
- 工具：Git、Docker（基础）、Linux 命令行
- 其他：数据结构与算法、面向对象编程

### 项目经历
1. **校园二手交易平台** | Django + MySQL + Docker
   - 独立完成全栈开发，实现用户注册/登录、商品发布/搜索、在线聊天
   - 使用 Docker 容器化部署，MySQL 存储商品和用户数据
   - 日活用户 200+，累计交易 500+ 单

2. **学生成绩管理系统** | Python + Tkinter + SQLite
   - 开发桌面 GUI 应用，支持成绩录入、查询、统计和报表导出
   - 使用 SQLite 本地数据库，无需额外安装

### 证书
- 英语 CET-4
"""

# ============================================================
# 演示用 JD（--demo 模式用）
# ============================================================
DEMO_JD = """
Python 后端开发实习生

岗位职责：
1. 参与后端 API 的设计与开发，使用 Python 技术栈
2. 维护和优化现有数据库查询性能
3. 编写单元测试，保证代码质量
4. 参与 code review，与团队协作

任职要求：
1. 计算机相关专业本科在读，2026/2027 届毕业生
2. 熟悉 Python，了解 Django 或 Flask 等 Web 框架
3. 熟悉关系型数据库（MySQL/PostgreSQL）
4. 了解 Git 版本控制和 Linux 基本操作
5. 有实际项目经验者优先

加分项：
- 了解 Redis 缓存
- 了解 Docker 容器化
- 有 GitHub 开源贡献
- 了解 AI/LLM API 调用
"""


# ============================================================
# 核心：评估 Prompt 模板（Day 3 的技能组合实战）
# ============================================================
SYSTEM_PROMPT = """你是一个资深的技术招聘专家，拥有 10 年以上的软件工程师招聘经验。
你擅长快速评估候选人与职位的匹配度，给出客观、精准的分析。

## 评估流程（严格按顺序）
1. 【JD 拆解】提取 JD 中的「硬性要求」「核心要求」「加分项」
2. 【逐项对照】将简历技能与每一项要求对比，标记：✅ 满足 / ⚠️ 部分满足 / ❌ 缺失
3. 【深度分析】分析候选人优势和风险点
4. 【综合打分】基于匹配度给出 1-100 的分数

## 打分标准
- 90-100：几乎完美匹配，硬性要求全部满足，加分项命中 70%+
- 75-89：强匹配，核心要求满足，有少量可补的差距
- 60-74：基本匹配，有明确的成长空间
- 40-59：勉强匹配，有多项关键要求不满足
- 0-39：不推荐，核心要求大量缺失

## 输出格式（必须是纯 JSON，不要任何额外文字）
{
  "match_score": 数字(1-100),
  "level": "strong_match / potential / reach / not_recommended",
  "summary": "一句话总结（不超过 50 字）",
  "jd_breakdown": {
    "must_have": ["硬性要求列表"],
    "nice_to_have": ["加分项列表"]
  },
  "skill_matrix": [
    {"requirement": "要求", "status": "matched / partial / missing", "evidence": "简历中的证据"}
  ],
  "strengths": ["候选人的 3 个核心优势"],
  "gaps": ["最重要的 3 个差距"],
  "improvement_plan": ["3 条可操作的改进建议"],
  "cover_letter_hint": "一句话，可以作为求职信的核心卖点"
}"""


def analyze(jd_text: str, resume_text: str) -> dict:
    """核心函数：调用 AI 分析 JD 和简历的匹配度（带自动重试）"""
    print("\n🔍 正在分析...", end="", flush=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【JD】\n{jd_text}\n\n【简历】\n{resume_text}"},
    ]

    # 用 Day 5 的 chat_with_retry 替代原来的 client.chat.completions.create
    # 好处：网络抖动自动重试，错误不崩溃
    raw = chat_with_retry(messages, model=MODEL, temperature=0.1, max_retries=3)

    if raw is None:
        raise RuntimeError("API 调用失败：重试 3 次后仍然无法连接，请检查网络或 API Key")

    print(" 完成！")

    # 清洗：AI 偶尔会在 JSON 外面包 ```json ... ```，去掉
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]  # 去掉第一行 ```json
        if raw.endswith("```"):
            raw = raw[:-3]  # 去掉末尾 ```

    return json.loads(raw)


def print_report(result: dict):
    """把 JSON 结果渲染成可读的报告"""
    print()
    print("=" * 60)
    print("  📊 简历匹配度分析报告")
    print("=" * 60)

    # 分数和等级
    score = result["match_score"]
    level_emoji = {
        "strong_match": "🟢",
        "potential": "🟡",
        "reach": "🟠",
        "not_recommended": "🔴",
    }
    emoji = level_emoji.get(result["level"], "⚪")

    print(f"""
  {emoji} 匹配度：{score}/100  ({result['level']})
  📝 {result['summary']}
""")

    # 技能矩阵
    print("  ┌─ 技能逐项对照 ─────────────────────────────────┐")
    for item in result["skill_matrix"]:
        icon = {"matched": "✅", "partial": "⚠️", "missing": "❌"}.get(
            item["status"], "⚪"
        )
        print(f"  │ {icon} {item['requirement']}")
        print(f"  │   → {item['evidence']}")
    print("  └─────────────────────────────────────────────────┘")

    # JD 拆解
    print(f"\n  📋 JD 硬性要求：{', '.join(result['jd_breakdown']['must_have'])}")
    print(f"  ⭐ 加分项：{', '.join(result['jd_breakdown']['nice_to_have'])}")

    # 优势
    print("\n  💪 核心优势：")
    for i, s in enumerate(result["strengths"], 1):
        print(f"     {i}. {s}")

    # 差距
    print("\n  ⚠️  主要差距：")
    for i, g in enumerate(result["gaps"], 1):
        print(f"     {i}. {g}")

    # 改进计划
    print("\n  🎯 改进建议：")
    for i, p in enumerate(result["improvement_plan"], 1):
        print(f"     {i}. {p}")

    # 求职信提示
    print(f"\n  ✉️  求职信核心卖点：{result['cover_letter_hint']}")
    print("\n" + "=" * 60)

    return score


# ============================================================
# 交互式：多 JD 批量对比
# ============================================================
def batch_compare(jds: list[str], resume: str):
    """一次分析多个 JD，横向对比"""
    results = []
    for i, jd in enumerate(jds):
        print(f"\n{'─' * 40}")
        print(f"📋 JD #{i+1}")
        try:
            result = analyze(jd, resume)
            results.append(result)
            print_report(result)
        except Exception as e:
            print(f"❌ 分析失败：{e}")
    return results


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("  🤖 AI 简历分析器 — Day 4")
    print("  输入 JD，给匹配度评分 + 逐项分析 + 改进建议")
    print("=" * 60)

    # 解析命令行参数
    args = sys.argv[1:]

    if "--demo" in args:
        # 演示模式：用内置 JD
        print("\n📋 使用内置演示 JD：")
        print(DEMO_JD.strip())
        result = analyze(DEMO_JD, MY_RESUME)
        print_report(result)
        return

    if "--jd" in args:
        # 从文件读取 JD
        idx = args.index("--jd")
        if idx + 1 < len(args):
            jd_path = args[idx + 1]
            if not os.path.exists(jd_path):
                print(f"❌ 文件不存在：{jd_path}")
                sys.exit(1)
            with open(jd_path, "r", encoding="utf-8") as f:
                jd_text = f.read()
            print(f"\n📋 从文件读取 JD：{jd_path}")
        else:
            print("❌ --jd 需要指定文件路径，例如：python day4_resume_analyzer.py --jd jd.txt")
            sys.exit(1)
    else:
        # 交互模式：粘贴 JD
        print("\n📋 请粘贴 JD（职位描述），输入完成后按 Ctrl+Z 再按回车（或直接回车开始分析）：")
        print("   （提示：也可以运行 python day4_resume_analyzer.py --demo 看演示）\n")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        jd_text = "\n".join(lines).strip()
        if not jd_text:
            print("❌ 没有输入 JD，使用 --demo 看演示")
            sys.exit(1)

    # 分析
    try:
        result = analyze(jd_text, MY_RESUME)
        print_report(result)
    except json.JSONDecodeError as e:
        print(f"\n❌ AI 返回的不是纯 JSON，解析失败：{e}")
        print("💡 试试换 qwen-max 模型，或者把 temperature 降到 0")
    except Exception as e:
        print(f"\n❌ 出错：{e}")

if __name__ == "__main__":
    main()
