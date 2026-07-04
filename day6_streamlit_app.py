"""
Day 6 - AI 简历分析器 · Streamlit Web 版
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
你的第一个有 UI 的 AI 应用！

技术栈：Streamlit（纯 Python，零 HTML/CSS/JS）+ ai_utils（Day 5 的重试模块）

启动方式：
  streamlit run day6_streamlit_app.py

启动后在浏览器打开 http://localhost:8501
"""

import streamlit as st
import json
from ai_utils import chat_with_retry, MODEL

# ============================================================
# 页面设置
# ============================================================
st.set_page_config(
    page_title="AI 简历分析器",
    page_icon="📊",
    layout="wide",
)

# ============================================================
# 评估 Prompt（和 Day 4 一样，挪到了这里）
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


# ============================================================
# 分析函数（和 Day 4 一样，只是改用 chat_with_retry）
# ============================================================
def analyze(jd_text: str, resume_text: str) -> dict | None:
    """调用 AI 分析 JD 和简历的匹配度"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【JD】\n{jd_text}\n\n【简历】\n{resume_text}"},
    ]
    raw = chat_with_retry(messages, model=MODEL, temperature=0.1, max_retries=3)
    if raw is None:
        return None

    # 清洗 JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

    return json.loads(raw)


# ============================================================
# UI 渲染
# ============================================================
# ── 标题 ──
st.title("📊 AI 简历分析器")
st.caption("粘贴 JD + 简历 → AI 输出匹配度评分 + 逐项分析 + 改进建议")

# ── 双栏布局：左边 JD，右边简历 ──
col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 职位描述（JD）")
    jd_input = st.text_area(
        "JD",
        placeholder="在这里粘贴职位描述...\n\n例如：Python 后端开发实习生\n要求：Python、Django、MySQL...",
        height=300,
        label_visibility="collapsed",
        key="jd",
    )

with col2:
    st.subheader("📝 你的简历")
    default_resume = """## 黄畅
### 教育背景
- 嘉应学院 · 软件工程 · 本科 · 2027 届

### 技术技能
- 编程语言：Python、Java、C
- 后端框架：Django
- 数据库：MySQL、Redis（基础）
- 工具：Git、Docker（基础）、Linux 命令行

### 项目经历
1. **校园二手交易平台** | Django + MySQL + Docker
   - 独立全栈开发，日活 200+，累计交易 500+ 单
   - Docker 容器化部署

2. **学生成绩管理系统** | Python + Tkinter + SQLite"""
    resume_input = st.text_area(
        "简历",
        value=default_resume,
        height=300,
        label_visibility="collapsed",
        key="resume",
    )

# ── 分析按钮 ──
analyze_btn = st.button("🔍 开始分析", type="primary", use_container_width=True)

# ── 底部提示 ──
st.caption("💡 提示：先改右边简历为自己的真实信息，左边贴 JD，点分析。JD 和简历都可以随时编辑。")


# ============================================================
# 分析逻辑 + 结果展示
# ============================================================
if analyze_btn:
    if not jd_input.strip():
        st.warning("⚠️ 请先粘贴 JD（职位描述）")
    elif not resume_input.strip():
        st.warning("⚠️ 请先填写简历")
    else:
        with st.spinner("🔍 AI 正在分析中..."):
            result = analyze(jd_input, resume_input)

        if result is None:
            st.error("❌ 分析失败：API 调用出错，请检查网络或 API Key")
        else:
            st.success("✅ 分析完成！")
            st.divider()

            # ── 第一行：分数卡片 ──
            col_score, col_level, col_summary = st.columns([1, 1, 3])

            score = result["match_score"]
            # 根据分数选颜色
            if score >= 80:
                color = "#22c55e"  # 绿色
            elif score >= 60:
                color = "#f59e0b"  # 黄色
            else:
                color = "#ef4444"  # 红色

            level_label = {
                "strong_match": "🟢 强匹配",
                "potential": "🟡 有潜力",
                "reach": "🟠 勉强匹配",
                "not_recommended": "🔴 不推荐",
            }.get(result["level"], result["level"])

            with col_score:
                st.metric("匹配度", f"{score}/100")
            with col_level:
                st.metric("评级", level_label)
            with col_summary:
                st.info(f"📝 {result['summary']}")

            st.divider()

            # ── 第二行：技能矩阵 ──
            st.subheader("🔍 技能逐项对照")
            matrix_data = []
            for item in result["skill_matrix"]:
                icon = {"matched": "✅", "partial": "⚠️", "missing": "❌"}.get(
                    item["status"], "⚪"
                )
                matrix_data.append(
                    {
                        "状态": icon,
                        "要求": item["requirement"],
                        "证据": item["evidence"],
                    }
                )
            st.dataframe(matrix_data, use_container_width=True, hide_index=True)

            # ── 第三行：优势 / 差距 / 改进 ──
            col_str, col_gap, col_plan = st.columns(3)

            with col_str:
                st.subheader("💪 核心优势")
                for s in result["strengths"]:
                    st.markdown(f"- {s}")

            with col_gap:
                st.subheader("⚠️ 主要差距")
                for g in result["gaps"]:
                    st.markdown(f"- {g}")

            with col_plan:
                st.subheader("🎯 改进建议")
                for i, p in enumerate(result["improvement_plan"], 1):
                    st.markdown(f"{i}. {p}")

            # ── 求职信提示 ──
            st.divider()
            st.subheader("✉️ 求职信核心卖点")
            st.success(result["cover_letter_hint"])

            # ── 原始 JSON（折叠） ──
            with st.expander("🔧 查看原始 JSON"):
                st.json(result)
