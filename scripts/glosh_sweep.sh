#!/usr/bin/env bash
# Grades every threshold rule against every detector's scores, across N
# regenerated datasets. A rule that only works on one detector's score shape
# isn't a general answer to "how many should I flag?", so each rule is
# applied to all of them:
#
#   detectors: isolation_forest, lof, glosh (unscaled, same inputs as the
#              other two), glosh_robust (features robust-scaled first)
#   rules:     gap    - largest jump between neighbouring scores
#              polar  - knee of the sorted scores, corrected by extrapolating
#                       a line fitted to the scores before it
#              oracle - told the true anomaly count (benchmark only)
#
# For the GLOSH rows min_pts is chosen from the data too, and the min_pts
# that would have ranked best in hindsight is recorded alongside it.
#
# Usage: scripts/glosh_sweep.sh [num_seeds]   (default 20)

set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-20}"
OUT_CSV="scripts/glosh_sweep_results.csv"

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

echo "seed,detector,rule,min_pts,best_min_pts,flagged,picked_rate,precision,recall,f1" >"$OUT_CSV"

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
import numpy as np
from sklearn.preprocessing import RobustScaler
from app.db import fetch_usage_events_with_labels
from app.registry import add_all_features
from app.model import FEATURE_COLUMNS, train_isolation_forest, train_lof
from app.threshold import largest_gap_cut
from app.glosh import glosh_parameter_free, polar_cut

seed = sys.argv[1]
df = add_all_features(fetch_usage_events_with_labels())
X = df[FEATURE_COLUMNS].fillna(0).to_numpy(dtype=float)
y = df['is_anomaly'].to_numpy()
n, true_k = len(y), int(y.sum())

# every detector's scores converted to one convention: higher = more anomalous
iso, _ = train_isolation_forest(df.copy())
lof = train_lof(df.copy())
detectors = {
    'isolation_forest': (-iso['anomaly_score'].to_numpy(), '', ''),
    'lof': (lof['lof_score'].to_numpy(), '', ''),
}
for name, Xin in [('glosh', X), ('glosh_robust', RobustScaler().fit_transform(X))]:
    r = glosh_parameter_free(Xin)
    p_at = {m: y[np.argsort(-s)[:true_k]].mean() for m, s in r['profiles'].items()}
    detectors[name] = (r['scores'], r['min_pts'], max(p_at, key=p_at.get))

for det, (s, m, best_m) in detectors.items():
    rules = {
        # largest_gap_cut reads lower = more anomalous, so it gets -s
        'gap': largest_gap_cut(-s, search_fraction=1.0),
        'polar': polar_cut(s),
        'oracle': true_k,
    }
    for rule, k in rules.items():
        flagged = np.zeros(n, bool)
        flagged[np.argsort(-s)[:k]] = True
        tp = int((flagged & y).sum())
        p = tp / k if k else 0.0
        rc = tp / true_k
        f = 2 * p * rc / (p + rc) if p + rc else 0.0
        print(f'{seed},{det},{rule},{m},{best_m},{k},{k/n:.4f},{p:.4f},{rc:.4f},{f:.4f}')
" "$seed" >>"$OUT_CSV"
done

echo
echo "=== F1 by detector x rule, across $N datasets (true rate 0.0378) ==="
python3 -c "
import csv, statistics
from collections import defaultdict

rows = list(csv.DictReader(open('$OUT_CSV')))
g = defaultdict(list)
for r in rows:
    g[(r['detector'], r['rule'])].append(r)

def ms(vals):
    return f'{statistics.mean(vals):.3f}+/-{statistics.pstdev(vals):.3f}'

for det in ('isolation_forest', 'lof', 'glosh', 'glosh_robust'):
    print(det)
    for rule in ('gap', 'polar', 'oracle'):
        grp = g[(det, rule)]
        if grp:
            print(f'  {rule:6s} rate={ms([float(r[\"picked_rate\"]) for r in grp])}  '
                  f'F1={ms([float(r[\"f1\"]) for r in grp])}')
    if det.startswith('glosh'):
        grp = g[(det, 'oracle')]
        chosen = [int(r['min_pts']) for r in grp]
        best = [int(r['best_min_pts']) for r in grp]
        print(f'  min_pts chosen={ms(chosen)}  best-in-hindsight={ms(best)}')
"
echo "raw rows: $OUT_CSV"
