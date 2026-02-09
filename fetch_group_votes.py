"""Fetch voting data aggregated by political group from HowTheyVote.eu API."""

from io import StringIO

import pandas as pd
import requests

BASE_URL = "https://howtheyvote.eu/api/votes"


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
        usecols=[
            "code",
            "label",
            "count_for",
            "count_against",
            "count_abstentions",
            "count_did_not_vote",
        ],
    )

    return df


def fetch_all_group_votes(max_workers: int = 40) -> pd.DataFrame:
    """Fetch group votes for all vote IDs in vote_index.csv (parallelized)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    vote_index = pd.read_csv("data/vote_index.csv")
    vote_ids = vote_index["id"].tolist()
    total = len(vote_ids)

    def fetch_single(vote_id):
        df = fetch_vote_groups(vote_id)
        df["vote_id"] = vote_id
        return df

    all_groups = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single, vid): vid for vid in vote_ids}

        for future in as_completed(futures):
            vote_id = futures[future]
            completed += 1
            try:
                all_groups.append(future.result())
                if completed % 50 == 0:
                    print(f"  Progress: {completed}/{total} votes processed")
            except Exception as e:
                print(f"  Error fetching {vote_id}: {e}")

    df_all = pd.concat(all_groups, ignore_index=True)
    return df_all


if __name__ == "__main__":
    print("Fetching group votes for all votes in vote_index.csv...")
    df = fetch_all_group_votes()
    df.to_csv("data/group_votes.csv", index=False)
    print(f"Saved {len(df)} records to data/group_votes.csv")
