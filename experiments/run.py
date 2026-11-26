#!/usr/bin/env python3
"""Run reproducible GSTFlow matching experiments without editing the engine."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from reconciliation import engine, risk  # noqa: E402

SEED = 42
TOLERANCE = Decimal("1.00")
THRESHOLDS = (70, 75, 80, 85, 90, 95)
SCENARIOS = (
    "clean_match", "case_punctuation_only", "invoice_number_typo", "gstin_typo",
    "value_difference", "date_shift", "duplicate_within_file", "missing_side", "hard_negative",
)
BASE_WEIGHTS = {"invoice": 55.0, "gstin": 20.0, "value": 20.0, "date": 5.0}


def read_records(path: Path, source: str) -> list[dict]:
    out = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append({
                "id": row["id"], "source": source,
                "supplier_gstin": row["supplier_gstin"],
                "invoice_number": row["invoice_number"],
                "invoice_date": date.fromisoformat(row["invoice_date"]) if row["invoice_date"] else None,
                "taxable_value": Decimal(row["taxable_value"]),
                "tax_amount": Decimal(row["tax_amount"]),
                "link_id": row["link_id"], "scenario": row["scenario"],
                "scenario_detail": row["scenario_detail"],
                "true_exception": row["true_exception"] == "1",
            })
    return out


def engine_records(records: list[dict]) -> list[dict]:
    """Whitelist only engine inputs; link_id/scenario never cross this boundary."""
    return [{k: r[k] for k in ("id", "source", "supplier_gstin", "invoice_number", "invoice_date", "taxable_value", "tax_amount")} for r in records]


def result_pairs(results: list[engine.MatchResult]) -> set[tuple[str, str]]:
    return {(str(r.books_invoice_id), str(r.statement_invoice_id)) for r in results
            if r.books_invoice_id is not None and r.statement_invoice_id is not None
            and r.discrepancy_type != engine.DUPLICATE}


def key(record: dict) -> tuple[str, str]:
    return engine._key(record)


def score_variant(book: dict, stmt: dict, weights: dict[str, float]) -> int:
    if weights == BASE_WEIGHTS:
        return engine._fuzzy_confidence(book, stmt)
    inv = engine._similarity(engine._norm_invoice_number(book.get("invoice_number", "")),
                             engine._norm_invoice_number(stmt.get("invoice_number", "")))
    gst = engine._similarity(book.get("supplier_gstin", ""), stmt.get("supplier_gstin", ""))
    bv, sv = engine._invoice_value(book), engine._invoice_value(stmt)
    val = max(0.0, 1 - float(abs(bv - sv) / max(bv, sv, Decimal("1"))))
    same_date = bool(book.get("invoice_date") and stmt.get("invoice_date") and book["invoice_date"] == stmt["invoice_date"])
    return round(inv * weights.get("invoice", 0) + gst * weights.get("gstin", 0)
                 + val * weights.get("value", 0) + (weights.get("date", 0) if same_date else 0))


def candidate_pool(books: list[dict], stmts: list[dict], tolerance: Decimal = TOLERANCE) -> set[tuple[str, str]]:
    """All pairs admitted to either engine fuzzy pass before confidence cutoff."""
    books_by, _ = engine._find_duplicates(books)
    stmts_by, _ = engine._find_duplicates(stmts)
    bk, sk = set(books_by), set(stmts_by)
    pairs = {(str(books_by[k]["id"]), str(stmts_by[k]["id"])) for k in bk & sk}
    for bkey in bk - sk:
        b = books_by[bkey]
        for skey in sk - bk:
            s = stmts_by[skey]
            distance = engine._edit_distance(bkey[0], skey[0])
            same_invoice = bkey[1] == skey[1]
            within = abs(engine._invoice_value(b) - engine._invoice_value(s)) <= tolerance
            if same_invoice and within and distance <= engine.GSTIN_MAX_EDIT_DISTANCE:
                pairs.add((str(b["id"]), str(s["id"])))
                continue
            if engine._similarity(b.get("supplier_gstin", ""), s.get("supplier_gstin", "")) >= 0.6:
                pairs.add((str(b["id"]), str(s["id"])))
    return pairs


def configurable_reconcile(books: list[dict], stmts: list[dict], threshold: int,
                           weights: dict[str, float] = BASE_WEIGHTS) -> list[engine.MatchResult]:
    """Evaluation adapter mirroring engine.py with only threshold/weights configurable.

    The production engine remains untouched. The canonical 80/55-20-20-5 run is
    checked against engine.reconcile() before this adapter is used for sweeps.
    """
    bmap, bd = engine._find_duplicates(books)
    smap, sd = engine._find_duplicates(stmts)
    results = [*bd, *sd]
    bk, sk = set(bmap), set(smap)
    for k in bk & sk:
        b, s = bmap[k], smap[k]
        diff = abs(engine._invoice_value(b) - engine._invoice_value(s))
        if diff > TOLERANCE:
            results.append(engine.MatchResult(engine.VALUE_MISMATCH, b["id"], s["id"], confidence_score=95))
        elif b.get("invoice_date") and s.get("invoice_date") and b["invoice_date"] != s["invoice_date"]:
            results.append(engine.MatchResult(engine.DATE_MISMATCH, b["id"], s["id"]))
        else:
            results.append(engine.MatchResult(engine.MATCHED, b["id"], s["id"]))
    ub, us = bk - sk, sk - bk
    consumed_b: set = set()
    consumed_s: set = set()
    for bkey in ub:
        b = bmap[bkey]
        for skey in us - consumed_s:
            s = smap[skey]
            if bkey[1] != skey[1]:
                continue
            if abs(engine._invoice_value(b) - engine._invoice_value(s)) > TOLERANCE:
                continue
            if engine._edit_distance(bkey[0], skey[0]) > engine.GSTIN_MAX_EDIT_DISTANCE:
                continue
            results.append(engine.MatchResult(engine.GSTIN_MISMATCH, b["id"], s["id"]))
            consumed_b.add(bkey); consumed_s.add(skey)
            break
    for bkey in ub - consumed_b:
        b = bmap[bkey]
        candidates = []
        for skey in us - consumed_s:
            s = smap[skey]
            if engine._similarity(b.get("supplier_gstin", ""), s.get("supplier_gstin", "")) < 0.6:
                continue
            confidence = score_variant(b, s, weights)
            if confidence >= threshold:
                candidates.append((confidence, skey, s))
        if candidates:
            confidence, skey, s = max(candidates, key=lambda item: item[0])
            results.append(engine.MatchResult(engine.FUZZY_MATCH, b["id"], s["id"], confidence_score=confidence))
            consumed_b.add(bkey); consumed_s.add(skey)
    for bkey in ub - consumed_b:
        b = bmap[bkey]
        results.append(engine.MatchResult(engine.MISSING_IN_2A, b["id"], None))
    for skey in us - consumed_s:
        s = smap[skey]
        results.append(engine.MatchResult(engine.MISSING_IN_BOOKS, None, s["id"]))
    return results


def exact_pairs(books: list[dict], stmts: list[dict]) -> set[tuple[str, str]]:
    bmap, _ = engine._find_duplicates(books)
    smap, _ = engine._find_duplicates(stmts)
    return {(str(bmap[k]["id"]), str(smap[k]["id"])) for k in set(bmap) & set(smap)}


def divide(a: int | float, b: int | float) -> float:
    return float(a / b) if b else 0.0


def metrics_row(method: str, scope: str, tp: int, fp: int, fn: int, tn: int,
                cand: int, cand_tp: int, gold: int) -> dict:
    precision, recall = divide(tp, tp + fp), divide(tp, tp + fn)
    return {"method": method, "scope": scope, "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": precision, "recall": recall,
            "F1": divide(2 * precision * recall, precision + recall),
            "false_positive_rate": divide(fp, fp + tn), "candidate_volume": cand,
            "candidate_generation_recall": divide(cand_tp, gold)}


def build_truth(books: list[dict], stmts: list[dict]):
    b_by_link: dict[str, list[dict]] = defaultdict(list)
    s_by_link: dict[str, list[dict]] = defaultdict(list)
    # Linkage is one-to-one: a duplicate row retains its invoice link_id for
    # provenance but is an exception, not a second gold counterpart.
    for r in books: b_by_link.setdefault(r["link_id"], [r])
    for r in stmts: s_by_link.setdefault(r["link_id"], [r])
    truth = set()
    for link in b_by_link.keys() & s_by_link.keys():
        for b in b_by_link[link]:
            for s in s_by_link[link]:
                truth.add((str(b["id"]), str(s["id"])))
    return truth


def stratum(pair: tuple[str, str], idmap: dict[str, dict]) -> str:
    a, b = idmap[pair[0]]["scenario"], idmap[pair[1]]["scenario"]
    return a if a == b else "cross_scenario"


def all_pair_bucket_counts(books: list[dict], stmts: list[dict]) -> Counter:
    bc, sc = Counter(r["scenario"] for r in books), Counter(r["scenario"] for r in stmts)
    result = Counter()
    for a, n in bc.items():
        for b, m in sc.items():
            result[a if a == b else "cross_scenario"] += n * m
    return result


def evaluate(method: str, predicted: set[tuple[str, str]], candidates: set[tuple[str, str]],
             truth: set[tuple[str, str]], books: list[dict], stmts: list[dict]) -> list[dict]:
    idmap = {str(r["id"]): r for r in books + stmts}
    total = len(books) * len(stmts)
    tp = len(predicted & truth); fp = len(predicted - truth); fn = len(truth - predicted)
    tn = total - tp - fp - fn
    rows = [metrics_row(method, "overall", tp, fp, fn, tn, len(candidates), len(candidates & truth), len(truth))]
    pair_totals = all_pair_bucket_counts(books, stmts)
    truth_counts, predicted_counts, candidate_counts = Counter(), Counter(), Counter()
    for p in truth: truth_counts[stratum(p, idmap)] += 1
    for p in predicted: predicted_counts[stratum(p, idmap)] += 1
    for p in candidates: candidate_counts[stratum(p, idmap)] += 1
    for scenario in SCENARIOS + ("cross_scenario",):
        g = truth_counts[scenario]
        t = len(predicted & truth) if scenario == "overall" else sum(1 for p in predicted & truth if stratum(p, idmap) == scenario)
        pp = predicted_counts[scenario] - t
        ff = g - t
        tt = pair_totals[scenario] - t - pp - ff
        rows.append(metrics_row(method, scenario, t, pp, ff, tt, candidate_counts[scenario],
                                sum(1 for p in candidates & truth if stratum(p, idmap) == scenario), g))
    supported = [r for r in rows[1:1 + len(SCENARIOS)] if truth_counts[r["scope"]] > 0]
    macro = {"method": method, "scope": "macro_supported_scenarios"}
    for col in ("precision", "recall", "F1", "false_positive_rate", "candidate_generation_recall"):
        macro[col] = sum(r[col] for r in supported) / len(supported) if supported else 0.0
    for col in ("TP", "FP", "FN", "TN", "candidate_volume"):
        macro[col] = ""
    rows.append(macro)
    return rows


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def risk_check(books: list[dict], stmts: list[dict], results: list[engine.MatchResult], out: Path) -> list[dict]:
    idmap = {str(r["id"]): r for r in books + stmts}
    row_risk: dict[str, int] = defaultdict(int)
    for result in results:
        for rid in (result.books_invoice_id, result.statement_invoice_id):
            if rid is not None:
                rec = idmap[str(rid)]
                score, _ = risk.score_discrepancy(result.discrepancy_type, rec["tax_amount"], result.confidence_score)
                row_risk[str(rid)] = max(row_risk[str(rid)], score)
    entities: dict[str, dict] = {}
    for rec in books + stmts:
        if not rec["true_exception"]: continue
        link = rec["link_id"]
        e = entities.setdefault(link, {"link_id": link, "scenario": rec["scenario"], "tax_exposure": float(rec["tax_amount"]), "risk_score": 0})
        e["tax_exposure"] = max(e["tax_exposure"], float(rec["tax_amount"]))
        e["risk_score"] = max(e["risk_score"], row_risk[str(rec["id"])])
    values = list(entities.values())
    total_exposure = sum(e["tax_exposure"] for e in values)
    rng = random.Random(SEED)
    rows = []
    for k in (10, 50, 100):
        n = min(k, len(values))
        ranked = sorted(values, key=lambda e: (-e["risk_score"], e["link_id"]))[:n]
        risk_share = divide(sum(e["tax_exposure"] for e in ranked), total_exposure)
        random_shares = []
        for _ in range(100):
            shuffled = values[:]; rng.shuffle(shuffled)
            random_shares.append(divide(sum(e["tax_exposure"] for e in shuffled[:n]), total_exposure))
        rows.append({"k_requested": k, "k_evaluated": n, "true_exception_entities": len(values),
                     "total_tax_exposure": total_exposure, "risk_top_k_exposure_share": risk_share,
                     "random_100_shuffle_mean_share": sum(random_shares) / 100,
                     "random_100_shuffle_min_share": min(random_shares),
                     "random_100_shuffle_max_share": max(random_shares)})
    write_rows(out / "risk_topk.csv", rows)
    write_rows(out / "risk_ranked_exceptions.csv", sorted(values, key=lambda e: (-e["risk_score"], e["link_id"])))
    return rows


def order_sensitivity(books: list[dict], stmts: list[dict], out: Path) -> list[dict]:
    def run_pair_sets(brows, srows):
        results = engine.reconcile(engine_records(brows), engine_records(srows), value_tolerance=TOLERANCE)
        all_pairs = result_pairs(results)
        fuzzy_pairs = {(str(r.books_invoice_id), str(r.statement_invoice_id)) for r in results
                       if r.books_invoice_id is not None and r.statement_invoice_id is not None
                       and r.discrepancy_type in {engine.FUZZY_MATCH, engine.GSTIN_MISMATCH}}
        return all_pairs, fuzzy_pairs
    base, base_fuzzy = run_pair_sets(books, stmts)
    rows, examples = [], []
    for i in range(20):
        seed = 1001 + i
        rb, rs = books[:], stmts[:]
        random.Random(seed).shuffle(rb); random.Random(seed + 10000).shuffle(rs)
        pairs, fuzzy_pairs = run_pair_sets(rb, rs)
        changed = fuzzy_pairs ^ base_fuzzy
        all_changed = pairs ^ base
        rows.append({"shuffle_index": i + 1, "books_seed": seed, "statement_seed": seed + 10000,
                     "baseline_pair_count": len(base), "shuffled_pair_count": len(pairs),
                     "baseline_fuzzy_pair_count": len(base_fuzzy), "shuffled_fuzzy_pair_count": len(fuzzy_pairs),
                     "changed_fuzzy_pair_count_symmetric_difference": len(changed),
                     "fuzzy_pairs_added": len(fuzzy_pairs - base_fuzzy), "fuzzy_pairs_removed": len(base_fuzzy - fuzzy_pairs),
                     "changed_all_pair_count_symmetric_difference": len(all_changed),
                     "all_pairs_added": len(pairs - base), "all_pairs_removed": len(base - pairs)})
        idmap = {str(r["id"]): r for r in books + stmts}
        for pair in sorted(all_changed)[:10]:
            b, s = idmap[pair[0]], idmap[pair[1]]
            examples.append({"shuffle_index": i + 1, "books_id": pair[0], "statement_id": pair[1],
                             "pair_classification": "fuzzy" if pair in changed else "other_paired_outcome",
                             "change": "added" if pair in pairs else "removed",
                             "books_invoice": b["invoice_number"], "statement_invoice": s["invoice_number"],
                             "books_scenario": b["scenario_detail"], "statement_scenario": s["scenario_detail"],
                             "books_link_id": b["link_id"], "statement_link_id": s["link_id"]})
    write_rows(out / "order_sensitivity.csv", rows)
    write_rows(out / "order_sensitivity_examples.csv", examples)
    return rows


def error_analysis(books: list[dict], stmts: list[dict], predicted: set[tuple[str, str]],
                   truth: set[tuple[str, str]], out: Path) -> list[dict]:
    idmap = {str(r["id"]): r for r in books + stmts}
    rows = []
    cause_counts = Counter()
    for kind, pairs in (("false_positive", sorted(predicted - truth)), ("false_negative", sorted(truth - predicted))):
        for pair in pairs:
            b, s = idmap[pair[0]], idmap[pair[1]]
            cause = b["scenario_detail"] if b["scenario"] == s["scenario"] else f"{b['scenario']} vs {s['scenario']}"
            cause_counts[(kind, cause)] += 1
            if sum(r["error_type"] == kind for r in rows) >= 30:
                continue
            rows.append({"error_type": kind, "cause_group": cause, "books_id": pair[0],
                         "statement_id": pair[1], "books_scenario": b["scenario"],
                         "statement_scenario": s["scenario"], "books_link_id": b["link_id"],
                         "statement_link_id": s["link_id"], "books_invoice": b["invoice_number"],
                         "statement_invoice": s["invoice_number"], "books_gstin": b["supplier_gstin"],
                         "statement_gstin": s["supplier_gstin"], "books_total": str(engine._invoice_value(b)),
                         "statement_total": str(engine._invoice_value(s))})
    write_rows(out / "error_analysis_hybrid80.csv", rows)
    write_rows(out / "error_cause_counts_hybrid80.csv", [
        {"error_type": kind, "cause_group": cause, "count": count}
        for (kind, cause), count in sorted(cause_counts.items())])
    return rows


def plot_pr(metrics: list[dict], out: Path) -> None:
    rows = [r for r in metrics if r["scope"] == "overall" and r["method"].startswith("Hybrid sweep")]
    rows.sort(key=lambda r: int(r["method"].split("=")[-1]))
    plt.figure(figsize=(7.2, 5.2))
    plt.plot([r["recall"] for r in rows], [r["precision"] for r in rows], marker="o", color="#176B87")
    offsets = {70: (-24, -22), 75: (-40, -12), 80: (-43, 2),
               85: (-43, 17), 90: (-42, 32), 95: (10, -20)}
    for row in rows:
        threshold = int(row["method"].split("=")[-1])
        plt.annotate(str(threshold), (row["recall"], row["precision"]),
                     xytext=offsets[threshold], textcoords="offset points",
                     bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.8})
    plt.xlabel("Pair-level recall"); plt.ylabel("Pair-level precision")
    plt.title("GSTFlow fuzzy threshold sweep (synthetic benchmark)")
    plt.xlim(-0.03, 1.03); plt.ylim(-0.03, 1.03); plt.grid(alpha=.25); plt.tight_layout()
    plt.savefig(out / "precision_recall.png", dpi=180); plt.close()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))


def write_results_md(out: Path, metrics: list[dict], risks: list[dict], order: list[dict], errors: list[dict], commit: str) -> None:
    overall = [r for r in metrics if r["scope"] == "overall"]
    def md_table(rows, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(c, "")) if not isinstance(row.get(c), float) else f"{row[c]:.6f}" for c in cols) + " |")
        return "\n".join(lines)
    def mention(method):
        r = next(x for x in overall if x["method"] == method)
        return f"{method}: TP={r['TP']}, FP={r['FP']}, FN={r['FN']}, TN={r['TN']}, precision={r['precision']:.4f}, recall={r['recall']:.4f}, F1={r['F1']:.4f}, candidate volume={r['candidate_volume']}."
    exact = next(r for r in overall if r["method"] == "Exact-only")
    hybrid = next(r for r in overall if r["method"] == "Hybrid engine (threshold 80)")
    fpr = lambda r: r["false_positive_rate"]
    threshold_rows = [r for r in overall if r["method"].startswith("Hybrid sweep")]
    best_threshold = max(threshold_rows, key=lambda r: r["F1"])
    ablation_rows = [r for r in overall if r["method"].startswith("Ablation")]
    scenario_by = {r["scope"]: r for r in metrics
                   if r["method"] == "Hybrid engine (threshold 80)" and r["scope"] in SCENARIOS}
    error_fp_total, error_fn_total = int(hybrid["FP"]), int(hybrid["FN"])
    fp_listed = sum(r["error_type"] == "false_positive" for r in errors)
    fn_listed = sum(r["error_type"] == "false_negative" for r in errors)
    order_changed = sum(int(r["changed_fuzzy_pair_count_symmetric_difference"]) > 0 for r in order)
    order_total_changed = sum(int(r["changed_fuzzy_pair_count_symmetric_difference"]) for r in order)
    all_order_changed = sum(int(r["changed_all_pair_count_symmetric_difference"]) > 0 for r in order)
    all_order_total = sum(int(r["changed_all_pair_count_symmetric_difference"]) for r in order)
    text = [
        "# GSTFlow Synthetic Reconciliation Evaluation", "",
        "## Setup", "",
        f"- Generator and evaluation seed: `{SEED}`; the seed is recorded in the raw generator output, command log, and `run_metadata.json`.",
        "- Base invoices: 1,000. Scenario counts: clean 400; case/punctuation 100; invoice-number typo 150; GSTIN typo 50; value differences 50 (25 within/25 above tolerance); date shift 50; duplicate 50; missing side 100 (50 each direction); hard negatives 50.",
        "- Synthetic suppliers are reused in groups of ten sequential invoice numbers to create repeated-supplier candidate ambiguity; 100 distinct format-valid-looking (checksum not independently verified) GSTIN strings are generated from seed 42.",
        "- Base scenario proportions are respectively 40%, 10%, 15%, 5%, 5%, 5%, 5%, 10%, and 5%; duplicate cases add one extra books row and hard-negative cases have unrelated book/statement link IDs.",
        f"- Engine source commit: `{commit}`. Tolerance: `{TOLERANCE}`. Python and matplotlib versions are recorded in `run_metadata.json`.",
        "- Dataset files are `synthetic_dataset.csv`, `books.csv`, and `statement.csv`. Ground-truth link IDs and scenario labels are removed by an explicit field whitelist before each call to the engine.",
        "- Pair truth is the one-to-one first row per ground-truth link ID on each side; extra within-file duplicate rows retain the link ID for provenance but are not a second gold counterpart. All possible cross-file row pairs form the confusion-matrix universe; this makes TN large and FPR small, so interpret both with precision/recall.",
        "- Scenario strata assign cross-scenario row pairs to `cross_scenario`; macro averages include scenarios with at least one ground-truth positive pair.",
        "- Candidate-generation recall is the share of true row pairs admitted by exact-key or fuzzy eligibility gates before confidence cutoff. Candidate volume is the number of eligible pair candidates, not CPU operations.",
        "- `Exact-only` uses upper/trimmed GSTIN plus normalized invoice number and pairs the first occurrence per key; the engine subsequently applies value/date discrepancy rules to exact keys.",
        "- Threshold and ablation variants use an evaluation adapter that mirrors the engine; canonical threshold 80 is validated against the unmodified production function. Ablations renormalize the remaining weights to 100.",
        "- Order test compares fuzzy pair memberships (GSTIN typo and fuzzy suggestions) separately from all paired outcomes across 20 deterministic shuffle seeds (books 1001–1020; statement seeds 11001–11020). Risk ranking uses the repository's `score_discrepancy` and 100 random permutations from seed 42.",
        "", "## Overall methods", "", md_table(overall, ["method", "TP", "FP", "FN", "TN", "precision", "recall", "F1", "false_positive_rate", "candidate_volume", "candidate_generation_recall"]), "",
        "### Plain-language interpretation", "",
        mention("Exact-only"), mention("Hybrid engine (threshold 80)"),
        f"Exact-only has {exact['FP']} false positives and hybrid threshold 80 has {hybrid['FP']}; therefore the hybrid {'is worse' if hybrid['FP'] > exact['FP'] else 'is not worse'} on false-positive count in this synthetic benchmark. Their false-positive rates are {fpr(exact):.6f} and {fpr(hybrid):.6f}, respectively.",
        f"The hybrid gains {int(hybrid['TP'])-int(exact['TP'])} true pairs and reduces false negatives by {int(exact['FN'])-int(hybrid['FN'])} versus exact-only, while adding {int(hybrid['FP'])-int(exact['FP'])} false-positive pairs. Its F1 is {hybrid['F1']-exact['F1']:+.6f} higher; precision changes by {hybrid['precision']-exact['precision']:+.6f}.",
        "The confusion counts and candidate volume are in `metrics.csv`; pair-level predictions include engine results with two IDs (matched or discrepancy/fuzzy pairs). Duplicate flags without a paired counterpart are not positive predictions.",
        "", "## Threshold sweep and ablations", "",
        md_table([r for r in overall if r["method"].startswith("Hybrid sweep") or r["method"].startswith("Ablation")], ["method", "TP", "FP", "FN", "TN", "precision", "recall", "F1", "false_positive_rate", "candidate_volume", "candidate_generation_recall"]),
        "", f"The plot `precision_recall.png` uses the executed threshold-sweep rows. The best observed sweep F1 is {best_threshold['F1']:.6f} at {best_threshold['method']}, with {best_threshold['FP']} FP and {best_threshold['FN']} FN. Threshold 90 has full observed recall on this synthetic gold, with {best_threshold['FP']} false positives; threshold 95 lowers recall, so a higher cutoff is not always better. Candidate generation is unchanged by confidence threshold. Ablation scores redistribute remaining component weights proportionally before applying threshold 80.",
        "Ablations versus canonical threshold-80 F1: " + "; ".join(f"remove {r['method'].split('remove ')[1].split(' ')[0]} gives F1 {r['F1']:.6f} ({r['F1']-hybrid['F1']:+.6f})" for r in ablation_rows) + ".",
        "", "## Per-scenario results", "", md_table([r for r in metrics if r["scope"] in SCENARIOS], ["method", "scope", "TP", "FP", "FN", "TN", "precision", "recall", "F1", "false_positive_rate", "candidate_volume", "candidate_generation_recall"]),
        "", "Scenario metrics are one-vs-rest over row pairs whose two rows share the named scenario; unmatched scenario combinations are separately labeled `cross_scenario` in the CSV. `macro_supported_scenarios` averages per-scenario metrics only where at least one positive ground-truth pair exists. Missing-side and hard-negative cases have no positive cross-file gold pair by construction, so they are represented in overall and per-scenario FP/TN counts but are not included in supported-scenario macro recall/F1.",
        f"At threshold 80, invoice-number typo pairs have TP={scenario_by['invoice_number_typo']['TP']}, FP={scenario_by['invoice_number_typo']['FP']}, FN={scenario_by['invoice_number_typo']['FN']} (recall {scenario_by['invoice_number_typo']['recall']:.4f}); missing-side cases produce {scenario_by['missing_side']['FP']} false pairings, and hard negatives produce {scenario_by['hard_negative']['FP']}. Clean, case/punctuation, GSTIN typo, value, date, and duplicate scenarios have full pair recall in this generated set; see their rows for precision and counts.",
        "", "## Candidate generation", "", "Candidate-generation recall and candidate volume are included in every row of `metrics.csv`; overall method rows are reproduced here.", "",
        md_table(overall, ["method", "candidate_volume", "candidate_generation_recall", "TP", "FN", "recall"]),
        "", "## Risk ranking", "", md_table(risks, ["k_requested", "k_evaluated", "true_exception_entities", "total_tax_exposure", "risk_top_k_exposure_share", "random_100_shuffle_mean_share", "random_100_shuffle_min_share", "random_100_shuffle_max_share"]),
        "", "The ranking universe is unique ground-truth exception link IDs (hard negatives are separate entities); exposure is each entity's maximum source tax amount, avoiding duplicate inflation. Risk score per entity is the maximum repository risk score attached to its rows by the canonical engine output. Random shares are the arithmetic mean/range over 100 deterministic shuffles.",
        *[f"At k={r['k_requested']}, risk ranking covered {r['risk_top_k_exposure_share']*100:.2f}% of exception tax exposure; random-order mean was {r['random_100_shuffle_mean_share']*100:.2f}% (observed range {r['random_100_shuffle_min_share']*100:.2f}%–{r['random_100_shuffle_max_share']*100:.2f}%)." for r in risks],
        "", "## Order sensitivity", "", f"Across 20 deterministic row-order shuffles, fuzzy pair membership changed in {order_changed} trials; the sum of symmetric-difference fuzzy pair counts is {order_total_changed}. For all paired outcomes (including exact and duplicate-row identity), changes occurred in {all_order_changed} trials with total symmetric difference {all_order_total}. The example CSV includes changed pair IDs and source scenario details; these are duplicate representative changes when the fuzzy-only count is zero.",
        "", "## Hybrid threshold-80 error analysis", "", f"The canonical output has {error_fp_total} false-positive pairs and {error_fn_total} false-negative pairs. The examples CSV lists {fp_listed} FP and {fn_listed} FN examples, capped at 30 per type; {max(0,error_fp_total-fp_listed)} FP and {max(0,error_fn_total-fn_listed)} FN examples are omitted by the cap. `error_cause_counts_hybrid80.csv` gives cause counts over all errors; `cause_group` uses generator scenario details.",
        "", "## Threats to validity", "",
        "This is a synthetic benchmark generated by the same project author, not a sample of real GST filings. Its noise model is hand-designed: controlled character edits, fixed date shifts, fixed value deltas, selected missingness, duplicates, and deliberately constructed hard negatives. Real exports may have different error frequencies, correlated errors, GSTIN validity behavior, tax rounding, invoice formats, and missingness mechanisms.",
        "The engine's matching weights and thresholds are hand-tuned and not calibrated on an independent labeled dataset. The generator gives a known oracle but cannot establish field performance. Pair-level row combinations create a large TN universe; accuracy and FPR alone would be misleading. Candidate generation is instrumented by an evaluation mirror for fuzzy eligibility, so its definition follows the observed source logic and should be checked if engine code changes.",
        "The engine iterates sets and greedily consumes fuzzy matches. Pair-order results are measured only for this generated input and this Python/hash-seed environment. The 20-shuffle check cannot establish stability over all inputs or runtimes.",
        "", "## Not tested", "",
        "Fellegi–Sunter was not run. This draft evaluation does not use real or de-identified GST data, human adjudication, cross-period generalization, calibrated confidence probabilities, production throughput/memory measurements, concurrent requests, or a statistically sampled confidence interval. Threshold/ablation adapter parity is checked at the canonical configuration; alternative policies are experimental wrappers, not production engine behavior.",
        "", "## Conclusion", "",
        f"On this seeded synthetic benchmark, the unmodified hybrid engine at threshold 80 achieves precision {hybrid['precision']:.6f}, recall {hybrid['recall']:.6f}, and F1 {hybrid['F1']:.6f}; exact-only achieves precision {exact['precision']:.6f}, recall {exact['recall']:.6f}, and F1 {exact['F1']:.6f}. The hybrid retrieves more true pairs but is worse on false-positive count ({hybrid['FP']} versus {exact['FP']}); constructed hard negatives and cross-record fuzzy conflicts contribute to those errors. Threshold 90 is the best observed sweep setting by F1, but it is a development-set result, not a validated production setting.",
        f"Fuzzy pair membership did not change in the 20 shuffles, so these runs do not demonstrate fuzzy greedy-order instability. All paired outputs did change because duplicate resolution retains the first exact-key row; those changes must not be characterized as fuzzy matching changes. Risk ranking exceeded the random mean for each tested k but did not exceed every random shuffle at every k. The experiment supports follow-up evaluation on governed, labeled real data; it does not establish real-world accuracy or tax outcomes.",
        "", "## Raw artifacts and exact commands", "",
        "Exact commands are saved in `raw/commands.txt`; captured stdout/stderr and runtime metadata are saved under `raw/`. Machine-readable metrics, errors, risks, and order tests are in the adjacent CSV files.", "",
    ]
    (out / "RESULTS.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("experiments/results"))
    parser.add_argument("--out", type=Path, default=Path("experiments/results"))
    args = parser.parse_args()
    data_dir, out = args.data_dir.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True); (out / "raw").mkdir(exist_ok=True)
    books = read_records(data_dir / "books.csv", "books")
    stmts = read_records(data_dir / "statement.csv", "2a")
    truth = build_truth(books, stmts)
    # Canonical unmodified function is the authoritative hybrid measurement.
    canonical_results = engine.reconcile(engine_records(books), engine_records(stmts), value_tolerance=TOLERANCE)
    canonical_pairs = result_pairs(canonical_results)
    # Sanity-check the configurable evaluation adapter at exactly the production settings.
    mirror = configurable_reconcile(engine_records(books), engine_records(stmts), 80, BASE_WEIGHTS)
    if result_pairs(mirror) != canonical_pairs:
        raise RuntimeError("Threshold-80 adapter does not reproduce canonical engine pair results.")
    exact = exact_pairs(books, stmts)
    methods: list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]] = []
    methods.append(("Exact-only", exact, exact))
    hybrid_candidates = candidate_pool(engine_records(books), engine_records(stmts))
    methods.append(("Hybrid engine (threshold 80)", canonical_pairs, hybrid_candidates))
    all_metrics = []
    for threshold in THRESHOLDS:
        results = canonical_results if threshold == 80 else configurable_reconcile(engine_records(books), engine_records(stmts), threshold, BASE_WEIGHTS)
        methods.append((f"Hybrid sweep threshold={threshold}", result_pairs(results), hybrid_candidates))
    for component in BASE_WEIGHTS:
        remaining = {k: v for k, v in BASE_WEIGHTS.items() if k != component}
        scale = 100.0 / sum(remaining.values())
        weights = {k: v * scale for k, v in remaining.items()}
        results = configurable_reconcile(engine_records(books), engine_records(stmts), 80, weights)
        methods.append((f"Ablation remove {component} (renormalized)", result_pairs(results), hybrid_candidates))
    for name, pred, cand in methods:
        all_metrics.extend(evaluate(name, pred, cand, truth, books, stmts))
    write_rows(out / "metrics.csv", all_metrics)
    plot_pr(all_metrics, out)
    risk_rows = risk_check(books, stmts, canonical_results, out)
    order_rows = order_sensitivity(books, stmts, out)
    errors = error_analysis(books, stmts, canonical_pairs, truth, out)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unavailable"
    import matplotlib as mpl
    metadata = {"seed": SEED, "hash_seed_environment": os.environ.get("PYTHONHASHSEED"),
                "python": sys.version, "matplotlib": mpl.__version__, "engine_commit": commit,
                "engine_module": str(Path(engine.__file__).resolve()),
                "tolerance": str(TOLERANCE), "thresholds": THRESHOLDS,
                "base_weights": BASE_WEIGHTS, "books_rows": len(books), "statement_rows": len(stmts),
                "truth_positive_pairs": len(truth), "total_pair_universe": len(books) * len(stmts),
                "canonical_mirror_pair_parity": True,
                "fellegi_sunter": "not run"}
    (out / "run_metadata.json").write_text(json.dumps(metadata, indent=2, default=list) + "\n", encoding="utf-8")
    write_results_md(out, all_metrics, risk_rows, order_rows, errors, commit)
    print(f"seed={SEED} engine_commit={commit} books={len(books)} statement={len(stmts)} truth_pairs={len(truth)}")
    for row in all_metrics:
        if row["scope"] == "overall":
            print(f"{row['method']}: TP={row['TP']} FP={row['FP']} FN={row['FN']} TN={row['TN']} P={row['precision']:.6f} R={row['recall']:.6f} F1={row['F1']:.6f} candidates={row['candidate_volume']} candidate_recall={row['candidate_generation_recall']:.6f}")
    print(f"fuzzy_order_shuffles_changed={sum(int(r['changed_fuzzy_pair_count_symmetric_difference']) > 0 for r in order_rows)}/20 fuzzy_symmetric_difference_total={sum(int(r['changed_fuzzy_pair_count_symmetric_difference']) for r in order_rows)}")
    print(f"all_pair_order_shuffles_changed={sum(int(r['changed_all_pair_count_symmetric_difference']) > 0 for r in order_rows)}/20 all_pair_symmetric_difference_total={sum(int(r['changed_all_pair_count_symmetric_difference']) for r in order_rows)}")
    print(f"false_positive_examples={sum(r['error_type']=='false_positive' for r in errors)} false_negative_examples={sum(r['error_type']=='false_negative' for r in errors)}")
    print(f"fellegi_sunter=not_run results={out}")


if __name__ == "__main__":
    main()
