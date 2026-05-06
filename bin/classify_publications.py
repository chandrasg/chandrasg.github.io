#!/usr/bin/env python3
"""
Auto-classify BibTeX publications into research themes.
Reads papers.bib, tags each entry with theme keywords, writes back.

When run locally (assets/pdf/ accessible), also extracts abstract text from
PDFs to supplement title-based matching for higher accuracy.

Run manually or via GitHub Actions whenever papers.bib is updated.
"""

import os
import re
import subprocess
from collections import Counter

# ---------------------------------------------------------------------------
# Theme keyword lists
# Each paper is tagged with ALL matching themes.
# A theme matches if the paper's text (title + journal + booktitle + abstract)
# contains ANY keyword from the theme's list.
# ---------------------------------------------------------------------------
THEMES = {
    "mental-health": [
        "depression", "depress", "loneliness", "lonely", "adhd",
        "mental health", "anxiety", "suicid", "psychiatric",
        "self-harm", "therapist", "therapy", "mental illness",
        "ptsd", "schizophren", "bipolar", "trauma", "anhedonia",
        "attention deficit", "well-being", "wellbeing",
        "psychological richness", "happiness", "meaning in life",
        "quarter-life", "rural-urban stress", "stress divide",
        "rural urban stress", "loneliness", "murder of george floyd",
        "gun violence", "substance use recov",
        "mental health chatbot", "depression risk",
    ],
    "public-health": [
        "covid", "vaccine", "vaccin", "opioid", "cardiovascular",
        "pandemic", "surveillance", "epidemiolog", "public health",
        "substance use", "substance abuse", "smoking", "tobacco",
        "overdose", "chronic disease", "obesity", "diabetes",
        "hiv", "ehr", "electronic health record",
        "health disparity", "population health", "semaglutide",
        "tirzepatide", "glp-1", "colorectal cancer",
        "cancer screening", "obstetric", "super-utilizer",
        "hospital visit", "health care facilit", "healthcare super",
        "sub-saharan", "health review", "medical condition",
        "health outcome", "hospital", "medical",
        "comorbid", "pregnancy", "prenatal", "maternal",
        "pain", "prescription", "pharmacy", "mortality", "morbidity",
        "patient", "ascvd", "digital phenotyp",
        "health care review", "drug treatment facilit",
        "contact tracing", "emergency medicine", "sepsis",
        "glioblastoma", "tumor segmentation", "skin lesion",
        "brain tumor", "pathology", "histolog",
    ],
    "cross-cultural": [
        "cross-cultur", "cross-cultural", "multilingual", "multilingua",
        "emoji", "language variation", "global health",
        "myanmar", "world bank", "developing countr",
        "cultural differ", "international comparison",
        "blacklivesmatter", "black lives matter", "rice farming",
        "china and japan", "temporal orientation",
        "politeness", "weibo", "mandarin",
        "racial", "race", "equity", "fairness",
        "disparit", " india", " china", "african", "arabic",
        "hindi", "chinese", "spanish", "south asia", "east asia",
        "international", "stereotype", "discriminat",
        "underrepresent", "minorit", "low-resource",
        "norms in cinema", "gender norms", "cultural variation",
        "urban-rural", "rural urban", "geography", "geographical",
        "geograph",
    ],
    "health-interventions": [
        # Require health context: only match if title/venue implies health use case
        "health chatbot", "health conversational agent",
        "clinical chatbot", "patient chatbot", "medical chatbot",
        "health intervention", "digital health intervention",
        "mhealth", "mobile health", "behavior change",
        "telehealth", "telemedicine", "ecological momentary",
        "patient-generated", "clinical decision support",
        "colorectal screening", "cancer screening intent",
        "health behavior", "health coaching", "self-manag",
        "adherence", "palliative", "patient simulat",
        "vaccine intent", "vaccination intent",
        "llm for health", "generative ai for health",
        "chatbot for health", "voicebot", "voice-based chatbot",
        "conversational ai for health",
        "hpv", "covid-19 vaccine", "vaccine hesitanc",
    ],
    "personality-and-social-media": [
        "personality trait", "big five", "big-five", "openness",
        "extraversion", "extroversion", "extraver", "agreeableness",
        "conscientiousness", "neuroticism", "neurotic",
        "self-presentation", "self-concept", "perceived personality",
        "personality predict", "personality model", "personality-based",
        "vocational interest", "career interest",
        "personality", "selfie", "agreeable", "conscientious",
        "self-disclos", "online identity", "user likes",
        "image likes", "deep representation", "user model",
        "cold-start", "latent factor", "work-personal conflict",
        "quarter-life crisis",
    ],
    "nlp-and-machine-learning": [
        "natural language processing", "nlp", "language model",
        "named entity recognition", "text classification",
        "sentiment analysis", "stance detection", "information extraction",
        "pretrained model", "bert", "transformer",
        "word embedding", "topic model", "annotation scheme",
        "random forest", "botnet detection", "network intrusion",
        "graph neural network", "spatial temporal",
        "multi-agent system", "llm", "large language model",
        "generative ai", "gpt", "neural network",
        "deep learning", "machine learning",
        "benchmark", "lexic", "corpus",
        "clustering", "transfer learn", "fine-tun", "pretrain",
        "predicting social media", "indicative of what",
        "language marker", "language use", "text mining",
        "computational linguistics", "word2vec", "embedding",
        "support vector", "classification", "prediction model",
        "peer influence", "llm agent", "style feature",
        "construct validity", "demographic prompting",
    ],
    "multimedia-and-images": [
        "image quality", "video quality", "multimedia quality",
        "quality of experience", "qoe", "3d image", "3d video",
        "synthesized view", "hazy image", "perceptual quality",
        "just noticeable difference",
        "visual quality", "image aesthetic", "photo aesthetic",
        "audio quality", "bilateral filter", "demosaicking",
        "perceptual audio", "b-shot", "3d feature descriptor",
        "point cloud", "computer vision", "face recognition",
        "image analys", "perceptual", "aesthetic",
        "video qoe", "video recommendation", "voD",
        "multimedia perception", "underwater image",
        "whole slide image", "wsi", "digital pathology",
        "computational pathology", "histopatholog",
        "slide image", "tissue section",
    ],
}

# Ordered priority: determines the first theme listed in keywords field
PRIORITY = [
    "health-interventions",
    "public-health",
    "mental-health",
    "cross-cultural",
    "multimedia-and-images",
    "personality-and-social-media",
    "nlp-and-machine-learning",
]

PDF_DIR = "assets/pdf"


def extract_field(entry, field):
    match = re.search(
        rf"{field}\s*=\s*\{{(.+?)\}}", entry, re.IGNORECASE | re.DOTALL
    )
    return match.group(1).strip() if match else ""


def extract_abstract_from_pdf(pdf_path, max_chars=2000):
    """Extract first 2000 chars of text from PDF (captures abstract on most papers)."""
    try:
        result = subprocess.run(
            ["pdftotext", "-l", "2", pdf_path, "-"],
            capture_output=True, text=True, timeout=10
        )
        text = result.stdout
        # Try to find and return just the abstract section
        text_lower = text.lower()
        abs_start = text_lower.find("abstract")
        if abs_start >= 0:
            abs_text = text[abs_start:abs_start + 1500]
        else:
            abs_text = text[:max_chars]
        return abs_text.lower()
    except Exception:
        return ""


# Cache: bib_key -> abstract_text
_abstract_cache = {}


def get_abstract_text(entry_key):
    """Look up abstract from PDF if available."""
    if entry_key in _abstract_cache:
        return _abstract_cache[entry_key]
    # Try exact match first, then partial key match
    pdf_path = os.path.join(PDF_DIR, f"{entry_key}.pdf")
    if os.path.exists(pdf_path):
        text = extract_abstract_from_pdf(pdf_path)
        _abstract_cache[entry_key] = text
        return text
    _abstract_cache[entry_key] = ""
    return ""


def classify_entry(entry):
    key_match = re.search(r"@\w+\{([\w_\-]+),", entry)
    entry_key = key_match.group(1) if key_match else ""

    title = extract_field(entry, "title").lower()
    journal = extract_field(entry, "journal").lower()
    booktitle = extract_field(entry, "booktitle").lower()
    base_text = f"{title} {journal} {booktitle}"

    # Augment with abstract from PDF if available
    abstract_text = get_abstract_text(entry_key) if entry_key else ""
    text = f"{base_text} {abstract_text}"

    matched = []
    for theme in PRIORITY:
        if any(kw in text for kw in THEMES[theme]):
            matched.append(theme)

    # Remaining themes not in PRIORITY
    for theme, keywords in THEMES.items():
        if theme not in matched and any(kw in text for kw in keywords):
            matched.append(theme)

    return matched if matched else ["other"]


def inject_keywords(entry, themes):
    kw_str = ", ".join(themes)
    # Remove existing keywords field (any spacing variant)
    entry = re.sub(r"\n\s*keywords\s*=\s*\{[^}]*\},?\n?", "\n", entry)
    # Insert before bibtex_show (handles `bibtex_show={true}` and `bibtex_show = {true}`)
    entry = re.sub(
        r"(\s*bibtex_show\s*=\s*\{[^}]+\})",
        f"\n  keywords = {{{kw_str}}},\\1",
        entry,
        count=1,
    )
    return entry


def main():
    bib_path = "_bibliography/papers.bib"

    with open(bib_path) as f:
        content = f.read()

    use_pdfs = os.path.isdir(PDF_DIR)
    if use_pdfs:
        print(f"PDF directory found — augmenting classification with abstract text")
    else:
        print(f"No PDF directory — using title/journal/venue text only")

    parts = re.split(r"(?=\n@)", content)

    theme_counts = Counter()
    classified = 0

    new_parts = []
    for part in parts:
        if not part.strip() or not re.search(r"@\w+\{", part):
            new_parts.append(part)
            continue

        themes = classify_entry(part)
        part = inject_keywords(part, themes)
        new_parts.append(part)

        for t in themes:
            theme_counts[t] += 1
        classified += 1

    with open(bib_path, "w") as f:
        f.write("\n".join(new_parts))

    print(f"\nClassified {classified} publications:")
    for theme, count in theme_counts.most_common():
        print(f"  {theme}: {count}")


if __name__ == "__main__":
    main()
