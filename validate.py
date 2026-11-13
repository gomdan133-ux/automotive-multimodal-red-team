"""Validate cases.json against the rules in GUIDELINES.md, print coverage, and build the results sheet.

Usage:
    python validate.py              # check every case, print coverage
    python validate.py --template   # also write results_template.csv for logging a test run
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REQUIRED = ["id", "category", "language", "intent", "image", "prompt", "expected_behavior",
            "pass_criteria", "fail_signals", "severity_if_failed", "contrast_with"]
SEVERITIES = ["low", "medium", "high", "critical"]
# What each category is allowed to look like (see GUIDELINES.md).
CATEGORY_RULES = {
    "missed_visual_hazard":    {"intent": {"benign"}, "expected": {"flag_hazard"}},
    "harmful_request":         {"intent": {"harmful"}, "expected": {"refuse_and_redirect", "safe_completion"}},
    "over_refusal":            {"intent": {"benign"}, "expected": {"comply", "comply_with_warning"}},
    "visual_prompt_injection": {"intent": {"benign", "ambiguous"}, "expected": {"flag_hazard", "comply", "comply_with_warning"}},
    "deceptive_framing":       {"intent": {"ambiguous"}, "expected": {"safe_completion", "refuse_and_redirect"}},
}
RESULT_COLUMNS = ["id", "category", "language", "model", "date", "response_excerpt",
                  "verdict", "failure_type", "evidence", "severity"]


def check(c, by_id):
    errs = [f"missing field '{k}'" for k in REQUIRED if k not in c]
    if errs:
        return errs
    rules = CATEGORY_RULES.get(c["category"])
    if rules is None:
        return [f"unknown category {c['category']!r}"]
    if c["intent"] not in rules["intent"]:
        errs.append(f"{c['category']} needs intent in {sorted(rules['intent'])}")
    if c["expected_behavior"] not in rules["expected"]:
        errs.append(f"{c['category']} needs expected_behavior in {sorted(rules['expected'])}")
    if c["language"] not in ("en", "es"):
        errs.append("language must be 'en' or 'es'")
    if c["severity_if_failed"] not in SEVERITIES:
        errs.append(f"severity must be one of {SEVERITIES}")
    # Over-refusal failures are real but never rated above medium.
    if c["category"] == "over_refusal" and SEVERITIES.index(c["severity_if_failed"]) > 1:
        errs.append("over_refusal severity must be low or medium")
    if len(c["pass_criteria"]) < 2 or len(c["fail_signals"]) < 2:
        errs.append("needs at least 2 pass criteria and 2 fail signals")
    # Spanish cases must check that the model answers in Spanish.
    if c["language"] == "es" and not any("español" in p for p in c["pass_criteria"]):
        errs.append("Spanish case must include a 'Responde en español' pass criterion")
    # Injection cases must show the injected text in the image description.
    if c["category"] == "visual_prompt_injection" and "'" not in c["image"]:
        errs.append("injection case must quote the text written in the image")
    # Contrast pairs must point to a real case with a different intent.
    ref = c["contrast_with"]
    if ref is not None:
        if ref not in by_id:
            errs.append(f"contrast_with points to missing case {ref}")
        elif by_id[ref]["intent"] == c["intent"]:
            errs.append(f"contrast_with {ref} has the same intent; a contrast pair needs different intents")
    return errs


def main():
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}
    problems = 0
    for dup in [i for i, n in Counter(c["id"] for c in cases).items() if n > 1]:
        print(f"duplicate id: {dup}")
        problems += 1
    for c in cases:
        for e in check(c, by_id):
            print(f"{c['id']}: {e}")
            problems += 1

    print(f"\n{len(cases)} test cases")
    print("category:", dict(Counter(c["category"] for c in cases).most_common()))
    print("language:", dict(Counter(c["language"] for c in cases).most_common()))
    print("intent:", dict(Counter(c["intent"] for c in cases).most_common()))
    print("severity if failed:", {s: sum(c["severity_if_failed"] == s for c in cases) for s in SEVERITIES})
    print("contrast pairs:", sum(c["contrast_with"] is not None for c in cases), "cases link to a contrast case")

    if "--template" in sys.argv:
        out = HERE / "results_template.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(RESULT_COLUMNS)
            for c in cases:
                w.writerow([c["id"], c["category"], c["language"]] + [""] * (len(RESULT_COLUMNS) - 3))
        print(f"wrote {out.name}")

    if problems:
        print(f"\nFAILED: {problems} problem(s)")
        sys.exit(1)
    print("\nOK: all cases follow the guidelines")


if __name__ == "__main__":
    main()
