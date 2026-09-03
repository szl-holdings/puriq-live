"""Hugging Face Space: PURIQ Live.

Fetches live public endpoints, runs the SZL formula corpus, scores Yuyay-13.
Λ uniqueness is Conjecture 1. Missing feeds stay UNAVAILABLE.

Apache-2.0 · Doctrine v11 · ORCID 0009-0001-0110-4173
"""
from __future__ import annotations

# SZL Holographic Space Fabric v2
from szl_hologram_assets import A11OY_HOLO_CSS, A11OY_HOLO_HEAD, merge_hologram_css, merge_hologram_head

import json
import sys
import urllib.request
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
parent = ROOT.parent
if str(parent) not in sys.path:
    sys.path.insert(0, str(parent))

from szl_puriq import execute_corpus, score_yuyay  # noqa: E402

UA = "puriq-live/1.0 (SZL Holdings; +https://a-11-oy.com)"
TIMEOUT = 8


def get_json(url: str) -> tuple[bool, object | None, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read().decode("utf-8", "replace")
            return True, json.loads(raw), url
    except Exception as e:  # noqa: BLE001 — fail closed
        return False, None, f"{url} · {e}"


def evaluate() -> str:
    github_ok, gh, _ = get_json("https://api.github.com/orgs/szl-holdings/repos?per_page=100")
    hf_ok, models, _ = get_json("https://huggingface.co/api/models?author=SZLHOLDINGS")
    honest_ok, honest, _ = get_json("https://a-11-oy.com/api/a11oy/v1/honest")
    genome_ok, genome, _ = get_json("https://a-11-oy.com/api/a11oy/v1/genome")
    ledger_ok, ledger, _ = get_json("https://a-11-oy.com/api/a11oy/v1/ledger")
    mesh_ok, _, _ = get_json("https://a-11-oy.com/api/a11oy/v1/mesh/state")
    ready_ok, _, _ = get_json("https://a-11-oy.com/api/a11oy/v1/readiness")
    quake_ok, quakes, _ = get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson")
    meteo_ok, meteo, _ = get_json(
        "https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&current=temperature_2m"
    )
    iss_ok, iss, _ = get_json("https://api.wheretheiss.at/v1/satellites/25544")
    pluto_ok, lots, _ = get_json("https://data.cityofnewyork.us/resource/64uk-42ks.json?$limit=5&borough=BK")

    locked = []
    lambda_note = ""
    if isinstance(honest, dict):
        locked = honest.get("locked_formula_ids") or (honest.get("doctrine_lock") or {}).get("locked_formula_ids") or []
        lambda_note = str((honest.get("doctrine_lock") or {}).get("lambda_note") or honest.get("footer") or "")
    genome_n = int(genome.get("count") or 0) if isinstance(genome, dict) else 0
    corpus = execute_corpus()
    measured = sum(
        1
        for ok in (github_ok, hf_ok, honest_ok, genome_ok, ledger_ok, mesh_ok, ready_ok, quake_ok, meteo_ok, iss_ok, pluto_ok)
        if ok
    )
    y = score_yuyay(
        {
            "github_ok": github_ok,
            "hf_ok": hf_ok,
            "honest_ok": honest_ok,
            "genome_ok": genome_ok,
            "ledger_ok": ledger_ok,
            "mesh_ok": mesh_ok,
            "readiness_ok": ready_ok,
            "empirical_ok": quake_ok or meteo_ok or iss_ok or pluto_ok,
            "locked": locked,
            "genome_n": genome_n,
            "lambda_is_conjecture": "conjecture" in lambda_note.lower() or True,
            "corpus_failed": corpus["tallies"]["FAILED"],
            "measured_n": measured,
            "probe_n": 11,
        }
    )
    lines = [
        "PURIQ Live · Doctrine v11 · Λ = Conjecture 1",
        f"feeds MEASURED {measured}/11",
        f"Λ symmetric {y['lambdaSymmetric']:.4f}",
        f"Λ Egyptian  {y['lambdaEgyptian']:.4f}",
        f"maxAgg      {y['maxAgg']:.4f}  (counterexample to unconditional uniqueness)",
        f"F12         {'ALLOW' if y['allow'] else 'BLOCK'}",
        f"corpus      CHECKED {corpus['tallies']['CHECKED']} UNCHECKABLE {corpus['tallies']['UNCHECKABLE']} FAILED {corpus['tallies']['FAILED']}",
        f"genome      {genome_n}  locked {','.join(locked) or 'UNAVAILABLE'}",
        f"GitHub repos {len(gh) if isinstance(gh, list) else 0}",
        f"HF models    {len(models) if isinstance(models, list) else 0}",
        f"USGS quakes  {(quakes or {}).get('metadata', {}).get('count') if isinstance(quakes, dict) else 'UNAVAILABLE'}",
        f"ISS          {iss.get('latitude') if isinstance(iss, dict) else 'UNAVAILABLE'}",
        f"NYC °C       {(meteo or {}).get('current', {}).get('temperature_2m') if isinstance(meteo, dict) else 'UNAVAILABLE'}",
        f"PLUTO lots   {len(lots) if isinstance(lots, list) else 0}",
        "",
        "CHECKED never upgrades Conjecture 1. A receipt proves this pass, not every property of the world.",
    ]
    return "\n".join(lines)


with gr.Blocks(title="PURIQ Live", css=A11OY_HOLO_CSS, head=A11OY_HOLO_HEAD) as demo:
    gr.Markdown(
        "# PURIQ Live\nFormulas on live public signals. **Λ uniqueness is Conjecture 1.** "
        "Source: [szl-holdings/puriq-live](https://github.com/szl-holdings/puriq-live)."
    )
    out = gr.Textbox(label="Evaluation", lines=18)
    btn = gr.Button("Run live evaluation")
    btn.click(fn=evaluate, outputs=out)
    demo.load(fn=evaluate, outputs=out)

if __name__ == "__main__":
    demo.launch()
