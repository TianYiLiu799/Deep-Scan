"""Deep-Scan Dashboard — interactive Streamlit app combining analytics + web UI."""

import json
import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Deep-Scan | Python Intern Job Analytics",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Chinese font + chart style ────────────────────────────────────────────────
plt.rcParams.update({
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'sans-serif'],
    'axes.unicode_minus': False,
    'figure.dpi': 150,
    'savefig.dpi': 150,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

COLORS = ['#4C72B0', '#55A868', '#C44E52', '#8172B2', '#CCB974',
          '#64B5CD', '#8C8C8C', '#E8A735', '#6D904F', '#B07AA1']

DATA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'jobs_cleaned.json'

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #4C72B0, #55A868); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0; }
    .sub-header { color: #888; font-size: 0.95rem; margin-top: -0.5rem; }
    div[data-testid="stMetric"] { background: #f8f9fa; border-radius: 12px; padding: 16px; border: 1px solid #e8eaed; }
    div[data-testid="stMetric"] label { font-weight: 600; color: #555; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #4C72B0; font-size: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _data_mtime() -> float:
    """Return file mtime so cache busts when data changes."""
    return DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0.0


@st.cache_data(ttl=10)
def load_data(_mtime: float) -> pd.DataFrame:
    if not DATA_PATH.exists():
        st.error(f"数据文件未找到: {DATA_PATH}")
        return pd.DataFrame()
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def extract_degree(text: str) -> str:
    """Pull degree requirement keyword from a description string."""
    if not isinstance(text, str):
        return '未知'
    mapping = {'博士': '博士', '硕士': '硕士', '本科': '本科', '大专': '大专', '不限学历': '不限', '学历不限': '不限'}
    for key, label in mapping.items():
        if key in text:
            return label
    return '未注明'


def compute_avg_salary(row: pd.Series) -> float | None:
    mn = pd.to_numeric(row.get('salary_min'), errors='coerce')
    mx = pd.to_numeric(row.get('salary_max'), errors='coerce')
    if pd.notna(mn) and pd.notna(mx):
        return (mn + mx) / 2
    if pd.notna(mn):
        return mn
    if pd.notna(mx):
        return mx
    return None


# ── Chart builders ────────────────────────────────────────────────────────────

def build_tech_chart(df: pd.DataFrame) -> plt.Figure | None:
    if 'core_tech_stack' not in df.columns or df.empty:
        return None
    exploded = df['core_tech_stack'].explode().dropna()
    exploded = exploded[exploded.apply(lambda x: isinstance(x, str) and x.strip() != '')]
    if exploded.empty:
        return None
    counts = exploded.value_counts().head(10)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    palette = COLORS[:len(counts)][::-1]
    bars = ax.barh(range(len(counts)), counts.values, color=palette, height=0.6, edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va='center', fontsize=10, fontweight='bold')

    ax.set_yticks(range(len(counts)))
    ax.set_yticklabels(counts.index, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel('需求数量', fontsize=11)
    ax.set_title('Python 实习岗位技能需求 Top 10', fontsize=13, fontweight='bold', pad=12)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(left=False)
    fig.tight_layout()
    return fig


def build_salary_chart(df: pd.DataFrame) -> plt.Figure | None:
    if df.empty:
        return None
    avg = df['_avg_salary'].dropna()
    if avg.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 4.5))
    bins = min(20, max(8, len(avg) // 2))
    ax.hist(avg, bins=bins, color='#4C72B0', edgecolor='white', linewidth=0.8, alpha=0.85)

    mean_val = avg.mean()
    median_val = avg.median()
    ax.axvline(mean_val, color='#C44E52', linestyle='--', linewidth=2, label=f'均值: {mean_val:.0f} 元/天')
    ax.axvline(median_val, color='#55A868', linestyle='--', linewidth=2, label=f'中位数: {median_val:.0f} 元/天')

    ax.set_xlabel('日均薪资 (元/天)', fontsize=11)
    ax.set_ylabel('岗位数量', fontsize=11)
    ax.set_title('Python 实习岗位薪资分布', fontsize=13, fontweight='bold', pad=12)
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Header
    st.markdown('<p class="main-header">Deep-Scan  ·  Python 实习岗位分析看板</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">实时监控 Python 实习岗位需求趋势  ·  技能分布  ·  薪资水平</p>', unsafe_allow_html=True)
    st.divider()

    raw = load_data(_data_mtime())

    if raw.empty:
        st.info("暂无清洗后的数据。请先运行 scraper → parser → cleaner 流水线，生成 `data/jobs_cleaned.json`。", icon="ℹ️")
        st.stop()

    # Enrich
    df = raw.copy()
    df['_avg_salary'] = df.apply(compute_avg_salary, axis=1)
    if 'description' in df.columns:
        df['_degree'] = df['description'].apply(extract_degree)
    else:
        df['_degree'] = '未知'

    # ── Sidebar ────────────────────────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ 筛选条件")

    # Degree filter
    degree_options = sorted([d for d in df['_degree'].unique() if d != '未知'])
    if degree_options:
        selected_degrees = st.sidebar.multiselect(
            "学历要求", options=degree_options, default=degree_options,
            help="根据职位描述中的学历关键词筛选"
        )
    else:
        selected_degrees = degree_options  # keep all

    # Salary range filter
    valid_salary = df['_avg_salary'].dropna()
    if not valid_salary.empty:
        sal_min_val = int(valid_salary.min())
        sal_max_val = int(valid_salary.max()) + 1
        salary_range = st.sidebar.slider(
            "日均薪资范围 (元/天)",
            min_value=sal_min_val, max_value=sal_max_val,
            value=(sal_min_val, sal_max_val),
            step=10,
        )
    else:
        salary_range = (0, 99999)

    st.sidebar.divider()
    st.sidebar.caption(f"共 {len(raw)} 条原始记录")

    # ── Apply filters ──────────────────────────────────────────────────────
    mask = pd.Series(True, index=df.index)
    if selected_degrees:
        mask &= df['_degree'].isin(selected_degrees)
    mask &= df['_avg_salary'].between(salary_range[0], salary_range[1]) | df['_avg_salary'].isna()
    filtered = df[mask]

    # ── Top metrics ────────────────────────────────────────────────────────
    total = len(filtered)
    avg_sal = filtered['_avg_salary'].mean()
    avg_sal_str = f"{avg_sal:.0f} 元/天" if pd.notna(avg_sal) else "暂无数据"

    top_skill = "暂无"
    if 'core_tech_stack' in filtered.columns and not filtered.empty:
        exploded = filtered['core_tech_stack'].explode().dropna()
        exploded = exploded[exploded.apply(lambda x: isinstance(x, str) and x.strip() != '')]
        if not exploded.empty:
            top_skill = exploded.value_counts().index[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("📋 当前岗位数", total)
    c2.metric("💰 平均日薪", avg_sal_str)
    c3.metric("🏆 最热门技能", top_skill)

    st.divider()

    # ── Charts ─────────────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown("#### 📊 技能需求 Top 10")
        fig1 = build_tech_chart(filtered)
        if fig1:
            st.pyplot(fig1)
        else:
            st.info("暂无技能数据可展示")

    with right:
        st.markdown("#### 📈 薪资分布")
        fig2 = build_salary_chart(filtered)
        if fig2:
            st.pyplot(fig2)
        else:
            st.info("暂无薪资数据可展示")

    st.divider()

    # ── Data table ─────────────────────────────────────────────────────────
    st.markdown("#### 📝 原始清洗数据")

    display_cols = [c for c in ['title', 'company', '_avg_salary', '_degree', 'core_tech_stack', 'location', 'detail_url']
                    if c in filtered.columns]
    display_df = filtered[display_cols].copy()
    if '_avg_salary' in display_df.columns:
        display_df['_avg_salary'] = display_df['_avg_salary'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "-")

    st.dataframe(
        display_df.rename(columns={
            'title': '职位名称', 'company': '公司', '_avg_salary': '日均薪资',
            '_degree': '学历要求', 'core_tech_stack': '核心技术栈',
            'location': '工作地点', 'detail_url': '详情链接',
        }),
        use_container_width=True,
        height=400,
        hide_index=True,
    )


if __name__ == '__main__':
    main()
