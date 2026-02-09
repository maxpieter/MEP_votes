"""
Export processed MEP data to JSON for the frontend visualization.
"""

import json
import pandas as pd


def main():
    # Load mep_stats (aggregated per MEP)
    print("Loading data...")
    mep_stats = pd.read_csv("data/mep_stats.csv")

    # Load all_votes_raw to get topics per MEP
    all_votes = pd.read_csv("data/all_votes_raw.csv")

    # Aggregate topics per MEP (combine all topics they voted on)
    mep_topics = (
        all_votes.groupby("member.id")["topics"]
        .apply(lambda x: ", ".join(set(t for topics in x.dropna() for t in topics.split(", ") if t)))
        .reset_index()
    )
    mep_topics.columns = ["member.id", "topics"]

    # Merge topics into mep_stats
    mep_data = mep_stats.merge(mep_topics, on="member.id", how="left")

    # Select columns for frontend
    output_cols = [
        "member.id",
        "first_name",
        "last_name",
        "party",
        "country",
        "n_votes",
        "avg_rebel_score",
        "total_rebel_score",
        "party_avg_rebel",
        "z_score",
        "is_outlier",
        "topics",
    ]
    mep_data = mep_data[output_cols]

    # Convert to JSON
    records = mep_data.to_dict(orient="records")

    # Save to docs/data/mep_data.json (for GitHub Pages)
    output_path = "docs/data/mep_data.json"
    with open(output_path, "w") as f:
        json.dump(records, f)

    print(f"Exported {len(records)} MEPs to {output_path}")


if __name__ == "__main__":
    main()
