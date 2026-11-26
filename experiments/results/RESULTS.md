# GSTFlow Synthetic Reconciliation Evaluation

## Setup

- Generator and evaluation seed: `42`; the seed is recorded in the raw generator output, command log, and `run_metadata.json`.
- Base invoices: 1,000. Scenario counts: clean 400; case/punctuation 100; invoice-number typo 150; GSTIN typo 50; value differences 50 (25 within/25 above tolerance); date shift 50; duplicate 50; missing side 100 (50 each direction); hard negatives 50.
- Synthetic suppliers are reused in groups of ten sequential invoice numbers to create repeated-supplier candidate ambiguity; 100 distinct format-valid-looking (checksum not independently verified) GSTIN strings are generated from seed 42.
- Base scenario proportions are respectively 40%, 10%, 15%, 5%, 5%, 5%, 5%, 10%, and 5%; duplicate cases add one extra books row and hard-negative cases have unrelated book/statement link IDs.
- Engine source commit: `17b53f231f038b8e626fad76f01a0a4902f16371`. Tolerance: `1.00`. Python and matplotlib versions are recorded in `run_metadata.json`.
- Dataset files are `synthetic_dataset.csv`, `books.csv`, and `statement.csv`. Ground-truth link IDs and scenario labels are removed by an explicit field whitelist before each call to the engine.
- Pair truth is the one-to-one first row per ground-truth link ID on each side; extra within-file duplicate rows retain the link ID for provenance but are not a second gold counterpart. All possible cross-file row pairs form the confusion-matrix universe; this makes TN large and FPR small, so interpret both with precision/recall.
- Scenario strata assign cross-scenario row pairs to `cross_scenario`; macro averages include scenarios with at least one ground-truth positive pair.
- Candidate-generation recall is the share of true row pairs admitted by exact-key or fuzzy eligibility gates before confidence cutoff. Candidate volume is the number of eligible pair candidates, not CPU operations.
- `Exact-only` uses upper/trimmed GSTIN plus normalized invoice number and pairs the first occurrence per key; the engine subsequently applies value/date discrepancy rules to exact keys.
- Threshold and ablation variants use an evaluation adapter that mirrors the engine; canonical threshold 80 is validated against the unmodified production function. Ablations renormalize the remaining weights to 100.
- Order test compares fuzzy pair memberships (GSTIN typo and fuzzy suggestions) separately from all paired outcomes across 20 deterministic shuffle seeds (books 1001–1020; statement seeds 11001–11020). Risk ranking uses the repository's `score_discrepancy` and 100 random permutations from seed 42.

## Overall methods

| method | TP | FP | FN | TN | precision | recall | F1 | false_positive_rate | candidate_volume | candidate_generation_recall |
|---|---|---|---|---|---|---|---|---|---|---|
| Exact-only | 650 | 25 | 200 | 949125 | 0.962963 | 0.764706 | 0.852459 | 0.000026 | 675 | 0.764706 |
| Hybrid engine (threshold 80) | 841 | 56 | 9 | 949094 | 0.937570 | 0.989412 | 0.962793 | 0.000059 | 1591 | 1.000000 |
| Hybrid sweep threshold=70 | 828 | 82 | 22 | 949068 | 0.909890 | 0.974118 | 0.940909 | 0.000086 | 1591 | 1.000000 |
| Hybrid sweep threshold=75 | 833 | 73 | 17 | 949077 | 0.919426 | 0.980000 | 0.948747 | 0.000077 | 1591 | 1.000000 |
| Hybrid sweep threshold=80 | 841 | 56 | 9 | 949094 | 0.937570 | 0.989412 | 0.962793 | 0.000059 | 1591 | 1.000000 |
| Hybrid sweep threshold=85 | 847 | 39 | 3 | 949111 | 0.955982 | 0.996471 | 0.975806 | 0.000041 | 1591 | 1.000000 |
| Hybrid sweep threshold=90 | 850 | 28 | 0 | 949122 | 0.968109 | 1.000000 | 0.983796 | 0.000030 | 1591 | 1.000000 |
| Hybrid sweep threshold=95 | 813 | 25 | 37 | 949125 | 0.970167 | 0.956471 | 0.963270 | 0.000026 | 1591 | 1.000000 |
| Ablation remove invoice (renormalized) | 840 | 43 | 10 | 949107 | 0.951302 | 0.988235 | 0.969417 | 0.000045 | 1591 | 1.000000 |
| Ablation remove gstin (renormalized) | 845 | 44 | 5 | 949106 | 0.950506 | 0.994118 | 0.971823 | 0.000046 | 1591 | 1.000000 |
| Ablation remove value (renormalized) | 828 | 79 | 22 | 949071 | 0.912900 | 0.974118 | 0.942516 | 0.000083 | 1591 | 1.000000 |
| Ablation remove date (renormalized) | 828 | 75 | 22 | 949075 | 0.916944 | 0.974118 | 0.944666 | 0.000079 | 1591 | 1.000000 |

### Plain-language interpretation

Exact-only: TP=650, FP=25, FN=200, TN=949125, precision=0.9630, recall=0.7647, F1=0.8525, candidate volume=675.
Hybrid engine (threshold 80): TP=841, FP=56, FN=9, TN=949094, precision=0.9376, recall=0.9894, F1=0.9628, candidate volume=1591.
Exact-only has 25 false positives and hybrid threshold 80 has 56; therefore the hybrid is worse on false-positive count in this synthetic benchmark. Their false-positive rates are 0.000026 and 0.000059, respectively.
The hybrid gains 191 true pairs and reduces false negatives by 191 versus exact-only, while adding 31 false-positive pairs. Its F1 is +0.110334 higher; precision changes by -0.025393.
The confusion counts and candidate volume are in `metrics.csv`; pair-level predictions include engine results with two IDs (matched or discrepancy/fuzzy pairs). Duplicate flags without a paired counterpart are not positive predictions.

## Threshold sweep and ablations

| method | TP | FP | FN | TN | precision | recall | F1 | false_positive_rate | candidate_volume | candidate_generation_recall |
|---|---|---|---|---|---|---|---|---|---|---|
| Hybrid sweep threshold=70 | 828 | 82 | 22 | 949068 | 0.909890 | 0.974118 | 0.940909 | 0.000086 | 1591 | 1.000000 |
| Hybrid sweep threshold=75 | 833 | 73 | 17 | 949077 | 0.919426 | 0.980000 | 0.948747 | 0.000077 | 1591 | 1.000000 |
| Hybrid sweep threshold=80 | 841 | 56 | 9 | 949094 | 0.937570 | 0.989412 | 0.962793 | 0.000059 | 1591 | 1.000000 |
| Hybrid sweep threshold=85 | 847 | 39 | 3 | 949111 | 0.955982 | 0.996471 | 0.975806 | 0.000041 | 1591 | 1.000000 |
| Hybrid sweep threshold=90 | 850 | 28 | 0 | 949122 | 0.968109 | 1.000000 | 0.983796 | 0.000030 | 1591 | 1.000000 |
| Hybrid sweep threshold=95 | 813 | 25 | 37 | 949125 | 0.970167 | 0.956471 | 0.963270 | 0.000026 | 1591 | 1.000000 |
| Ablation remove invoice (renormalized) | 840 | 43 | 10 | 949107 | 0.951302 | 0.988235 | 0.969417 | 0.000045 | 1591 | 1.000000 |
| Ablation remove gstin (renormalized) | 845 | 44 | 5 | 949106 | 0.950506 | 0.994118 | 0.971823 | 0.000046 | 1591 | 1.000000 |
| Ablation remove value (renormalized) | 828 | 79 | 22 | 949071 | 0.912900 | 0.974118 | 0.942516 | 0.000083 | 1591 | 1.000000 |
| Ablation remove date (renormalized) | 828 | 75 | 22 | 949075 | 0.916944 | 0.974118 | 0.944666 | 0.000079 | 1591 | 1.000000 |

The plot `precision_recall.png` uses the executed threshold-sweep rows. The best observed sweep F1 is 0.983796 at Hybrid sweep threshold=90, with 28 FP and 0 FN. Threshold 90 has full observed recall on this synthetic gold, with 28 false positives; threshold 95 lowers recall, so a higher cutoff is not always better. Candidate generation is unchanged by confidence threshold. Ablation scores redistribute remaining component weights proportionally before applying threshold 80.
Ablations versus canonical threshold-80 F1: remove invoice gives F1 0.969417 (+0.006624); remove gstin gives F1 0.971823 (+0.009030); remove value gives F1 0.942516 (-0.020278); remove date gives F1 0.944666 (-0.018127).

## Per-scenario results

| method | scope | TP | FP | FN | TN | precision | recall | F1 | false_positive_rate | candidate_volume | candidate_generation_recall |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Exact-only | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Exact-only | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Exact-only | invoice_number_typo | 0 | 0 | 150 | 22350 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0.000000 |
| Exact-only | gstin_typo | 0 | 0 | 50 | 2450 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0.000000 |
| Exact-only | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Exact-only | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Exact-only | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Exact-only | missing_side | 0 | 0 | 0 | 2500 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0.000000 |
| Exact-only | hard_negative | 0 | 25 | 0 | 2475 | 0.000000 | 0.000000 | 0.000000 | 0.010000 | 25 | 0.000000 |
| Hybrid engine (threshold 80) | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid engine (threshold 80) | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid engine (threshold 80) | invoice_number_typo | 141 | 0 | 9 | 22350 | 1.000000 | 0.940000 | 0.969072 | 0.000000 | 364 | 1.000000 |
| Hybrid engine (threshold 80) | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid engine (threshold 80) | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid engine (threshold 80) | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid engine (threshold 80) | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid engine (threshold 80) | missing_side | 0 | 15 | 0 | 2485 | 0.000000 | 0.000000 | 0.000000 | 0.006000 | 32 | 0.000000 |
| Hybrid engine (threshold 80) | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Hybrid sweep threshold=70 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=70 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=70 | invoice_number_typo | 128 | 1 | 22 | 22349 | 0.992248 | 0.853333 | 0.917563 | 0.000045 | 364 | 1.000000 |
| Hybrid sweep threshold=70 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=70 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=70 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=70 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=70 | missing_side | 0 | 19 | 0 | 2481 | 0.000000 | 0.000000 | 0.000000 | 0.007600 | 32 | 0.000000 |
| Hybrid sweep threshold=70 | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Hybrid sweep threshold=75 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=75 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=75 | invoice_number_typo | 133 | 1 | 17 | 22349 | 0.992537 | 0.886667 | 0.936620 | 0.000045 | 364 | 1.000000 |
| Hybrid sweep threshold=75 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=75 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=75 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=75 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=75 | missing_side | 0 | 17 | 0 | 2483 | 0.000000 | 0.000000 | 0.000000 | 0.006800 | 32 | 0.000000 |
| Hybrid sweep threshold=75 | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Hybrid sweep threshold=80 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=80 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=80 | invoice_number_typo | 141 | 0 | 9 | 22350 | 1.000000 | 0.940000 | 0.969072 | 0.000000 | 364 | 1.000000 |
| Hybrid sweep threshold=80 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=80 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=80 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=80 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=80 | missing_side | 0 | 15 | 0 | 2485 | 0.000000 | 0.000000 | 0.000000 | 0.006000 | 32 | 0.000000 |
| Hybrid sweep threshold=80 | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Hybrid sweep threshold=85 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=85 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=85 | invoice_number_typo | 147 | 0 | 3 | 22350 | 1.000000 | 0.980000 | 0.989899 | 0.000000 | 364 | 1.000000 |
| Hybrid sweep threshold=85 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=85 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=85 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=85 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=85 | missing_side | 0 | 7 | 0 | 2493 | 0.000000 | 0.000000 | 0.000000 | 0.002800 | 32 | 0.000000 |
| Hybrid sweep threshold=85 | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Hybrid sweep threshold=90 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=90 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=90 | invoice_number_typo | 150 | 0 | 0 | 22350 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 364 | 1.000000 |
| Hybrid sweep threshold=90 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=90 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=90 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=90 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=90 | missing_side | 0 | 3 | 0 | 2497 | 0.000000 | 0.000000 | 0.000000 | 0.001200 | 32 | 0.000000 |
| Hybrid sweep threshold=90 | hard_negative | 0 | 25 | 0 | 2475 | 0.000000 | 0.000000 | 0.000000 | 0.010000 | 26 | 0.000000 |
| Hybrid sweep threshold=95 | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Hybrid sweep threshold=95 | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Hybrid sweep threshold=95 | invoice_number_typo | 113 | 0 | 37 | 22350 | 1.000000 | 0.753333 | 0.859316 | 0.000000 | 364 | 1.000000 |
| Hybrid sweep threshold=95 | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Hybrid sweep threshold=95 | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=95 | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=95 | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Hybrid sweep threshold=95 | missing_side | 0 | 0 | 0 | 2500 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 32 | 0.000000 |
| Hybrid sweep threshold=95 | hard_negative | 0 | 25 | 0 | 2475 | 0.000000 | 0.000000 | 0.000000 | 0.010000 | 26 | 0.000000 |
| Ablation remove invoice (renormalized) | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Ablation remove invoice (renormalized) | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Ablation remove invoice (renormalized) | invoice_number_typo | 140 | 0 | 10 | 22350 | 1.000000 | 0.933333 | 0.965517 | 0.000000 | 364 | 1.000000 |
| Ablation remove invoice (renormalized) | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Ablation remove invoice (renormalized) | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove invoice (renormalized) | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove invoice (renormalized) | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove invoice (renormalized) | missing_side | 0 | 5 | 0 | 2495 | 0.000000 | 0.000000 | 0.000000 | 0.002000 | 32 | 0.000000 |
| Ablation remove invoice (renormalized) | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Ablation remove gstin (renormalized) | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Ablation remove gstin (renormalized) | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Ablation remove gstin (renormalized) | invoice_number_typo | 145 | 0 | 5 | 22350 | 1.000000 | 0.966667 | 0.983051 | 0.000000 | 364 | 1.000000 |
| Ablation remove gstin (renormalized) | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Ablation remove gstin (renormalized) | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove gstin (renormalized) | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove gstin (renormalized) | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove gstin (renormalized) | missing_side | 0 | 10 | 0 | 2490 | 0.000000 | 0.000000 | 0.000000 | 0.004000 | 32 | 0.000000 |
| Ablation remove gstin (renormalized) | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Ablation remove value (renormalized) | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Ablation remove value (renormalized) | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Ablation remove value (renormalized) | invoice_number_typo | 128 | 3 | 22 | 22347 | 0.977099 | 0.853333 | 0.911032 | 0.000134 | 364 | 1.000000 |
| Ablation remove value (renormalized) | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Ablation remove value (renormalized) | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove value (renormalized) | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove value (renormalized) | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove value (renormalized) | missing_side | 0 | 21 | 0 | 2479 | 0.000000 | 0.000000 | 0.000000 | 0.008400 | 32 | 0.000000 |
| Ablation remove value (renormalized) | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |
| Ablation remove date (renormalized) | clean_match | 400 | 0 | 0 | 159600 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 400 | 1.000000 |
| Ablation remove date (renormalized) | case_punctuation_only | 100 | 0 | 0 | 9900 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 100 | 1.000000 |
| Ablation remove date (renormalized) | invoice_number_typo | 128 | 1 | 22 | 22349 | 0.992248 | 0.853333 | 0.917563 | 0.000045 | 364 | 1.000000 |
| Ablation remove date (renormalized) | gstin_typo | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 66 | 1.000000 |
| Ablation remove date (renormalized) | value_difference | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove date (renormalized) | date_shift | 50 | 0 | 0 | 2450 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove date (renormalized) | duplicate_within_file | 50 | 0 | 0 | 4950 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 50 | 1.000000 |
| Ablation remove date (renormalized) | missing_side | 0 | 15 | 0 | 2485 | 0.000000 | 0.000000 | 0.000000 | 0.006000 | 32 | 0.000000 |
| Ablation remove date (renormalized) | hard_negative | 0 | 26 | 0 | 2474 | 0.000000 | 0.000000 | 0.000000 | 0.010400 | 26 | 0.000000 |

Scenario metrics are one-vs-rest over row pairs whose two rows share the named scenario; unmatched scenario combinations are separately labeled `cross_scenario` in the CSV. `macro_supported_scenarios` averages per-scenario metrics only where at least one positive ground-truth pair exists. Missing-side and hard-negative cases have no positive cross-file gold pair by construction, so they are represented in overall and per-scenario FP/TN counts but are not included in supported-scenario macro recall/F1.
At threshold 80, invoice-number typo pairs have TP=141, FP=0, FN=9 (recall 0.9400); missing-side cases produce 15 false pairings, and hard negatives produce 26. Clean, case/punctuation, GSTIN typo, value, date, and duplicate scenarios have full pair recall in this generated set; see their rows for precision and counts.

## Candidate generation

Candidate-generation recall and candidate volume are included in every row of `metrics.csv`; overall method rows are reproduced here.

| method | candidate_volume | candidate_generation_recall | TP | FN | recall |
|---|---|---|---|---|---|
| Exact-only | 675 | 0.764706 | 650 | 200 | 0.764706 |
| Hybrid engine (threshold 80) | 1591 | 1.000000 | 841 | 9 | 0.989412 |
| Hybrid sweep threshold=70 | 1591 | 1.000000 | 828 | 22 | 0.974118 |
| Hybrid sweep threshold=75 | 1591 | 1.000000 | 833 | 17 | 0.980000 |
| Hybrid sweep threshold=80 | 1591 | 1.000000 | 841 | 9 | 0.989412 |
| Hybrid sweep threshold=85 | 1591 | 1.000000 | 847 | 3 | 0.996471 |
| Hybrid sweep threshold=90 | 1591 | 1.000000 | 850 | 0 | 1.000000 |
| Hybrid sweep threshold=95 | 1591 | 1.000000 | 813 | 37 | 0.956471 |
| Ablation remove invoice (renormalized) | 1591 | 1.000000 | 840 | 10 | 0.988235 |
| Ablation remove gstin (renormalized) | 1591 | 1.000000 | 845 | 5 | 0.994118 |
| Ablation remove value (renormalized) | 1591 | 1.000000 | 828 | 22 | 0.974118 |
| Ablation remove date (renormalized) | 1591 | 1.000000 | 828 | 22 | 0.974118 |

## Risk ranking

| k_requested | k_evaluated | true_exception_entities | total_tax_exposure | risk_top_k_exposure_share | random_100_shuffle_mean_share | random_100_shuffle_min_share | random_100_shuffle_max_share |
|---|---|---|---|---|---|---|---|
| 10 | 10 | 550 | 5135360.020000 | 0.020927 | 0.018531 | 0.011322 | 0.026981 |
| 50 | 50 | 550 | 5135360.020000 | 0.111076 | 0.091299 | 0.071881 | 0.104890 |
| 100 | 100 | 550 | 5135360.020000 | 0.200869 | 0.182185 | 0.161532 | 0.202557 |

The ranking universe is unique ground-truth exception link IDs (hard negatives are separate entities); exposure is each entity's maximum source tax amount, avoiding duplicate inflation. Risk score per entity is the maximum repository risk score attached to its rows by the canonical engine output. Random shares are the arithmetic mean/range over 100 deterministic shuffles.
At k=10, risk ranking covered 2.09% of exception tax exposure; random-order mean was 1.85% (observed range 1.13%–2.70%).
At k=50, risk ranking covered 11.11% of exception tax exposure; random-order mean was 9.13% (observed range 7.19%–10.49%).
At k=100, risk ranking covered 20.09% of exception tax exposure; random-order mean was 18.22% (observed range 16.15%–20.26%).

## Order sensitivity

Across 20 deterministic row-order shuffles, fuzzy pair membership changed in 0 trials; the sum of symmetric-difference fuzzy pair counts is 0. For all paired outcomes (including exact and duplicate-row identity), changes occurred in 20 trials with total symmetric difference 1018. The example CSV includes changed pair IDs and source scenario details; these are duplicate representative changes when the fuzzy-only count is zero.

## Hybrid threshold-80 error analysis

The canonical output has 56 false-positive pairs and 9 false-negative pairs. The examples CSV lists 30 FP and 9 FN examples, capped at 30 per type; 26 FP and 0 FN examples are omitted by the cap. `error_cause_counts_hybrid80.csv` gives cause counts over all errors; `cause_group` uses generator scenario details.

## Threats to validity

This is a synthetic benchmark generated by the same project author, not a sample of real GST filings. Its noise model is hand-designed: controlled character edits, fixed date shifts, fixed value deltas, selected missingness, duplicates, and deliberately constructed hard negatives. Real exports may have different error frequencies, correlated errors, GSTIN validity behavior, tax rounding, invoice formats, and missingness mechanisms.
The engine's matching weights and thresholds are hand-tuned and not calibrated on an independent labeled dataset. The generator gives a known oracle but cannot establish field performance. Pair-level row combinations create a large TN universe; accuracy and FPR alone would be misleading. Candidate generation is instrumented by an evaluation mirror for fuzzy eligibility, so its definition follows the observed source logic and should be checked if engine code changes.
The engine iterates sets and greedily consumes fuzzy matches. Pair-order results are measured only for this generated input and this Python/hash-seed environment. The 20-shuffle check cannot establish stability over all inputs or runtimes.

## Not tested

Fellegi–Sunter was not run. This draft evaluation does not use real or de-identified GST data, human adjudication, cross-period generalization, calibrated confidence probabilities, production throughput/memory measurements, concurrent requests, or a statistically sampled confidence interval. Threshold/ablation adapter parity is checked at the canonical configuration; alternative policies are experimental wrappers, not production engine behavior.

## Conclusion

On this seeded synthetic benchmark, the unmodified hybrid engine at threshold 80 achieves precision 0.937570, recall 0.989412, and F1 0.962793; exact-only achieves precision 0.962963, recall 0.764706, and F1 0.852459. The hybrid retrieves more true pairs but is worse on false-positive count (56 versus 25); constructed hard negatives and cross-record fuzzy conflicts contribute to those errors. Threshold 90 is the best observed sweep setting by F1, but it is a development-set result, not a validated production setting.
Fuzzy pair membership did not change in the 20 shuffles, so these runs do not demonstrate fuzzy greedy-order instability. All paired outputs did change because duplicate resolution retains the first exact-key row; those changes must not be characterized as fuzzy matching changes. Risk ranking exceeded the random mean for each tested k but did not exceed every random shuffle at every k. The experiment supports follow-up evaluation on governed, labeled real data; it does not establish real-world accuracy or tax outcomes.

## Raw artifacts and exact commands

Exact commands are saved in `raw/commands.txt`; captured stdout/stderr and runtime metadata are saved under `raw/`. Machine-readable metrics, errors, risks, and order tests are in the adjacent CSV files.
