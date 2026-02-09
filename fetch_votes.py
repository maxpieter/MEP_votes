import pandas as pd
import requests

BASE_URL = "https://howtheyvote.eu/api/votes"
ALL_VOTES = []
PAGE = 1
PAGE_SIZE = 200

while True:
    response = requests.get(f"{BASE_URL}?page={PAGE}&page_size={PAGE_SIZE}")
    response.raise_for_status()
    data = response.json()

    for vote in data["results"]:
        topics = [t["label"] for t in vote.get("topics", [])]
        oeil_labels = [t["label"] for t in vote.get("oeil_subjects", [])]
        eurovoc_concepts = [t["label"] for t in vote.get("eurovoc_concepts", [])]

        ALL_VOTES.append(
            {
                "id": vote["id"],
                "title": vote["display_title"],
                "timestamp": vote["timestamp"],
                "reference": vote["reference"],
                "topics": ", ".join(topics) if topics else None,
                "oeil_subjects": ", ".join(oeil_labels) if oeil_labels else None,
                "eurovoc_concepts": ", ".join(eurovoc_concepts)
                if eurovoc_concepts
                else None,
                "result": vote["result"],
            }
        )

    print(
        f"  Page {PAGE}: {len(data['results'])} votes (total so far: {len(ALL_VOTES)})"
    )

    if not data["has_next"]:
        break
    PAGE += 1

df = pd.DataFrame(ALL_VOTES)
df.to_csv("data/vote_index.csv", index=False, encoding="utf-8")
print(f"Saved {len(df)} votes to data/vote_index.csv")
