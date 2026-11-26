#!/usr/bin/env python3
"""Create a deterministic synthetic GST invoice reconciliation benchmark."""
from __future__ import annotations

import argparse
import csv
import random
import string
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 42
SCENARIO_COUNTS = {
    "clean_match": 400,
    "case_punctuation_only": 100,
    "invoice_number_typo": 150,
    "gstin_typo": 50,
    "value_difference": 50,
    "date_shift": 50,
    "duplicate_within_file": 50,
    "missing_side": 100,
    "hard_negative": 50,
}
FIELDS = ["id", "source", "supplier_gstin", "invoice_number", "invoice_date",
          "taxable_value", "tax_amount", "link_id", "scenario", "scenario_detail",
          "true_exception"]


def gstin(rng: random.Random) -> str:
    letters = string.ascii_uppercase
    pan = "".join(rng.choice(letters) for _ in range(5))
    pan += "".join(rng.choice(string.digits) for _ in range(4)) + rng.choice(letters)
    return rng.choice([f"{n:02d}" for n in range(1, 38)]) + pan + rng.choice("123456789") + "Z" + rng.choice(string.ascii_uppercase + string.digits)


def mutate_gstin(value: str, rng: random.Random, count: int) -> str:
    chars = list(value)
    for pos in rng.sample(range(len(chars)), count):
        pool = string.ascii_uppercase + string.digits
        choices = pool.replace(chars[pos], "")
        chars[pos] = rng.choice(choices)
    return "".join(chars)


def mutate_invoice(value: str, rng: random.Random, operation: str) -> str:
    pos = rng.randrange(2, len(value) - 1)
    if operation == "substitution":
        c = rng.choice(string.ascii_uppercase + string.digits)
        while c == value[pos]:
            c = rng.choice(string.ascii_uppercase + string.digits)
        return value[:pos] + c + value[pos + 1:]
    if operation == "deletion":
        return value[:pos] + value[pos + 1:]
    if operation == "insertion":
        return value[:pos] + rng.choice(string.ascii_uppercase + string.digits) + value[pos:]
    possible = [p for p in range(2, len(value) - 1) if value[p] != value[p + 1]]
    left = rng.choice(possible)
    right = left + 1
    return value[:left] + value[right] + value[left] + value[right + 1:]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def generate(n: int = 1000, seed: int = SEED) -> tuple[list[dict], dict]:
    if n != 1000:
        raise ValueError("This protocol fixes N=1000; change the source to define another protocol.")
    rng = random.Random(seed)
    # One supplier issues ten sequentially numbered invoices. Repeated vendors
    # make near-invoice-number collisions possible in the fuzzy candidate set.
    supplier_pool = [gstin(rng) for _ in range(100)]
    scenario_plan = [name for name, count in SCENARIO_COUNTS.items() for _ in range(count)]
    rng.shuffle(scenario_plan)
    books: list[dict] = []
    statement: list[dict] = []
    book_serial = statement_serial = 0
    scenario_seen: dict[str, int] = defaultdict(int)
    typo_ops = ["substitution", "deletion", "insertion", "transposition"]
    for index, scenario in enumerate(scenario_plan, start=1):
        scenario_seen[scenario] += 1
        scenario_index = scenario_seen[scenario]
        link = f"L{index:06d}"
        supplier = supplier_pool[(index - 1) // 10]
        invoice = f"INV2026{index:06d}"
        inv_date = date(2026, 4, 1) + timedelta(days=rng.randrange(0, 25))
        taxable = rng.randrange(1000, 100000) + rng.randrange(0, 100) / 100
        tax = round(taxable * 0.18, 2)
        b = {"supplier_gstin": supplier, "invoice_number": invoice,
             "invoice_date": inv_date.isoformat(), "taxable_value": f"{taxable:.2f}",
             "tax_amount": f"{tax:.2f}"}
        s = dict(b)
        detail = scenario
        missing = None
        if scenario == "case_punctuation_only":
            s["supplier_gstin"] = supplier.lower()
            s["invoice_number"] = invoice.lower()[:6] + "/-" + invoice[6:]
        elif scenario == "invoice_number_typo":
            detail = "invoice_" + typo_ops[(scenario_index - 1) % len(typo_ops)]
            s["invoice_number"] = mutate_invoice(invoice, rng, detail.removeprefix("invoice_"))
        elif scenario == "gstin_typo":
            edits = 1 + ((scenario_index - 1) % 2)
            detail = f"gstin_{edits}_character_edits"
            s["supplier_gstin"] = mutate_gstin(supplier, rng, edits)
        elif scenario == "value_difference":
            # Half are within the engine's $1.00 combined-value tolerance; half exceed it.
            within = (scenario_index % 2 == 0)
            delta = 0.50 if within else 2.00
            detail = "within_tolerance_0.50" if within else "above_tolerance_2.00"
            s["taxable_value"] = f"{taxable + delta:.2f}"
            s["tax_amount"] = f"{tax:.2f}"
        elif scenario == "date_shift":
            shifted = inv_date + timedelta(days=1 if inv_date.day < 28 else -1)
            s["invoice_date"] = shifted.isoformat()
            detail = "date_shift_1_day"
        elif scenario == "duplicate_within_file":
            detail = "duplicate_in_books"
        elif scenario == "missing_side":
            missing = "books" if scenario_index % 2 == 0 else "statement"
            detail = "missing_from_" + missing
        elif scenario == "hard_negative":
            # Two nonmatching underlying invoices intentionally share an invoice number.
            if scenario_index % 2 == 0:
                s["supplier_gstin"] = supplier_pool[((index - 1) // 10 + 1) % len(supplier_pool)]
                detail = "same_invoice_different_supplier"
            else:
                s["taxable_value"] = f"{taxable + 250.00:.2f}"
                detail = "same_invoice_same_supplier_different_amount"
        b_id = ""
        s_id = ""
        if scenario == "hard_negative":
            book_serial += 1
            statement_serial += 1
            b_id, s_id = f"B{book_serial:06d}", f"S{statement_serial:06d}"
            books.append({**b, "id": b_id, "source": "books", "link_id": f"{link}-B",
                          "scenario": scenario, "scenario_detail": detail, "true_exception": "1"})
            statement.append({**s, "id": s_id, "source": "2a", "link_id": f"{link}-S",
                              "scenario": scenario, "scenario_detail": detail, "true_exception": "1"})
            continue
        if missing != "books":
            book_serial += 1
            b_id = f"B{book_serial:06d}"
            books.append({**b, "id": b_id, "source": "books", "link_id": link,
                          "scenario": scenario, "scenario_detail": detail,
                          "true_exception": "0" if scenario in {"clean_match", "case_punctuation_only"} else "1"})
        if missing != "statement":
            statement_serial += 1
            s_id = f"S{statement_serial:06d}"
            statement.append({**s, "id": s_id, "source": "2a", "link_id": link,
                              "scenario": scenario, "scenario_detail": detail,
                              "true_exception": "0" if scenario in {"clean_match", "case_punctuation_only"} else "1"})
        if scenario == "duplicate_within_file":
            book_serial += 1
            books.append({**b, "id": f"B{book_serial:06d}", "source": "books", "link_id": link,
                          "scenario": scenario, "scenario_detail": detail, "true_exception": "1"})
    return books + statement, {"books": books, "statement": statement}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("experiments/results"))
    args = parser.parse_args()
    rows, split = generate(args.n, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "synthetic_dataset.csv", rows)
    write_csv(args.output / "books.csv", split["books"])
    write_csv(args.output / "statement.csv", split["statement"])
    message = f"seed={args.seed} base_invoices={args.n} books_rows={len(split['books'])} statement_rows={len(split['statement'])} combined_rows={len(rows)}\n"
    message += "base_case_counts=" + ",".join(f"{name}:{count}" for name, count in SCENARIO_COUNTS.items()) + "\n"
    print(message, end="")


if __name__ == "__main__":
    main()
