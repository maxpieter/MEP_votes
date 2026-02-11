"""
Process aggregated vote data: calculate division scores, rebel scores, and generate stats.
Supports filtering by topic.
"""

import argparse
import os

import pandas as pd


def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cohesion-weighted deviation (rebel) scores."""

    # Majority position among AGAINST(0), FOR(1), ABSTAIN(2)
    maj_col = df[["count_against", "count_for", "count_abstentions"]].idxmax(axis=1)
    maj_map = {"count_against": 0, "count_for": 1, "count_abstentions": 2}
    df["group_majority"] = maj_col.map(maj_map).astype(int)

    # Agreement Index (AI) cohesion per (group, vote)
    total = df["count_for"] + df["count_against"] + df["count_abstentions"]
    M = df[["count_for", "count_against", "count_abstentions"]].max(axis=1)
    df["AI"] = ((M - (total - M) / 2) / total).where(total > 0, 0.0)

    # Deviation indicator (ignore DID_NOT_VOTE=3)
    participated = df["member_voted"].isin([0, 1, 2])
    df["deviation"] = (participated & (df["member_voted"] != df["group_majority"])).astype(int)

    # Weighted deviation score per vote
    df["rebel_score"] = df["deviation"] * df["AI"]

    return df



def compute_stats(df_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute party and MEP statistics from vote data.

    Returns:
        party_stats: Party-level aggregated division scores
        mep_stats: MEP-level aggregated rebel scores with outlier detection
    """
    # === PARTY-LEVEL STATS ===
    party_stats = (
        df_all.groupby("code")
        .agg({"AI": "mean", "vote_id": "nunique"})
        .rename(columns={"AI": "avg_AI", "vote_id": "n_votes"})
    )


    # === MEP-LEVEL STATS ===
    mep_stats = df_all.groupby("member.id").agg(
        avg_rebel_score=("rebel_score", "mean"),
        total_rebel_score=("rebel_score", "sum"),
        n_votes=("member_voted", "count"),
        party=("code", "first"),
        first_name=("member.first_name", "first"),
        last_name=("member.last_name", "first"),
        country=("member.country.code", "first"),
    ).reset_index()

    # === OUTLIER DETECTION (Z-score within party) ===
    party_agg = mep_stats.groupby("party")["avg_rebel_score"].agg(["mean", "std"])
    party_agg.columns = ["party_avg_rebel", "party_std"]
    mep_stats = mep_stats.merge(party_agg, on="party")
    mep_stats["z_score"] = (
        (mep_stats["avg_rebel_score"] - mep_stats["party_avg_rebel"])
        / mep_stats["party_std"].replace(0, float("inf"))
    )
    mep_stats = mep_stats.drop(columns=["party_std"])

    # Flag outliers (z > 2 = significantly more rebellious than party peers)
    mep_stats["is_outlier"] = mep_stats["z_score"] > 2

    # Sort by z-score to show biggest rebels first
    mep_stats = mep_stats.sort_values("z_score", ascending=False)

    return party_stats, mep_stats


def filter_by_topic(df: pd.DataFrame, topic: str) -> pd.DataFrame:
    """Filter dataframe by topic (case-insensitive, partial match)."""
    topic_col = "topics_effective" if "topics_effective" in df.columns else "topics"
    mask = df[topic_col].fillna("").str.lower().str.contains(topic.lower())
    return df[mask]


def print_stats(party_stats: pd.DataFrame, mep_stats: pd.DataFrame, topic: str = None):
    """Print statistics to console."""
    topic_str = f" (topic: {topic})" if topic else ""

    print("\n" + "=" * 60)
    print(f"PARTY-LEVEL STATISTICS{topic_str}")
    print("=" * 60)
    print(party_stats.to_string())

    print("\n" + "=" * 60)
    print(f"TOP 20 REBELS (highest z-score within party){topic_str}")
    print("=" * 60)
    top_rebels = mep_stats.head(20)[
        [
            "first_name",
            "last_name",
            "party",
            "country",
            "n_votes",
            "avg_rebel_score",
            "party_avg_rebel",
            "z_score",
        ]
    ]
    print(top_rebels.to_string(index=False))

    outliers = mep_stats[mep_stats["is_outlier"]]
    print(f"\n" + "=" * 60)
    print(f"OUTLIERS DETECTED: {len(outliers)} MEPs (z-score > 2){topic_str}")
    print("=" * 60)
    if len(outliers) > 0:
        print(
            outliers[
                [
                    "first_name",
                    "last_name",
                    "party",
                    "country",
                    "n_votes",
                    "avg_rebel_score",
                    "z_score",
                ]
            ].to_string(index=False)
        )


def main():
    parser = argparse.ArgumentParser(description="Process MEP voting data")
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Filter by topic (e.g., 'agriculture', 'defence')",
    )
    args = parser.parse_args()

    # Load raw data
    input_file = "data/all_votes_raw.csv"
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Run aggregate_votes.py first.")
        return

    print(f"Loading data from {input_file}...")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} records")

    # Filter by topic if specified
    if args.topic:
        df = filter_by_topic(df, args.topic)
        print(f"Filtered to {len(df)} records matching topic '{args.topic}'")
        if len(df) == 0:
            print("No records match this topic.")
            return

    # Calculate scores
    df = calculate_scores(df)

    # Compute stats
    party_stats, mep_stats = compute_stats(df)

    # Print stats
    print_stats(party_stats, mep_stats, args.topic)

    # Save outputs
    os.makedirs("data", exist_ok=True)
    party_stats.to_csv(f"data/party_stats.csv")
    mep_stats.to_csv(f"data/mep_stats.csv", index=False)
    print(f"\nSaved: data/party_stats.csv, data/mep_stats.csv")


if __name__ == "__main__":
    main()
