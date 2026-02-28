"""
chart.py — Generate a chart image from SQL query results.

Detects if a query spans multiple dates and produces a bar or line chart.
Returns the path to a temporary PNG file.
"""

import os
import re
import tempfile
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Optional matplotlib import — graceful fallback if not installed
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")   
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def is_date_range_query(sql: str) -> bool:
    """
    Returns True if the SQL looks like a date range query
    (i.e. contains BETWEEN, >= / <=, or groups/orders by date).
    """
    patterns = [
        r"\bBETWEEN\b",
        r"date\s*>=",
        r"date\s*<=",
        r"date\s*>",
        r"date\s*<",
        r"GROUP\s+BY\s+date",
        r"ORDER\s+BY\s+date",
    ]
    sql_upper = sql.upper()
    return any(re.search(p, sql_upper, re.IGNORECASE) for p in patterns)


def generate_chart(
    columns: List[str],
    rows: List[Dict[str, Any]],
    question: str,
) -> str | None:
    """
    Generate a bar chart from query results and save to a temp PNG file.

    Args:
        columns:  Column names from the query result.
        rows:     List of result row dicts.
        question: The original user question (used as chart title).

    Returns:
        Path to the temporary PNG file, or None if chart can't be generated.
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    if not rows or len(columns) < 2:
        return None

    
    x_col = columns[0]     
    y_cols = []

    for col in columns[1:]:
        try:
            float(str(rows[0].get(col, "")))
            y_cols.append(col)
        except (ValueError, TypeError):
            pass

    if not y_cols:
        return None

    x_labels = [str(row.get(x_col, "")) for row in rows]

    
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    colors = ["#0f3460", "#e94560", "#533483", "#2ecc71", "#f39c12"]
    bar_width = 0.8 / len(y_cols)
    x_positions = range(len(x_labels))

    for i, y_col in enumerate(y_cols):
        y_values = []
        for row in rows:
            try:
                y_values.append(float(str(row.get(y_col, 0) or 0)))
            except (ValueError, TypeError):
                y_values.append(0.0)

        offset = [x + (i - len(y_cols) / 2 + 0.5) * bar_width for x in x_positions]
        bars = ax.bar(
            offset,
            y_values,
            width=bar_width * 0.9,
            label=y_col.replace("_", " ").title(),
            color=colors[i % len(colors)],
            alpha=0.85,
            edgecolor="#ffffff20",
        )

        
        for bar, val in zip(bars, y_values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(y_values) * 0.01,
                    f"{val:,.0f}",
                    ha="center", va="bottom",
                    fontsize=7, color="white", alpha=0.8,
                )

    
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(x_labels, rotation=30, ha="right", color="white", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#ffffff30")
    ax.spines["left"].set_color("#ffffff30")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.label.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.set_xlabel(x_col.replace("_", " ").title(), color="white", fontsize=10)
    ax.set_ylabel(", ".join(y_cols).replace("_", " ").title(), color="white", fontsize=10)

    
    title = question[:60] + "..." if len(question) > 60 else question
    ax.set_title(title, color="white", fontsize=11, pad=12)

    if len(y_cols) > 1:
        ax.legend(facecolor="#0f3460", labelcolor="white", fontsize=9)

    ax.grid(axis="y", color="#ffffff15", linestyle="--", linewidth=0.5)

    plt.tight_layout()

    
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    plt.savefig(tmp.name, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return tmp.name


def cleanup_chart(path: str) -> None:
    """Delete the temporary chart file after upload."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass