#!/usr/bin/env bash
# Tests whether the number of events to flag can be worked out from the score
# distribution alone, instead of being supplied.
#
# Four ways of deciding, graded against each other on every dataset:
#   gap      - cut at the largest jump between neighbouring scores
#   knee     - cut at the corner of the sorted score curve
#   fixed    - the hardcoded assume-5% currently in the code
#   oracle   - told the exact true count. Not achievable in real use; it's
#              here as the benchmark the others are trying to reach.
#
# Usage: scripts/threshold_sweep.sh [num_seeds]   (default 20)

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
OUT_CSV="scripts/threshold_sweep_results.csv"

# `run` below reuses whatever ingestion image exists, so rebuild it
# explicitly — a stale image silently ignores SEED.
docker compose build ingestion
docker compose up -d --build postgres redis ai-service

echo "waiting for ai-service..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "seed,method,flagged,picked_rate,precision,recall,f1" >"$OUT_CSV"

for seed in $(seq 1 "$N"); do
    echo "== seed $seed/$N =="

    docker compose exec -T postgres psql -U admin -d credit_anomaly -q -c "
        DELETE FROM anomaly_label;
        DELETE FROM usage_event;
        DELETE FROM credit_transaction WHERE type != 'initial_grant';
    "

    out=$(docker compose run --rm -e SEED="$seed" ingestion 2>&1)
    if ! grep -q "generator RNG seed: $seed " <<<"$out"; then
        echo "ingestion did not confirm SEED=$seed — refusing to measure an unseeded dataset" >&2
        exit 1
    fi

    docker compose exec -T ai-service python -c "
import sys
from app.db import fetch_usage_events_with_labels
from app.registry import add_all_features
from app.model import train_isolation_forest
from app.evaluate import evaluate_model
from app.threshold import largest_gap_cut, knee_cut, flags_from_cut

seed = sys.argv[1]
df = add_all_features(fetch_usage_events_with_labels())
n = len(df)

# contamination shifts every score by the same constant, so it cannot change
# which gap is largest or where the curve bends — the fixed row below is the
# only one that actually depends on this value.
scored, _ = train_isolation_forest(df.copy(), contamination=0.05)
s = scored['anomaly_score'].values

candidates = {
    'gap': largest_gap_cut(s, search_fraction=1.0),
    'knee': knee_cut(s),
    'fixed': int((scored['model_flag'] == -1).sum()),
    'oracle': int(scored['is_anomaly'].sum()),
}

for name, k in candidates.items():
    graded = scored.copy()
    graded['model_flag'] = flags_from_cut(s, k)
    r = evaluate_model(graded)
    print(f'{seed},{name},{k},{k/n:.4f},{r[\"precision\"]},{r[\"recall\"]},{r[\"f1_score\"]}')
" "$seed" >>"$OUT_CSV"
done

echo
echo "=== across $N datasets (true rate is 0.0378) ==="
python3 -c "
import csv, statistics
from collections import defaultdict

rows = list(csv.DictReader(open('$OUT_CSV')))
by_method = defaultdict(list)
for r in rows:
    by_method[r['method']].append(r)

def summarize(vals):
    return f'{statistics.mean(vals):.3f}+/-{statistics.pstdev(vals):.3f}'

for method in ('gap', 'knee', 'fixed', 'oracle'):
    g = by_method[method]
    if not g:
        continue
    print(f'{method:7s} '
          f'picked_rate={summarize([float(r[\"picked_rate\"]) for r in g])}  '
          f'P={summarize([float(r[\"precision\"]) for r in g])}  '
          f'R={summarize([float(r[\"recall\"]) for r in g])}  '
          f'F1={summarize([float(r[\"f1\"]) for r in g])}')
"
echo "raw rows: $OUT_CSV"
