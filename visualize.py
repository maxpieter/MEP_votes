"""
Visualizations for MEP voting rebellion analysis.
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# === CONFIGURATION ===
DATA_DIR = "data"
OUTPUT_DIR = "plots"

# Party colors (official EU Parliament colors)
PARTY_COLORS = {
    "EPP": "#3399FF",
    "SD": "#FF0000",
    "RENEW": "#FFD700",
    "GREEN_EFA": "#00994D",
    "ECR": "#0054A5",
    "ID": "#2B3856",
    "GUE_NGL": "#990000",
    "PFE": "#000080",
    "ESN": "#8B0000",
    "NI": "#999999"
}


def load_data():
    """Load all data files."""
    party_stats = pd.read_csv(f"{DATA_DIR}/party_stats.csv")
    mep_stats = pd.read_csv(f"{DATA_DIR}/mep_stats.csv")
    return party_stats, mep_stats


def plot_party_cohesion(party_stats):
    """Bar chart showing party division scores (higher = less cohesive)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    party_stats_sorted = party_stats.sort_values("avg_division", ascending=True)
    colors = [PARTY_COLORS.get(p, "#999999") for p in party_stats_sorted["code"]]

    ax.barh(party_stats_sorted["code"], party_stats_sorted["avg_division"], color=colors)
    ax.set_xlabel("Average Division Score")
    ax.set_title("Party Cohesion (lower = more unified)")
    ax.set_xlim(0, party_stats_sorted["avg_division"].max() * 1.1)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/party_cohesion.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/party_cohesion.png")


def plot_top_rebels(mep_stats, n=25):
    """Bar chart of top rebels by average rebel score."""
    fig, ax = plt.subplots(figsize=(10, 8))

    top = mep_stats.head(n).copy()
    top["label"] = top["first_name"] + " " + top["last_name"] + " (" + top["party"] + ")"
    colors = [PARTY_COLORS.get(p, "#999999") for p in top["party"]]

    ax.barh(top["label"], top["avg_rebel_score"], color=colors)
    ax.set_xlabel("Average Rebel Score")
    ax.set_title(f"Top {n} Rebels (voted against unified party)")
    ax.invert_yaxis()

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/top_rebels.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/top_rebels.png")


def plot_rebel_distribution(mep_stats):
    """Box plot showing rebel score distribution by party."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Order by median rebel score
    order = mep_stats.groupby("party")["avg_rebel_score"].median().sort_values(ascending=False).index
    palette = {p: PARTY_COLORS.get(p, "#999999") for p in order}

    sns.boxplot(data=mep_stats, x="party", y="avg_rebel_score", order=order, palette=palette, ax=ax)
    ax.set_xlabel("Party")
    ax.set_ylabel("Average Rebel Score")
    ax.set_title("Rebel Score Distribution by Party")
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/rebel_distribution.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/rebel_distribution.png")


def plot_country_party_heatmap(mep_stats):
    """Heatmap of average rebel score by country and party."""
    fig, ax = plt.subplots(figsize=(14, 10))

    pivot = mep_stats.pivot_table(
        values="avg_rebel_score",
        index="country",
        columns="party",
        aggfunc="mean"
    )

    # Sort by overall country rebel score
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]

    sns.heatmap(pivot, cmap="Reds", annot=True, fmt=".2f", ax=ax, cbar_kws={"label": "Avg Rebel Score"})
    ax.set_title("Rebel Score by Country and Party")

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/country_party_heatmap.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/country_party_heatmap.png")


def plot_participation_vs_rebellion(mep_stats):
    """Scatter plot of votes participated vs rebel score."""
    fig, ax = plt.subplots(figsize=(10, 8))

    for party in mep_stats["party"].unique():
        subset = mep_stats[mep_stats["party"] == party]
        ax.scatter(
            subset["n_votes"],
            subset["avg_rebel_score"],
            c=PARTY_COLORS.get(party, "#999999"),
            label=party,
            alpha=0.6,
            s=30
        )

    ax.set_xlabel("Number of Votes Participated")
    ax.set_ylabel("Average Rebel Score")
    ax.set_title("Participation vs Rebellion")
    ax.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/participation_vs_rebellion.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/participation_vs_rebellion.png")


def plot_outliers_by_party(mep_stats):
    """Bar chart showing number of outliers per party."""
    fig, ax = plt.subplots(figsize=(10, 6))

    outlier_counts = mep_stats[mep_stats["is_outlier"]].groupby("party").size()
    total_counts = mep_stats.groupby("party").size()
    outlier_pct = (outlier_counts / total_counts * 100).fillna(0).sort_values(ascending=True)

    colors = [PARTY_COLORS.get(p, "#999999") for p in outlier_pct.index]
    ax.barh(outlier_pct.index, outlier_pct.values, color=colors)
    ax.set_xlabel("% of MEPs flagged as outliers (z-score > 2)")
    ax.set_title("Outlier Rate by Party")

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/outliers_by_party.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/outliers_by_party.png")


def plot_z_score_distribution(mep_stats):
    """Histogram of z-scores across all MEPs."""
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.hist(mep_stats["z_score"], bins=50, edgecolor="black", alpha=0.7)
    ax.axvline(x=2, color="red", linestyle="--", label="Outlier threshold (z=2)")
    ax.axvline(x=-2, color="red", linestyle="--")
    ax.set_xlabel("Z-Score (within party)")
    ax.set_ylabel("Number of MEPs")
    ax.set_title("Distribution of Rebel Z-Scores")
    ax.legend()

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/z_score_distribution.png", dpi=150)
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/z_score_distribution.png")


def plot_party_rebel_distributions(mep_stats):
    """Faceted histograms showing rebel score distribution for each party."""
    parties = mep_stats["party"].unique()
    n_parties = len(parties)
    cols = 3
    rows = (n_parties + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(14, 3 * rows))
    axes = axes.flatten()

    # Sort parties by median rebel score
    party_order = mep_stats.groupby("party")["avg_rebel_score"].median().sort_values(ascending=False).index

    for i, party in enumerate(party_order):
        ax = axes[i]
        subset = mep_stats[mep_stats["party"] == party]["avg_rebel_score"]
        color = PARTY_COLORS.get(party, "#999999")

        ax.hist(subset, bins=30, color=color, edgecolor="black", alpha=0.7)
        ax.axvline(subset.median(), color="black", linestyle="--", linewidth=1.5, label=f"median: {subset.median():.3f}")
        ax.set_title(f"{party} (n={len(subset)})")
        ax.set_xlabel("Rebel Score")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8)

    # Hide empty subplots
    for i in range(len(party_order), len(axes)):
        axes[i].set_visible(False)

    plt.suptitle("Rebel Score Distributions by Party", fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/party_rebel_distributions.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {OUTPUT_DIR}/party_rebel_distributions.png")


def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading data...")
    party_stats, mep_stats = load_data()

    print("\nGenerating visualizations...")
    plot_party_cohesion(party_stats)
    plot_top_rebels(mep_stats)
    plot_rebel_distribution(mep_stats)
    plot_country_party_heatmap(mep_stats)
    plot_participation_vs_rebellion(mep_stats)
    plot_outliers_by_party(mep_stats)
    plot_z_score_distribution(mep_stats)
    plot_party_rebel_distributions(mep_stats)

    print(f"\nAll plots saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
