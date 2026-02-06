"""
Fetch MEP voting data from HowTheyVote.eu API and analyze party rebellion.
Aggregates across multiple votes to detect consistent rebels.
"""
import os
import requests
import pandas as pd
from io import StringIO

# === CONFIGURATION ===
BASE_URL = "https://howtheyvote.eu/api/votes"


def fetch_all_vote_ids() -> pd.DataFrame:
    """
    Fetch all vote metadata from the API (paginated).
    Returns DataFrame with columns: id, display_title, timestamp, topics, result
    """
    all_votes = []
    page = 1

    print("Fetching vote index...")
    while True:
        response = requests.get(f"{BASE_URL}?page={page}&page_size=100")
        response.raise_for_status()
        data = response.json()

        for vote in data["results"]:
            # Extract topic labels
            topics = [t["label"] for t in vote.get("topics", [])]
            all_votes.append({
                "id": vote["id"],
                "title": vote["display_title"],
                "timestamp": vote["timestamp"],
                "topics": ", ".join(topics) if topics else None,
                "result": vote["result"]
            })

        print(f"  Page {page}: {len(data['results'])} votes (total so far: {len(all_votes)})")

        if not data["has_next"]:
            break
        page += 1

    print(f"Found {len(all_votes)} total votes\n")
    return pd.DataFrame(all_votes)


def fetch_vote_groups(vote_id: str) -> pd.DataFrame:
    """
    Fetch voting data aggregated by political group.
    Returns: DataFrame with columns [code, count_for, count_against, count_abstentions,
             count_did_not_vote, group_voted, division]
    """
    url = f"{BASE_URL}/{vote_id}/groups.csv"

    response = requests.get(url)
    response.raise_for_status()

    df = pd.read_csv(
        StringIO(response.text),
        usecols=["code", "count_for", "count_against", "count_abstentions", "count_did_not_vote"]
    )

    # Determine if the group voted FOR (majority): 1=FOR, 0=AGAINST
    df["group_voted"] = (df["count_for"] > df["count_against"]).astype(int)

    # Calculate division score: 0 = unanimous, higher = more divided
    total = df["count_for"] + df["count_against"] + df["count_abstentions"]
    majority = df[["count_for", "count_against"]].max(axis=1)
    df["division"] = 1 - (majority / total)

    return df


def fetch_vote_mep(vote_id: str) -> pd.DataFrame:
    """Fetch individual MEP voting positions."""
    url = f"{BASE_URL}/{vote_id}/members.csv"

    response = requests.get(url)
    response.raise_for_status()

    df = pd.read_csv(
        StringIO(response.text),
        usecols=["position", "member.id", "member.first_name", "member.last_name",
                 "member.country.code", "member.group.code"]
    )

    # Encode positions: AGAINST=0, FOR=1, ABSTENTION=2, DID_NOT_VOTE=3
    position_map = {
        "VotePosition.AGAINST": 0,
        "VotePosition.FOR": 1,
        "VotePosition.ABSTENTION": 2,
        "VotePosition.DID_NOT_VOTE": 3
    }
    df["member_voted"] = df["position"].map(position_map)
    df = df.drop(columns=["position"])

    return df


def process_single_vote(vote_id: str) -> pd.DataFrame:
    """Fetch and process a single vote, returning MEP-level data with rebel scores."""

    df_groups = fetch_vote_groups(vote_id)
    df_mep = fetch_vote_mep(vote_id)

    # Merge group-level data onto each MEP
    df_mep = df_mep.merge(
        df_groups[["code", "group_voted", "division"]],
        left_on="member.group.code",
        right_on="code"
    )

    # Calculate rebel score (only FOR vs AGAINST counts)
    voted_opposite = (
        (df_mep["member_voted"].isin([0, 1])) &
        (df_mep["member_voted"] != df_mep["group_voted"])
    )
    df_mep["rebel_score"] = voted_opposite.astype(int) * (1 - df_mep["division"])

    # Clean up columns
    df_mep = df_mep.drop(columns=["member.group.code"])
    df_mep["vote_id"] = vote_id

    return df_mep


def compute_stats(df_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute party and MEP statistics from vote data.

    Returns:
        party_stats: Party-level aggregated division scores
        mep_stats: MEP-level aggregated rebel scores with outlier detection
    """
    # === PARTY-LEVEL STATS ===
    party_stats = df_all.groupby("code").agg({
        "division": "mean",
        "vote_id": "nunique"
    }).rename(columns={
        "division": "avg_division",
        "vote_id": "n_votes"
    })

    # === MEP-LEVEL STATS ===
    mep_stats = df_all.groupby("member.id").agg({
        "rebel_score": ["mean", "sum"],
        "member_voted": "count",
        "code": "first",
        "member.first_name": "first",
        "member.last_name": "first",
        "member.country.code": "first"
    })
    # Flatten column names
    mep_stats.columns = ["avg_rebel_score", "total_rebel_score", "n_votes",
                         "party", "first_name", "last_name", "country"]
    mep_stats = mep_stats.reset_index()

    # === OUTLIER DETECTION (Z-score within party) ===
    def compute_z_score(group):
        mean = group["avg_rebel_score"].mean()
        std = group["avg_rebel_score"].std()
        if std > 0:
            group["z_score"] = (group["avg_rebel_score"] - mean) / std
        else:
            group["z_score"] = 0
        group["party_avg_rebel"] = mean
        return group

    mep_stats = mep_stats.groupby("party", group_keys=False).apply(compute_z_score)

    # Flag outliers (z > 2 = significantly more rebellious than party peers)
    mep_stats["is_outlier"] = mep_stats["z_score"] > 2

    # Sort by z-score to show biggest rebels first
    mep_stats = mep_stats.sort_values("z_score", ascending=False)

    return party_stats, mep_stats


def aggregate_all_votes(vote_ids: list) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetch all votes and compute aggregated statistics.

    Returns:
        df_all: All individual vote records
        party_stats: Party-level aggregated division scores
        mep_stats: MEP-level aggregated rebel scores with outlier detection
    """
    # Fetch all votes
    all_votes = []
    total = len(vote_ids)
    for i, vote_id in enumerate(vote_ids, 1):
        try:
            df = process_single_vote(vote_id)
            all_votes.append(df)
            if i % 50 == 0:
                print(f"  Progress: {i}/{total} votes processed")
        except Exception as e:
            print(f"  Error fetching {vote_id}: {e}")

    df_all = pd.concat(all_votes, ignore_index=True)
    print(f"\nTotal records: {len(df_all)} votes from {len(vote_ids)} vote sessions")

    party_stats, mep_stats = compute_stats(df_all)

    return df_all, party_stats, mep_stats


def main():
    cache_file = "all_votes_raw.csv"

    # Check if cached data exists
    if os.path.exists(cache_file):
        print(f"Loading cached data from {cache_file}...")
        df_all = pd.read_csv(cache_file)
        print(f"Loaded {len(df_all)} records")

        # Compute stats from cached data
        party_stats, mep_stats = compute_stats(df_all)
    else:
        # Fetch all available vote IDs from the API
        vote_index = fetch_all_vote_ids()
        vote_index.to_csv("vote_index.csv", index=False)
        print("Saved: vote_index.csv")

        vote_ids = vote_index["id"].tolist()
        df_all, party_stats, mep_stats = aggregate_all_votes(vote_ids)

    # === OUTPUT: Party Stats ===
    print("\n" + "="*60)
    print("PARTY-LEVEL STATISTICS")
    print("="*60)
    print(party_stats.to_string())

    # === OUTPUT: Top Rebels ===
    print("\n" + "="*60)
    print("TOP 20 REBELS (highest z-score within party)")
    print("="*60)
    top_rebels = mep_stats.head(20)[["first_name", "last_name", "party", "country",
                                      "n_votes", "avg_rebel_score", "party_avg_rebel", "z_score"]]
    print(top_rebels.to_string(index=False))

    # === OUTPUT: Outliers ===
    outliers = mep_stats[mep_stats["is_outlier"]]
    print(f"\n" + "="*60)
    print(f"OUTLIERS DETECTED: {len(outliers)} MEPs (z-score > 2)")
    print("="*60)
    if len(outliers) > 0:
        print(outliers[["first_name", "last_name", "party", "country",
                        "n_votes", "avg_rebel_score", "z_score"]].to_string(index=False))

    # === SAVE TO CSV ===
    df_all.to_csv("all_votes_raw.csv", index=False)
    party_stats.to_csv("party_stats.csv")
    mep_stats.to_csv("mep_stats.csv", index=False)
    print("\nSaved: all_votes_raw.csv, party_stats.csv, mep_stats.csv")


if __name__ == "__main__":
    main()
