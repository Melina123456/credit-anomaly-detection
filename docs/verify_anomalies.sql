-- Anomaly separability check (Week 1 close-out)

-- anomalies by type: min/max/avg quantity
SELECT al.anomaly_type, MIN(ue.quantity), MAX(ue.quantity), AVG(ue.quantity)
FROM usage_event ue
JOIN anomaly_label al ON al.usage_event_id = ue.id
GROUP BY al.anomaly_type;

-- normal (non-anomaly) events for comparison
SELECT MIN(quantity), MAX(quantity), AVG(quantity)
FROM usage_event
WHERE source = 'synthetic';

-- Results (2026-08-03):
-- normal:            1 – 78,      avg 17
-- spike:            222 – 8996,   avg 2726
-- negative_balance: 3256 – 69624, avg 18872
-- replay:             1 – 58,     avg 20   (size looks normal — it's a duplicate, not a big number)
-- out_of_order:       2 – 50,     avg 15   (size looks normal — it's the timestamp that's wrong)