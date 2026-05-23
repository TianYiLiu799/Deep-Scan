"""Data analytics module for Deep-Scan project.

Loads cleaned job data, generates tech stack rankings and salary distribution charts.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

logger = logging.getLogger(__name__)

# ── Chart style & Chinese font ──────────────────────────────────────────────
plt.rcParams.update({
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'sans-serif'],
    'axes.unicode_minus': False,
    'figure.dpi': 150,
    'savefig.dpi': 150,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

STYLE_COLORS = ['#4C72B0', '#55A868', '#C44E52', '#8172B2', '#CCB974',
                '#64B5CD', '#8C8C8C', '#E8A735', '#6D904F', '#B07AA1']


class JobAnalyzer:
    """Analyze cleaned job data and produce visual reports."""

    def __init__(self, data_path: str = 'data/jobs_cleaned.json',
                 output_dir: str = 'data/charts'):
        self.data_path = Path(data_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.df: Optional[pd.DataFrame] = None

    def load(self) -> pd.DataFrame:
        """Load cleaned JSON into a DataFrame."""
        if not self.data_path.exists():
            raise FileNotFoundError(f'Data file not found: {self.data_path}')

        with open(self.data_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        if not records:
            logger.warning('Loaded 0 records — charts will be empty.')
            self.df = pd.DataFrame()
            return self.df

        self.df = pd.DataFrame(records)
        logger.info(f'Loaded {len(self.df)} records, columns: {list(self.df.columns)}')
        return self.df

    # ── Tech Stack Ranking ───────────────────────────────────────────────

    def plot_tech_stack_top10(self) -> Optional[Path]:
        """Horizontal bar chart of top-10 most demanded technologies."""
        if self.df is None or self.df.empty:
            logger.warning('No data to plot tech stack.')
            return None

        if 'core_tech_stack' not in self.df.columns:
            logger.warning('Column "core_tech_stack" not found.')
            return None

        # Explode list column and count
        exploded = self.df['core_tech_stack'].explode().dropna()
        exploded = exploded[exploded.apply(
            lambda x: isinstance(x, str) and x.strip() != ''
        )]
        if exploded.empty:
            logger.warning('No tech stack entries to plot.')
            return None

        counts = exploded.value_counts().head(10)

        # Plot
        fig, ax = plt.subplots(figsize=(10, 5))
        colors = STYLE_COLORS[:len(counts)][::-1]
        bars = ax.barh(range(len(counts)), counts.values, color=colors, height=0.65, edgecolor='white', linewidth=0.5)

        ax.set_yticks(range(len(counts)))
        ax.set_yticklabels(counts.index, fontsize=11)
        ax.invert_yaxis()
        ax.set_xlabel('Demand Count (职位需求数)', fontsize=12)
        ax.set_title('Top 10 Most Demanded Skills for Python Interns\nPython实习岗位技能需求 Top 10',
                     fontsize=14, fontweight='bold', pad=15)

        # Inline value labels
        for bar, val in zip(bars, counts.values):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', fontsize=10, fontweight='bold')

        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(left=False)

        path = self.output_dir / 'top10_skills.png'
        fig.savefig(path, facecolor='white')
        plt.close(fig)
        logger.info(f'Tech stack chart saved → {path}')
        return path

    # ── Salary Distribution ──────────────────────────────────────────────

    def plot_salary_distribution(self) -> Optional[Path]:
        """Histogram of average salary distribution."""
        if self.df is None or self.df.empty:
            logger.warning('No data to plot salary.')
            return None

        # Compute average salary: (min + max) / 2
        has_min = 'salary_min' in self.df.columns
        has_max = 'salary_max' in self.df.columns

        if not has_min and not has_max:
            logger.warning('No salary_min / salary_max columns found.')
            return None

        if has_min and has_max:
            avg_salary = (pd.to_numeric(self.df['salary_min'], errors='coerce') +
                          pd.to_numeric(self.df['salary_max'], errors='coerce')) / 2
        elif has_min:
            avg_salary = pd.to_numeric(self.df['salary_min'], errors='coerce')
        else:
            avg_salary = pd.to_numeric(self.df['salary_max'], errors='coerce')

        avg_salary = avg_salary.dropna()
        if avg_salary.empty:
            logger.warning('No valid salary values to plot.')
            return None

        # Plot
        fig, ax = plt.subplots(figsize=(10, 5))

        bins = min(20, max(8, len(avg_salary) // 2))
        n, bins_edges, patches = ax.hist(
            avg_salary, bins=bins, color='#4C72B0', edgecolor='white',
            linewidth=0.8, alpha=0.85, rwidth=0.92,
        )

        # Stats annotations
        mean_val = avg_salary.mean()
        median_val = avg_salary.median()
        ax.axvline(mean_val, color='#C44E52', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.0f} 元/天')
        ax.axvline(median_val, color='#55A868', linestyle='--', linewidth=2, label=f'Median: {median_val:.0f} 元/天')

        ax.set_xlabel('Average Daily Salary (元/天)', fontsize=12)
        ax.set_ylabel('Number of Positions (岗位数量)', fontsize=12)
        ax.set_title('Python Intern Salary Distribution\nPython实习岗位薪资分布',
                     fontsize=14, fontweight='bold', pad=15)
        ax.legend(loc='upper right', fontsize=10, framealpha=0.9)

        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        path = self.output_dir / 'salary_distribution.png'
        fig.savefig(path, facecolor='white')
        plt.close(fig)
        logger.info(f'Salary distribution chart saved → {path}')
        return path

    # ── Run all ──────────────────────────────────────────────────────────

    def run(self) -> None:
        """Load data and generate all charts."""
        self.load()
        self.plot_tech_stack_top10()
        self.plot_salary_distribution()
        logger.info('Analysis complete.')


# ── CLI entry ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    JobAnalyzer().run()
