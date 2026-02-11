"""
Aggregate vote data by merging CSV files from fetch scripts.
"""

import pandas as pd


def load_and_merge_data() -> pd.DataFrame:
    """Load pre-fetched CSV files and merge them on vote_id."""
    print("Loading data from CSV files...")

    df_votes = pd.read_csv("data/vote_index_clean.csv")
    print(f"  Loaded {len(df_votes)} vote records")

    df_members = pd.read_csv("data/member_votes.csv")
    print(f"  Loaded {len(df_members)} member vote records")

    df_groups = pd.read_csv("data/group_votes.csv")
    print(f"  Loaded {len(df_groups)} group vote records")

    # Merge group-level data onto each MEP record
    df_all = df_members.merge(
        df_groups,
        left_on=["vote_id", "member.group.code"],
        right_on=["vote_id", "code"],
    )

    # Merge vote metadata
    df_all = df_all.merge(
        df_votes.rename(columns={"id": "vote_id"}),
        on="vote_id",
    )

    print(f"  Merged into {len(df_all)} records")
    return df_all


if __name__ == "__main__":
    df = load_and_merge_data()
    df.to_csv("data/all_votes_raw.csv", index=False)
    print(f"Saved {len(df)} records to data/all_votes_raw.csv")
