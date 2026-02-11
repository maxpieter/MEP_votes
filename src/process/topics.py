#!/usr/bin/env python3
"""
clean_vote_index.py

Enriches/cleans vote-level topics in data/vote_index.csv by filling missing `topics`
using `oeil_subjects` via:
  1) keyword-to-topic mapping rules (substring match)
  2) phrase matching against an inferred "ground truth" topic vocabulary

Input:
  - data/vote_index.csv (expects columns: id, topics, oeil_subjects)

Output:
  - data/vote_index_clean.csv (adds: topics_filled, topics_effective)
  - data/vote_index_clean.summary.txt (basic summary + sample fills)

Usage:
  python clean_vote_index.py
"""

import os
from collections import Counter
import pandas as pd

INPUT_PATH = "data/vote_index.csv"
OUTPUT_PATH = "data/vote_index_clean.csv"
SUMMARY_PATH = "data/vote_index_clean.summary.txt"


# --- Your manual mapping rules (substring keyword -> topic label) ---
MAPPING_RULES = {
    "children": "Youth and culture",
    "bilateral economic and trade agreements": "International trade",
    "women": "Gender equality",
    "refugee": "Migration",
    "third-country": "Foreign affairs",
    "information and communication technologies": "Digital",
    "ozone": "Climate and environment",
    "fundamental freedoms": "Democracy",
    "investments": "Economy and budget",
    "financial services": "Economy and budget",
    "financial reporting and auditing": "Economy and budget",
    "diseases": "Health",
    "medicine": "Health",
    "protection of privacy and data protection": "Data protection and privacy",
    "principles common to the member states": "Democracy",
    "eu values": "Democracy",
    "common security and defence policy": "Defense",
    "nato": "Foreign affairs",
    "action to combat terrorism": "Security and Justice",
    "structural funds": "Economy and budget",
    "investment funds": "Economy and budget",
    "capital outflow": "Economy and budget",
    "money laundering": "Security and Justice",
    "european investment bank": "Economy and budget",
    "business of parliament": "Democracy",
    "rules of procedure": "Democracy",
    "fundamental rights in the eu": "Human rights",
    "charter": "Human rights",
    "common foreign and security policy": "Foreign affairs",
    "interinstitutional relations": "Democracy",
    "subsidiarity": "Democracy",
    "proportionality": "Democracy",
    "comitology": "Democracy",
    "action to combat crime": "Security and Justice",
    "judicial cooperation in criminal matters": "Security and Justice",
    "committees": "Democracy",
    "interparliamentary delegations": "Democracy",
    "european parliament": "Democracy",
    "elections": "Democracy",
    "direct universal suffrage": "Democracy",
    "cohesion policy": "Economy and budget",
    "company law": "Economy and budget",
    "road transport": "Transport",
    "european ombudsman": "Democracy",
    "people with disabilities": "Social protection",
    "internal market": "Economy and budget",
    "single market": "Economy and budget",
    "innovation": "Digital",
    "state and evolution of the union": "Democracy",
    "european commission": "Democracy",
    "financial management": "Economy and budget",
    "business loans": "Economy and budget",
    "accounting": "Economy and budget",
    "banks and credit": "Economy and budget",
    "small and medium-sized enterprises": "Economy and budget",
    "craft industries": "Economy and budget",
    "citizen rights": "Human rights",
    "scientific and technological cooperation": "Digital",
    "equal treatment": "Human rights",
    "non-discrimination": "Human rights",
    "judicial cooperation in civil": "Security and Justice",
    "macro-financial assistance": "Foreign affairs",
    "transport regulations": "Transport",
    "road safety": "Transport",
    "roadworthiness": "Transport",
    "driving licence": "Transport",
    "implementation of eu law": "Democracy",
    "common commercial policy": "International trade",
    "trans-european transport": "Transport",
    "regional cooperation": "Foreign affairs",
    "cross-border cooperation": "Foreign affairs",
}

# Extra topics you wanted to add regardless of what exists in `topics`
EXTRA_TOPICS = [
    "Human rights",
    "Democracy",
    "Data protection and privacy",
    "Security and Justice",
    "Transport",
]


def build_ground_truth_topics(votes: pd.DataFrame) -> pd.DataFrame:
    """Infer unique topic labels from existing `topics` + manual extra topics."""
    indv_topics = set()

    if "topics" in votes.columns:
        for t in votes["topics"].dropna().astype(str):
            for part in t.split(","):
                p = part.strip()
                if p:
                    indv_topics.add(p)

    for t in EXTRA_TOPICS:
        indv_topics.add(t)

    gt = pd.DataFrame({"topic": sorted(indv_topics)})
    gt["keywords"] = ""
    return gt


def fill_topics_from_subjects(
    votes: pd.DataFrame, ground_truth_topics: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """
    Fill missing topics using oeil_subjects:
      Step 1: mapping rules (keyword substring)
      Step 2: phrase match against ground truth topic phrases
    """
    votes = votes.copy()

    gt_lookup = {row["topic"].lower(): row["topic"] for _, row in ground_truth_topics.iterrows()}

    votes["topics_filled"] = pd.NA
    filled_from_mapping = 0
    filled_from_phrase = 0
    examples = []

    for idx, row in votes.iterrows():
        topics = row.get("topics", pd.NA)
        subjects = row.get("oeil_subjects", pd.NA)

        if pd.isna(topics) and pd.notna(subjects):
            subject_list = [s.strip() for s in str(subjects).split(",") if s.strip()]
            matched = set()

            # Step 1: mapping rules
            for subject in subject_list:
                s_low = subject.lower()
                for kw, topic in MAPPING_RULES.items():
                    if kw in s_low:
                        matched.add(topic)
                        filled_from_mapping += 1
                        break

            # Step 2: phrase matches (consecutive word phrases)
            for subject in subject_list:
                words = subject.lower().split()
                for phrase_len in range(len(words), 0, -1):
                    for start in range(len(words) - phrase_len + 1):
                        phrase = " ".join(words[start : start + phrase_len])
                        if phrase in gt_lookup:
                            matched.add(gt_lookup[phrase])
                            filled_from_phrase += 1

            if matched:
                votes.at[idx, "topics_filled"] = ", ".join(sorted(matched))
                if len(examples) < 15:
                    examples.append((idx, subject_list, votes.at[idx, "topics_filled"]))
        else:
            votes.at[idx, "topics_filled"] = topics

    votes["topics_effective"] = votes["topics_filled"].fillna(votes.get("topics"))

    stats = {
        "filled_from_mapping_hits": filled_from_mapping,
        "filled_from_phrase_hits": filled_from_phrase,
        "n_topics_missing_before": int(votes["topics"].isna().sum()) if "topics" in votes.columns else None,
        "n_topics_missing_after": int(votes["topics_filled"].isna().sum()),
        "examples": examples,
    }
    return votes, stats


def summarize_remaining_missing(votes: pd.DataFrame) -> list[tuple[str, int]]:
    """Top oeil_subjects among rows still missing topics."""
    if "oeil_subjects" not in votes.columns:
        return []

    missing = votes[votes["topics_filled"].isna()]
    c = Counter()
    for subjects in missing["oeil_subjects"]:
        if pd.notna(subjects):
            c.update([s.strip() for s in str(subjects).split(",") if s.strip()])
    return c.most_common(30)


def write_summary(stats: dict, remaining_top: list[tuple[str, int]]) -> None:
    lines = []
    lines.append("vote_index topic fill summary\n")
    lines.append(f"Mapping hits: {stats['filled_from_mapping_hits']}")
    lines.append(f"Phrase-match hits: {stats['filled_from_phrase_hits']}")
    if stats["n_topics_missing_before"] is not None:
        lines.append(f"Missing topics before: {stats['n_topics_missing_before']}")
    lines.append(f"Missing topics after: {stats['n_topics_missing_after']}\n")

    lines.append("Sample filled rows (up to 15):")
    for idx, subjects, topics in stats["examples"]:
        lines.append(f"Row {idx}: {subjects} -> {topics}")
    lines.append("")

    if remaining_top:
        lines.append("Top 30 oeil_subjects among remaining missing rows:")
        for rank, (subj, cnt) in enumerate(remaining_top, 1):
            lines.append(f"{rank}. {subj}: {cnt}")

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Missing {INPUT_PATH}")

    os.makedirs("data", exist_ok=True)

    votes = pd.read_csv(INPUT_PATH)

    required_cols = {"id", "topics", "oeil_subjects"}
    missing_cols = required_cols - set(votes.columns)
    if missing_cols:
        raise KeyError(f"{INPUT_PATH} is missing columns: {sorted(missing_cols)}")

    gt = build_ground_truth_topics(votes)
    votes_clean, stats = fill_topics_from_subjects(votes, gt)
    remaining_top = summarize_remaining_missing(votes_clean)

    votes_clean.to_csv(OUTPUT_PATH, index=False)
    write_summary(stats, remaining_top)

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(f"Missing topics after fill: {stats['n_topics_missing_after']}")


if __name__ == "__main__":
    main()

