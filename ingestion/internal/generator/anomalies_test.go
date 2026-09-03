package generator

import (
	"testing"
	"time"
)

func TestInjectSpikes_QuantityIsWithinDocumentedMultiplier(t *testing.T) {
	tenants := testTenants()
	features := testFeatures()

	anomalies := InjectSpikes(tenants, features, 7, 20)

	if len(anomalies) != 20 {
		t.Fatalf("got %d spikes, want 20", len(anomalies))
	}

	for _, a := range anomalies {
		if a.AnomalyType != "spike" {
			t.Fatalf("unexpected anomaly type %q", a.AnomalyType)
		}
		baseline := tierBaseline[tenantTierByID(tenants, a.TenantID)]
		low, high := 10*baseline, 20*baseline
		if a.Quantity < low || a.Quantity > high {
			t.Fatalf("spike quantity %.2f outside documented 10x-20x range [%.2f, %.2f]", a.Quantity, low, high)
		}
	}
}

func TestInjectSpikes_ZeroCountProducesNoAnomalies(t *testing.T) {
	anomalies := InjectSpikes(testTenants(), testFeatures(), 7, 0)
	if len(anomalies) != 0 {
		t.Fatalf("expected 0 anomalies, got %d", len(anomalies))
	}
}

func TestInjectReplays_DuplicatesAnExistingEventExactly(t *testing.T) {
	existing := []EventSpec{
		{TenantID: "t1", FeatureID: "f1", Quantity: 42.5, OccurredAt: time.Now().UTC()},
		{TenantID: "t2", FeatureID: "f2", Quantity: 7, OccurredAt: time.Now().UTC().AddDate(0, 0, -1)},
	}

	anomalies := InjectReplays(existing, 5)

	if len(anomalies) != 5 {
		t.Fatalf("got %d replays, want 5", len(anomalies))
	}

	for _, a := range anomalies {
		if a.AnomalyType != "replay" {
			t.Fatalf("unexpected anomaly type %q", a.AnomalyType)
		}
		matched := false
		for _, e := range existing {
			if a.TenantID == e.TenantID && a.FeatureID == e.FeatureID &&
				a.Quantity == e.Quantity && a.OccurredAt.Equal(e.OccurredAt) {
				matched = true
				break
			}
		}
		if !matched {
			t.Fatalf("replay %+v does not exactly match any existing event", a)
		}
	}
}

func TestInjectReplays_EmptyExistingProducesNoAnomalies(t *testing.T) {
	// this is the important edge case: if InjectReplays ever loses this
	// guard, rand.Intn(0) panics instead of returning an empty slice.
	anomalies := InjectReplays(nil, 5)
	if len(anomalies) != 0 {
		t.Fatalf("expected 0 anomalies for empty existing events, got %d", len(anomalies))
	}
}

func TestInjectOutOfOrderEvents_BackdatedWithinDocumentedRange(t *testing.T) {
	tenants := testTenants()
	features := testFeatures()
	now := time.Now().UTC()

	anomalies := InjectOutOfOrderEvents(tenants, features, 15)

	if len(anomalies) != 15 {
		t.Fatalf("got %d out-of-order anomalies, want 15", len(anomalies))
	}

	for _, a := range anomalies {
		if a.AnomalyType != "out_of_order" {
			t.Fatalf("unexpected anomaly type %q", a.AnomalyType)
		}
		daysBack := now.Sub(a.OccurredAt).Hours() / 24
		// documented range is 20-40 days back; allow a small tolerance for
		// the seconds that elapse between "now" here and inside the function.
		if daysBack < 19.9 || daysBack > 40.1 {
			t.Fatalf("out-of-order event backdated %.2f days, expected 20-40", daysBack)
		}

		baseline := tierBaseline[tenantTierByID(tenants, a.TenantID)]
		wantQty := baseline / 10
		if a.Quantity != wantQty {
			t.Fatalf("out-of-order quantity %.2f, want baseline/10 = %.2f", a.Quantity, wantQty)
		}
	}
}

// tenantTierByID is a small test helper to recover which plan tier a
// generated anomaly's TenantID belongs to, so tests can re-derive the
// expected baseline the same way the production code does.
func tenantTierByID(tenants []Tenant, id string) string {
	for _, t := range tenants {
		if t.ID == id {
			return t.PlanTier
		}
	}
	return ""
}
