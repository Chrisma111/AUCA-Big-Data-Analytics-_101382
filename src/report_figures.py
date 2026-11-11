"""
Report figures for Part 4 (the four visualization types named in the brief).

    python src/report_figures.py

Reads the result tables written by notebooks 03-05 (outputs/tables) and writes:
  outputs/figures/report_1_sales_performance.png      sales over time AND by category
  outputs/figures/report_2_customer_segmentation.png  users per segment and their average spending
Product performance (03_views_vs_sales.png) and the conversion funnel
(04_conversion_funnel.png) come from notebook 06.
"""
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
TAB = Path(os.environ.get("TAB_DIR", ROOT / "outputs" / "tables"))
FIG = Path(os.environ.get("FIG_DIR", ROOT / "outputs" / "figures"))
FIG.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"savefig.dpi": 200, "axes.titlesize": 12.5, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False})
PAL = sns.color_palette("deep")
money = mtick.FuncFormatter(lambda v, _: f"{v/1e6:.1f} M" if v >= 1e6 else f"{v/1e3:.0f} k")


def sales_performance():
    """Figure 1 - sales over time (left) and by category (right)."""
    d = pd.read_csv(TAB / "sql_daily_revenue_ma.csv", parse_dates=["txn_date"])
    c = pd.read_csv(TAB / "sql_category_conversion.csv").sort_values("net_revenue", ascending=False).head(10).iloc[::-1]
    full = d.iloc[1:-1]                                   # first and last day are partial days
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1.35, 1]})

    a.bar(d.txn_date, d.revenue, color=PAL[0], alpha=.35, label="Daily revenue")
    a.plot(d.txn_date, d.revenue_ma7, color=PAL[3], lw=2.4, label="7-day moving average")
    a.yaxis.set_major_formatter(money); a.set_ylabel("Revenue")
    a.set_title(f"Over time: {d.revenue.sum()/1e6:.1f} M in {len(d)} days, steady near {full.revenue.mean()/1e3:.0f} k/day")
    a.legend(frameon=False, loc="lower center"); a.tick_params(axis="x", labelsize=9)

    y = range(len(c)); h = .4
    b.barh([i + h/2 for i in y], c.net_revenue, h, color=PAL[0], label="Net revenue")
    b.barh([i - h/2 for i in y], c.est_gross_profit, h, color=PAL[2], label="Estimated gross profit")
    b.set_yticks(list(y)); b.set_yticklabels(c.category_name, fontsize=9)
    b.xaxis.set_major_formatter(money)
    b.set_title("By category: top 10 by revenue (profit ranks differ)")
    b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    fig.tight_layout(); fig.savefig(FIG / "report_1_sales_performance.png", bbox_inches="tight"); plt.close(fig)


def customer_segmentation():
    """Figure 2 - distribution of users by RFM segment and their average spending.
    (The data has no age, so RFM segments replace the brief's 'age group'.)"""
    r = pd.read_csv(TAB / "sql_rfm.csv")
    s = (r.groupby("segment").agg(users=("user_id", "count"), avg_spend=("monetary", "mean"),
                                 avg_orders=("frequency", "mean"))
          .sort_values("avg_spend", ascending=False))
    s["share"] = s.users / s.users.sum() * 100
    colors = [PAL[0] if seg in ("Champions", "Loyal") else (PAL[3] if seg == "At risk" else "#9aa5b1") for seg in s.index]
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.4))

    a.bar(s.index, s.users, color=colors)
    for i, (u, sh) in enumerate(zip(s.users, s.share)):
        a.text(i, u, f"{u:,}\n({sh:.0f}%)", ha="center", va="bottom", fontsize=9)
    a.set_ylim(0, s.users.max() * 1.25); a.set_ylabel("Customers")
    a.set_title(f"Distribution of {s.users.sum():,} buyers by RFM segment")

    b.bar(s.index, s.avg_spend, color=colors)
    for i, (v, o) in enumerate(zip(s.avg_spend, s.avg_orders)):
        b.text(i, v, f"{v:,.0f}\n{o:.1f} orders", ha="center", va="bottom", fontsize=9)
    b.set_ylim(0, s.avg_spend.max() * 1.25); b.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    b.set_ylabel("Average spend per customer")
    top, risk = s.iloc[0], s.loc["At risk"]
    b.set_title(f"Average spending: {s.index[0]} spend {top.avg_spend / risk.avg_spend:.1f}x more than At risk")
    for ax in (a, b): ax.tick_params(axis="x", labelsize=10)
    fig.tight_layout(); fig.savefig(FIG / "report_2_customer_segmentation.png", bbox_inches="tight"); plt.close(fig)
    return s


if __name__ == "__main__":
    sales_performance()
    seg = customer_segmentation()
    print(seg.round(1).to_string())
    print("saved to", FIG)
