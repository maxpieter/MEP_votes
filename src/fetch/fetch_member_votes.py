"""Fetch individual MEP voting positions from HowTheyVote.eu API."""

from io import StringIO

import pandas as pd
import requests

BASE_URL = "https://howtheyvote.eu/api/votes"


def fetch_vote_mep(vote_id: str) -> pd.DataFrame:
    """Fetch individual MEP voting positions."""
    url = f"{BASE_URL}/{vote_id}/members.csv"

    response = requests.get(url)
    response.raise_for_status()
    response.encoding = "utf-8"

    df = pd.read_csv(
        StringIO(response.text),
        encoding="utf-8",
        usecols=[
            "position",
            "member.id",
            "member.first_name",
            "member.last_name",
            "member.country.code",
            "member.country.label",
            "member.group.code",
        ],
    )

    # Encode positions: AGAINST=0, FOR=1, ABSTENTION=2, DID_NOT_VOTE=3
    position_map = {
        "VotePosition.AGAINST": 0,
        "VotePosition.FOR": 1,
        "VotePosition.ABSTENTION": 2,
        "VotePosition.DID_NOT_VOTE": 3,
    }
    df["member_voted"] = df["position"].map(position_map)
    df = df.drop(columns=["position"])

    return df


def fetch_all_member_votes(max_workers: int = 40) -> pd.DataFrame:
    """Fetch member votes for all vote IDs in vote_index.csv (parallelized)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    vote_index = pd.read_csv("data/vote_index.csv")
    vote_ids = vote_index["id"].tolist()
    total = len(vote_ids)

    def fetch_single(vote_id):
        df = fetch_vote_mep(vote_id)
        df["vote_id"] = vote_id
        return df

    all_members = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single, vid): vid for vid in vote_ids}

        for future in as_completed(futures):
            vote_id = futures[future]
            completed += 1
            try:
                all_members.append(future.result())
                if completed % 50 == 0:
                    print(f"  Progress: {completed}/{total} votes processed")
            except Exception as e:
                print(f"  Error fetching {vote_id}: {e}")

    df_all = pd.concat(all_members, ignore_index=True)
    return df_all


if __name__ == "__main__":
    print("Fetching member votes for all votes in vote_index.csv...")
    df = fetch_all_member_votes()
    df.to_csv("data/member_votes.csv", index=False, encoding="utf-8")
    print(f"Saved {len(df)} records to data/member_votes.csv")
