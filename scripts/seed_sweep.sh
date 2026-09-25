#!/usr/bin/env bash
# Evaluates precision/recall/F1 across N different random datasets instead of
# just one, so the reported numbers are a mean +/- std rather than a single
# draw. Requires the ingestion service to accept a SEED env var.
#
# For each seed: wipe the generated events/anomalies/debits (tenants,
# features and credit pools are fixed lists and are left alone), regenerate
# with that seed, and hit /debug/evaluate, which fits a fresh throwaway
# IsolationForest from whatever is in the DB right now.
#
# Usage: scripts/seed_sweep.sh [num_seeds]   (default 20)

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
API_KEY="local-dev-only-key" # matches docker-compose.yml's ADMIN_API_KEY
BASE_URL="http://localhost:8000"
OUT_CSV="scripts/seed_sweep_results.csv"

docker compose up -d --build postgres redis ai-service

echo "waiting for ai-service..."
for i in $(seq 1 30); do
    if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "seed,precision,recall,f1" >"$OUT_CSV"

for seed in $(seq 1 "$N"); do
    echo "== seed $seed/$N =="

    docker compose exec -T postgres psql -U admin -d credit_anomaly -q -c "
        DELETE FROM anomaly_label;
        DELETE FROM usage_event;
        DELETE FROM credit_transaction WHERE type != 'initial_grant';
    "

    docker compose run --rm -e SEED="$seed" ingestion

    curl -sf -H "X-API-Key: $API_KEY" "$BASE_URL/debug/evaluate" | python3 -c "
import json, sys
r = json.load(sys.stdin)['aggregate']
print(f\"{sys.argv[1]},{r['precision']},{r['recall']},{r['f1_score']}\")
" "$seed" >>"$OUT_CSV"
done

echo
echo "=== summary across $N seeds ==="
python3 -c "
import csv, statistics
rows = list(csv.DictReader(open('$OUT_CSV')))
for metric in ('precision', 'recall', 'f1'):
    vals = [float(r[metric]) for r in rows]
    print(f'{metric}: mean={statistics.mean(vals):.3f} std={statistics.pstdev(vals):.3f}')
"
echo "raw per-seed results: $OUT_CSV"
