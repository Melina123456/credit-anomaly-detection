#!/usr/bin/env bash
# Measures how each detector and threshold rule copes as anomalies of one
# type bunch together. The total stays at 55 (the default dataset's count),
# so the anomaly rate is the same in every setting; only the split changes:
#
#   spikes = S, and the other 55 - S are shared evenly between replay,
#   negative_balance and out_of_order.
#
# Small S scatters the anomalies across types; large S makes one big group
# of near-identical spikes. Every (S, seed) pair is a separate dataset.
#
#   detectors: isolation_forest; lof with 10, 20 (default) and 40 neighbours;
#              glosh with min_pts chosen from the data
#   rules:     gap, polar, oracle (told the true count; benchmark only)
#
# spike_recall is the share of the planted spikes that were flagged, so a
# collapse can be traced to the spike group specifically.
#
# Usage: scripts/clump_sweep.sh [num_seeds]   (default 20)
#        SPIKES="5 20 40" scripts/clump_sweep.sh 3   (quick run)

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
SPIKES="${SPIKES:-1 5 10 15 20 25 30 40 52}"
TOTAL=55
OUT_CSV="scripts/clump_sweep_results.csv"

# `run` below reuses whatever ingestion image exists, so rebuild it
# explicitly — a stale image silently ignores SEED and ANOMALY_COUNTS.
docker compose build ingestion
docker compose up -d --build postgres redis ai-service

echo "waiting for ai-service..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "spikes,seed,detector,rule,min_pts,flagged,precision,recall,f1,spike_recall" >"$OUT_CSV"

for spikes in $SPIKES; do
    rest=$((TOTAL - spikes))
    replay=$((rest / 3 + (rest % 3 > 0 ? 1 : 0)))
    out_of_order=$((rest / 3 + (rest % 3 > 1 ? 1 : 0)))
    negative=$((rest / 3))
    counts="spike=$spikes,replay=$replay,negative_balance=$negative,out_of_order=$out_of_order"

    for seed in $(seq 1 "$N"); do
        echo "== $counts  seed $seed/$N =="

        docker compose exec -T postgres psql -U admin -d credit_anomaly -q -c "
            DELETE FROM anomaly_label;
            DELETE FROM usage_event;
            DELETE FROM credit_transaction WHERE type != 'initial_grant';
        "

        out=$(docker compose run --rm -e SEED="$seed" -e ANOMALY_COUNTS="$counts" ingestion 2>&1)
        if ! grep -q "generator RNG seed: $seed " <<<"$out"; then
            echo "ingestion did not confirm SEED=$seed — refusing to measure an unseeded dataset" >&2
            exit 1
        fi
        if ! grep -q "generator anomaly counts: $counts " <<<"$out"; then
            echo "ingestion did not confirm ANOMALY_COUNTS=$counts — refusing to measure the wrong split" >&2
            exit 1
        fi

        docker compose exec -T ai-service python -c "
import sys
import numpy as np
from app.db import fetch_usage_events_with_labels
from app.registry import add_all_features
from app.model import FEATURE_COLUMNS, train_isolation_forest, train_lof
from app.threshold import largest_gap_cut
from app.glosh import glosh_parameter_free, polar_cut

spikes, seed = sys.argv[1], sys.argv[2]
df = add_all_features(fetch_usage_events_with_labels())
X = df[FEATURE_COLUMNS].fillna(0).to_numpy(dtype=float)
y = df['is_anomaly'].to_numpy()
is_spike = (df['anomaly_type'] == 'spike').to_numpy()
n, true_k, n_spike = len(y), int(y.sum()), int(is_spike.sum())

# every detector's scores converted to one convention: higher = more anomalous
iso, _ = train_isolation_forest(df.copy())
detectors = {'isolation_forest': (-iso['anomaly_score'].to_numpy(), '')}
for k in (10, 20, 40):
    detectors[f'lof_k{k}'] = (train_lof(df.copy(), n_neighbors=k)['lof_score'].to_numpy(), '')
g = glosh_parameter_free(X)
detectors['glosh'] = (g['scores'], g['min_pts'])

for det, (s, m) in detectors.items():
    rules = {
        # largest_gap_cut reads lower = more anomalous, so it gets -s
        'gap': largest_gap_cut(-s, search_fraction=1.0),
        'polar': polar_cut(s),
        'oracle': true_k,
    }
    for rule, k in rules.items():
        flagged = np.zeros(n, bool)
        flagged[np.argsort(-s, kind='stable')[:k]] = True
        tp = int((flagged & y).sum())
        p = tp / k if k else 0.0
        rc = tp / true_k
        f = 2 * p * rc / (p + rc) if p + rc else 0.0
        sr = (flagged & is_spike).sum() / n_spike if n_spike else 0.0
        print(f'{spikes},{seed},{det},{rule},{m},{k},{p:.4f},{rc:.4f},{f:.4f},{sr:.4f}')
" "$spikes" "$seed" >>"$OUT_CSV"
    done
done

echo
echo "=== F1 (mean+/-std over $N seeds) by number of spikes, out of $TOTAL anomalies ==="
python3 -c "
import csv, statistics
from collections import defaultdict

rows = list(csv.DictReader(open('$OUT_CSV')))
g = defaultdict(list)
for r in rows:
    g[(r['detector'], r['rule'], int(r['spikes']))].append(r)
spike_counts = sorted({int(r['spikes']) for r in rows})

def ms(vals):
    return f'{statistics.mean(vals):.2f}+/-{statistics.pstdev(vals):.2f}'

for metric in ('f1', 'spike_recall'):
    print(f'--- {metric} ---')
    for rule in ('oracle', 'gap', 'polar'):
        print(rule)
        print('  ' + 'detector'.ljust(17) + ''.join(str(s).rjust(12) for s in spike_counts))
        for det in ('isolation_forest', 'lof_k10', 'lof_k20', 'lof_k40', 'glosh'):
            cells = [ms([float(r[metric]) for r in g[(det, rule, s)]]) for s in spike_counts]
            print('  ' + det.ljust(17) + ''.join(c.rjust(12) for c in cells))
"
echo "raw rows: $OUT_CSV"
