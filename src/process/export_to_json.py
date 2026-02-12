"""
Generate per-topic and per-period JSON files for the frontend visualization.
Creates docs/data/periods/<period>/mep_data.json and docs/data/periods/<period>/topics/<topic>.json
"""

import json
import os
import re

import pandas as pd

# Define the topics to export
TOPICS = [
    "Biodiversity",
    "Climate and environment",
    "Climate change",
    "Consumer protection",
    "Digital",
    "Economy and budget",
    "Education",
    "Energy",
    "Enlargement",
    "Food and agriculture",
    "Foreign affairs",
    "Gender equality",
    "Health",
    "International trade",
    "Migration",
    "Social protection",
    "Taxation",
    "Travel",
    "Worker’s rights",
    "youth and culture",
]

# Define EU Parliament periods (start date, end date, label)
# EP terms run from July to June
PERIODS = [
    {
        "id": "ep10",
        "label": "EP10 (2024-2029)",
        "start": "2024-07-16",
        "end": "2029-07-15",
        "is_default": True,
    },
    {
        "id": "ep9",
        "label": "EP9 (2019-2024)",
        "start": "2019-07-02",
        "end": "2024-07-15",
        "is_default": False,
    },
]


def slugify(text: str) -> str:
    """Convert topic name to URL-safe filename."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate division and rebel scores for both group and country."""
    df = df.copy()

    # Group-level rebel score (existing logic)
    df["group_voted"] = (df["count_for"] > df["count_against"]).astype(int)
    total = df["count_for"] + df["count_against"] + df["count_abstentions"]
    majority = df[["count_for", "count_against"]].max(axis=1)
    df["division"] = 1 - (majority / total)
    voted_opposite = (df["member_voted"].isin([0, 1])) & (
        df["member_voted"] != df["group_voted"]
    )
    df["rebel_score"] = voted_opposite.astype(int) * (1 - df["division"])

    # Country-level rebel score
    # Aggregate votes by country for each vote
    country_votes = df.groupby(["vote_id", "member.country.code"]).agg(
        country_for=("member_voted", lambda x: (x == 1).sum()),
        country_against=("member_voted", lambda x: (x == 0).sum()),
        country_abstain=("member_voted", lambda x: (x == 2).sum()),
    ).reset_index()
    country_votes["country_voted"] = (country_votes["country_for"] > country_votes["country_against"]).astype(int)
    country_total = country_votes["country_for"] + country_votes["country_against"] + country_votes["country_abstain"]
    country_majority = country_votes[["country_for", "country_against"]].max(axis=1)
    country_votes["country_division"] = 1 - (country_majority / country_total.replace(0, 1))

    # Merge country stats back
    df = df.merge(
        country_votes[["vote_id", "member.country.code", "country_voted", "country_division"]],
        on=["vote_id", "member.country.code"],
        how="left"
    )

    # Calculate country rebel score
    country_voted_opposite = (df["member_voted"].isin([0, 1])) & (
        df["member_voted"] != df["country_voted"]
    )
    df["country_rebel_score"] = country_voted_opposite.astype(int) * (1 - df["country_division"])

    return df


def compute_mep_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute MEP statistics with outlier detection for both group and country."""
    mep_stats = df.groupby("member.id").agg(
        avg_rebel_score=("rebel_score", "mean"),
        total_rebel_score=("rebel_score", "sum"),
        avg_country_rebel_score=("country_rebel_score", "mean"),
        n_votes=("member_voted", "count"),
        group=("member.group.code", "first"),
        first_name=("member.first_name", "first"),
        last_name=("member.last_name", "first"),
        country=("member.country.code", "first"),
    ).reset_index()

    # Z-score within group
    group_agg = mep_stats.groupby("group")["avg_rebel_score"].agg(["mean", "std"])
    group_agg.columns = ["group_avg_rebel", "group_std"]
    mep_stats = mep_stats.merge(group_agg, on="group")
    mep_stats["group_z_score"] = (
        (mep_stats["avg_rebel_score"] - mep_stats["group_avg_rebel"])
        / mep_stats["group_std"].replace(0, float("inf"))
    )
    mep_stats = mep_stats.drop(columns=["group_std"])
    mep_stats["group_is_outlier"] = mep_stats["group_z_score"] > 2

    # Z-score within country
    country_agg = mep_stats.groupby("country")["avg_country_rebel_score"].agg(["mean", "std"])
    country_agg.columns = ["country_avg_rebel", "country_std"]
    mep_stats = mep_stats.merge(country_agg, on="country")
    mep_stats["country_z_score"] = (
        (mep_stats["avg_country_rebel_score"] - mep_stats["country_avg_rebel"])
        / mep_stats["country_std"].replace(0, float("inf"))
    )
    mep_stats = mep_stats.drop(columns=["country_std"])
    mep_stats["country_is_outlier"] = mep_stats["country_z_score"] > 2

    mep_stats = mep_stats.sort_values("group_z_score", ascending=False)

    return mep_stats


def export_data(df: pd.DataFrame, output_path: str) -> int:
    """Calculate scores and export to JSON."""
    if len(df) == 0:
        return 0

    # Count unique votes before aggregation
    total_votes = df["vote_id"].nunique()

    df = calculate_scores(df)
    mep_stats = compute_mep_stats(df)

    # Add topics list for each MEP (from this filtered set)
    mep_topics = (
        df.groupby("member.id")["topics"]
        .apply(lambda x: ", ".join(set(t for topics in x.dropna() for t in topics.split(", ") if t)))
        .reset_index()
    )
    mep_topics.columns = ["member.id", "topics"]
    mep_data = mep_stats.merge(mep_topics, on="member.id", how="left")

    # Select columns for frontend
    output_cols = [
        "member.id",
        "first_name",
        "last_name",
        "group",
        "country",
        "n_votes",
        "avg_rebel_score",
        "total_rebel_score",
        "group_avg_rebel",
        "group_z_score",
        "group_is_outlier",
        "avg_country_rebel_score",
        "country_avg_rebel",
        "country_z_score",
        "country_is_outlier",
        "topics",
    ]
    mep_data = mep_data[output_cols]

    # Export with metadata
    output = {
        "meta": {
            "total_votes": total_votes,
            "total_meps": len(mep_data),
        },
        "meps": mep_data.to_dict(orient="records"),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    return len(mep_data)


def filter_by_period(df: pd.DataFrame, period: dict) -> pd.DataFrame:
    """Filter dataframe by parliament period."""
    mask = (df["timestamp"] >= period["start"]) & (df["timestamp"] <= period["end"])
    return df[mask].copy()


def filter_by_topic(df: pd.DataFrame, topic: str) -> pd.DataFrame:
    """Filter dataframe by topic."""
    mask = df["topics"].fillna("").str.lower().str.contains(topic.lower())
    return df[mask].copy()


def main():
    print("Loading raw vote data...")
    df_all = pd.read_csv("data/all_votes_raw.csv", low_memory=False)
    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], format="ISO8601")
    print(f"Loaded {len(df_all)} vote records")
    print(f"Date range: {df_all['timestamp'].min()} to {df_all['timestamp'].max()}")

    print(f"\nUsing {len(TOPICS)} topics and {len(PERIODS)} periods")

    # Build topic index (topic name -> slug)
    topic_index = {topic: slugify(topic) for topic in TOPICS}

    # Export data for each period
    for period in PERIODS:
        period_id = period["id"]
        print(f"\n{'='*60}")
        print(f"Processing {period['label']}...")
        print(f"{'='*60}")

        # Filter by period
        df_period = filter_by_period(df_all, period)
        print(f"  {len(df_period)} votes in period")

        if len(df_period) == 0:
            print(f"  Skipping {period_id}: no data")
            continue

        # Create output directories
        period_dir = f"docs/data/periods/{period_id}"
        topics_dir = f"{period_dir}/topics"
        os.makedirs(topics_dir, exist_ok=True)

        # Export "all topics" data for this period
        output_path = f"{period_dir}/mep_data.json"
        n = export_data(df_period, output_path)
        print(f"  {output_path}: {n} MEPs")

        # Export per-topic data for this period
        for topic in TOPICS:
            slug = topic_index[topic]
            df_topic = filter_by_topic(df_period, topic)
            output_path = f"{topics_dir}/{slug}.json"
            n = export_data(df_topic, output_path)
            if n > 0:
                print(f"  {output_path}: {n} MEPs")
            else:
                print(f"  Skipping {topic}: no data")

    # Save config for frontend (topics, periods)
    config = {
        "topics": topic_index,
        "periods": PERIODS,
        "default_period": next(p["id"] for p in PERIODS if p.get("is_default", False)),
    }
    config_path = "docs/data/config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"\nSaved config to {config_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
