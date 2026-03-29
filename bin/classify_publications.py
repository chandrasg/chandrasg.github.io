#!/usr/bin/env python3
"""
Auto-classify BibTeX publications into research themes.
Reads papers.bib, tags each entry with theme keywords, writes back.
Run manually or via GitHub Actions whenever papers.bib is updated.
"""

import re
from collections import Counter

THEMES = {
    "mental-health": [
        "depression", "depress", "loneliness", "lonely", "adhd",
        "stress", "well-being", "wellbeing", "mental health", "anxiety",
        "suicid", "psychiatric", "psycholog", "mood", "emotion",
        "sentiment", "distress", "ptsd", "schizophren", "bipolar",
        "trauma", "resilien", "rumination", "anhedonia", "self-harm",
        "therapist", "therapy", "counseling", "mental illness",
        "affective", "valence", "arousal",
    ],
    "public-health": [
        "covid", "vaccine", "vaccin", "substance", "opioid",
        "cardiovascular", "smoking", "tobacco", "alcohol", "obesity",
        "diabetes", "pandemic", "surveillance", "epidemiolog",
        "mortality", "morbidity", "public health", "health behav",
        "health outcome", "health dispar", "clinical", "patient",
        "electronic health", "ehr", "hospital", "medical", "drug",
        "cannabis", "marijuana", "overdose", "chronic disease",
        "cancer", "symptom", "diagnos", "physician", "nurse",
        "health care", "healthcare", "health record", "comorbid",
        "pregnancy", "prenatal", "maternal", "birth", "infant",
        "pain", "prescription", "pharmacy", "health inform",
    ],
    "cross-cultural": [
        "cultur", "cross-cultur", "emoji", "politeness", "gender",
        "bias", "racial", "race", "disparit", "equity", "fairness",
        "india", "china", "african", "multilingual", "language variation",
        "norm", "global", "non-english", "multilingua", "arabic",
        "hindi", "chinese", "spanish", "south asia", "east asia",
        "low-resource", "international", "countr",
        "stereotype", "discriminat", "underrepresent", "minorit",
    ],
    "health-interventions": [
        "conversational", "chatbot", "intervention", "digital health",
        "behavior change", "mhealth", "smartphone", "mobile health",
        "wearable", "ecological momentary", "telehealth", "telemedicine",
        "agent", "dialogue", "dialog", "chatgpt", "llm", "large language",
        "generative ai", "gpt", "prompt", "reinforcement",
        "recommendation", "nudg", "reminder", "feedback", "coaching",
        "self-manage", "app-based", "text messag", "sms",
    ],
}

# Sub-themes for papers that don't match main themes
SUB_THEMES = {
    "personality-and-social-media": [
        "personality", "big five", "big-five", "openness", "extraver",
        "agreeable", "conscientious", "neurotic", "selfie", "self-present",
        "profile", "social media", "twitter", "facebook", "instagram",
        "reddit", "online", "user", "posted", "post", "tweet",
        "blog", "content analy", "user-generat",
    ],
    "nlp-and-machine-learning": [
        "natural language", "nlp", "language model", "deep learning",
        "neural", "transformer", "bert", "classification", "prediction",
        "machine learning", "supervised", "unsupervised", "embedding",
        "feature", "representation", "annotation", "corpus", "lexic",
        "topic model", "clustering", "regression", "transfer learn",
        "fine-tun", "pretrain", "benchmark",
    ],
    "multimedia-and-images": [
        "image", "visual", "photo", "video", "multimedia", "perception",
        "quality", "aesthetic", "selfie", "picture", "visual content",
        "face", "facial", "recognition", "computer vision",
    ],
}


def extract_field(entry, field):
    match = re.search(rf"{field}\s*=\s*\{{(.+?)\}}", entry, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def classify_entry(entry):
    title = extract_field(entry, "title").lower()
    journal = extract_field(entry, "journal").lower()
    text = f"{title} {journal}"

    matched = []
    for theme, keywords in THEMES.items():
        for kw in keywords:
            if kw in text:
                matched.append(theme)
                break

    if not matched:
        # Try sub-themes
        for theme, keywords in SUB_THEMES.items():
            for kw in keywords:
                if kw in text:
                    matched.append(theme)
                    break

    if not matched:
        matched = ["other"]

    return matched


def update_keywords(entry, themes):
    kw_str = ", ".join(themes)
    entry = re.sub(r"\s*keywords\s*=\s*\{[^}]*\},?\n?", "", entry)
    entry = entry.replace(
        "bibtex_show={true}",
        f"keywords={{{kw_str}}},\n  bibtex_show={{true}}",
    )
    return entry


def main():
    bib_path = "_bibliography/papers.bib"

    with open(bib_path) as f:
        content = f.read()

    parts = re.split(r"(?=\n@)", content)

    theme_counts = Counter()
    classified = 0

    new_parts = []
    for part in parts:
        if not part.strip() or not re.search(r"@\w+\{", part):
            new_parts.append(part)
            continue

        themes = classify_entry(part)
        part = update_keywords(part, themes)
        new_parts.append(part)

        for t in themes:
            theme_counts[t] += 1
        classified += 1

    with open(bib_path, "w") as f:
        f.write("\n".join(new_parts))

    print(f"Classified {classified} publications:")
    for theme, count in theme_counts.most_common():
        print(f"  {theme}: {count}")


if __name__ == "__main__":
    main()
