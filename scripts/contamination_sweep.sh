#!/usr/bin/env bash
# For each of N regenerated datasets, fits Isolation Forest and LOF once per
# contamination value in the grid and records precision/recall/F1 — so the
# reported curves are a mean +/- std across seeds, not one dataset's shape.
#
# Contamination doesn't require regenerating data, only refitting, so the
# grid runs in a single Python process per seed rather than one docker run
# per (seed, contamination) pair.
#
# Usage: scripts/contamination_sweep.sh [num_seeds]   (default 20)

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
GRID="0.01 0.02 0.03 0.0378 0.05 0.07 0.10 0.15"
OUT_CSV="scripts/contamination_sweep_results.csv"

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

echo "seed,contamination,model,precision,recall,f1" >"$OUT_CSV"

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
from app.features import add_zscore_features, add_duplicate_features, add_lag_feature
from app.model import train_isolation_forest, train_lof
from app.evaluate import evaluate_model

seed = sys.argv[1]
grid = [float(x) for x in sys.argv[2:]]

df = fetch_usage_events_with_labels()
df = add_zscore_features(df)
df = add_duplicate_features(df)
df = add_lag_feature(df)

def row(model_name, r):
    return f'{seed},{c},{model_name},{r[\"precision\"]},{r[\"recall\"]},{r[\"f1_score\"]}'

for c in grid:
    iso, _ = train_isolation_forest(df.copy(), contamination=c)
    print(row('isolation_forest', evaluate_model(iso)))

    # pyod labels anomalies 1 and normals 0, the opposite of sklearn's -1/1
    lof = train_lof(df.copy(), contamination=c)
    print(row('lof', evaluate_model(lof, pred_col='lof_flag', anomaly_value=1)))
" "$seed" $GRID >>"$OUT_CSV"
done

echo
echo "=== summary: mean +/- std per contamination level, across $N seeds ==="
python3 -c "
import csv, statistics
from collections import defaultdict

rows = list(csv.DictReader(open('$OUT_CSV')))
grouped = defaultdict(list)
for r in rows:
    grouped[(r['model'], float(r['contamination']))].append(r)

for model in sorted({m for m, _ in grouped}):
    print()
    print(model)
    for (m, c) in sorted(k for k in grouped if k[0] == model):
        group = grouped[(m, c)]
        line = f'  {c:.4f}'
        for metric in ('precision', 'recall', 'f1'):
            vals = [float(r[metric]) for r in group]
            line += f'  {metric}={statistics.mean(vals):.3f}+/-{statistics.pstdev(vals):.3f}'
        print(line)
"
echo "raw per-seed-per-contamination results: $OUT_CSV"
