"""Phase 1 bake-off: score every page reader against the human-reviewed gold pages.

Writes data/eval/results/bakeoff.json and prints a markdown table.
Cost per page comes from the usage log (actual provider-reported or token x price).
"""

from __future__ import annotations

import json
import statistics as st

from eval.extraction_eval import evaluate
from pipeline.config import BAKEOFF_PAGES, INTER, page_id
from pipeline.vlm_parse import model_dir

ROLES = {
    "tesseract-ara": "Reader A / baseline",
    "claude-opus-5-5": "Reader B (gold reader, not eligible)",
    "claude-fable-5-1": "Reader C on bake-off pages (gold reader, not eligible)",
    "surya-ocr-2": "Reader C on other gold pages (not eligible)",
    "gemini-3.5-flash": "candidate",
    "openrouter:google/gemini-3.8-flash": "candidate",
    "openrouter:google/gemini-3.1-pro-preview": "candidate",
    "openrouter:openai/gpt-5.6-terra": "candidate",
    "openrouter:qwen/qwen3-vl-32b-instruct": "candidate",
    "openrouter:google/gemini-3.1-pro-preview@page_parse.v2": "candidate, prompt v2",
    "openrouter:google/gemini-3.8-flash@page_parse.v2": "candidate, prompt v2",
}


def systems(printed: int) -> dict[str, list[dict]]:
    pid = page_id(printed)
    out = {}
    ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
    out["tesseract-ara"] = [{"type": "body", "text": ocr["text"]}]
    sp = INTER / "surya" / f"{pid}.json"
    if sp.exists():
        out["surya-ocr-2"] = json.loads(sp.read_text())["blocks"]
    for m in ROLES:
        p = INTER / "vlm" / model_dir(m) / f"{pid}.json"
        if p.exists():
            out[m] = json.loads(p.read_text())["blocks"]
    return out


def costs() -> dict[str, float]:
    """Mean USD per page parse per (model, prompt), from the saved responses.
    Anthropic costs are token x price; OpenRouter costs are provider-reported; Google AI
    Studio free tier = 0."""
    price = {"claude-opus-5-5": (4, 20), "claude-fable-5-1": (10, 50)}
    per: dict[str, list[float]] = {}
    for f in (INTER.parent / "cache" / "llm" / "vlm_parse").rglob("*.json"):
        d = json.loads(f.read_text())
        if "-retry" in d.get("prompt_version", ""):
            continue
        m = d["model"].removeprefix("anthropic:").removeprefix("google:")
        if d.get("prompt_version") == "page_parse.v2":
            m = f"{m}@page_parse.v2"
        c = d.get("cost_usd")
        if c is None:
            pi, po = price.get(m, (0, 0))
            c = (d["input_tokens"] * pi + d["output_tokens"] * po) / 1e6
        per.setdefault(m, []).append(c)
    return {m: st.mean(v) for m, v in per.items()}


def main() -> None:
    res = {p: evaluate(p, systems(p)) for p in BAKEOFF_PAGES}
    names = [n for n in ROLES if all(n in res[p] for p in BAKEOFF_PAGES)]
    cost = costs()
    rows = []
    for n in names:
        agg = {
            "system": n,
            "role": ROLES[n],
            "cer_strict": st.mean(res[p][n]["strict"]["cer"] for p in BAKEOFF_PAGES),
            "cer_loose": st.mean(res[p][n]["loose"]["cer"] for p in BAKEOFF_PAGES),
            "wer_loose": st.mean(res[p][n]["loose"]["wer"] for p in BAKEOFF_PAGES),
            "per_page_cer_strict": {p: res[p][n]["strict"]["cer"] for p in BAKEOFF_PAGES},
            "footnote_f1": st.mean(res[p][n]["footnote_links"]["f1"] for p in BAKEOFF_PAGES),
            "type_acc": (
                st.mean(res[p][n]["type_acc"] for p in BAKEOFF_PAGES)
                if res[BAKEOFF_PAGES[0]][n]["type_acc"] is not None
                else None
            ),
            "usd_per_page": cost.get(n),
        }
        rows.append(agg)
    out = INTER.parent / "eval" / "results" / "bakeoff.json"
    out.write_text(
        json.dumps({"pages": BAKEOFF_PAGES, "rows": rows, "raw": res}, indent=1, ensure_ascii=False)
    )
    print(
        "| System | Role | CER strict | CER loose | WER loose | Footnote-link F1 | "
        "Block-type acc. | USD/page |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: r["cer_strict"]):
        ta = f"{r['type_acc']:.1%}" if r["type_acc"] is not None else "n/a"
        c = f"{r['usd_per_page']:.3f}" if r["usd_per_page"] is not None else "0 (local)"
        print(
            f"| {r['system']} | {r['role']} | {r['cer_strict']:.1%} | {r['cer_loose']:.1%} | "
            f"{r['wer_loose']:.1%} | {r['footnote_f1']:.2f} | {ta} | {c} |"
        )
    for r in sorted(rows, key=lambda r: r["cer_strict"]):
        print(r["system"], {p: f"{v:.1%}" for p, v in r["per_page_cer_strict"].items()})


if __name__ == "__main__":
    main()
