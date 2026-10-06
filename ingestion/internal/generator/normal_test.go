package generator

import (
	"math/rand"
	"testing"
	"time"
)

func testRNG() *rand.Rand {
	return rand.New(rand.NewSource(1))
}

var testRef = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

func testTenants() []Tenant {
	return []Tenant{
		{ID: "t1", Name: "Acme", PlanTier: "enterprise"},
		{ID: "t2", Name: "Tiny", PlanTier: "free"},
	}
}

func testFeatures() []Feature {
	return []Feature{
		{ID: "f1", Key: "api_calls"},
		{ID: "f2", Key: "storage_gb"},
	}
}

func TestGenerateNormalEvents_Count(t *testing.T) {
	tenants := testTenants()
	features := testFeatures()
	days := 3
	eventsPerDay := 4

	events := GenerateNormalEvents(testRNG(), testRef, tenants, features, days, eventsPerDay)

	want := len(tenants) * len(features) * days * eventsPerDay
	if len(events) != want {
		t.Fatalf("got %d events, want %d", len(events), want)
	}
}

func TestGenerateNormalEvents_QuantityNeverBelowFloor(t *testing.T) {
	// gaussian noise around a small "free" tier baseline can dip below zero;
	// the function is supposed to floor it at 1. Run a large batch since a
	// single call might not hit the tail of the distribution.
	tenants := []Tenant{{ID: "t1", Name: "Tiny", PlanTier: "free"}}
	features := testFeatures()

	events := GenerateNormalEvents(testRNG(), testRef, tenants, features, 30, 50)

	for _, e := range events {
		if e.Quantity < 1 {
			t.Fatalf("event quantity %.4f is below the documented floor of 1", e.Quantity)
		}
	}
}

func TestGenerateNormalEvents_UnknownPlanTierYieldsZeroBaseline(t *testing.T) {
	// tierBaseline is a plain map lookup with no fallback — an unrecognized
	// plan tier silently resolves to a zero baseline (Go's zero value for
	// float64) rather than an error. This test pins that behavior down so a
	// future change to tierBaseline can't silently break it without a test
	// failing.
	tenants := []Tenant{{ID: "t1", Name: "Mystery", PlanTier: "unobtainium"}}
	features := testFeatures()

	events := GenerateNormalEvents(testRNG(), testRef, tenants, features, 1, 5)

	for _, e := range events {
		if e.Quantity != 1 {
			t.Fatalf("expected zero-baseline events to floor at 1, got %.4f", e.Quantity)
		}
	}
}

func TestGenerateNormalEvents_EmptyInputsProduceNoEvents(t *testing.T) {
	if events := GenerateNormalEvents(testRNG(), testRef, nil, testFeatures(), 3, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for nil tenants, got %d", len(events))
	}
	if events := GenerateNormalEvents(testRNG(), testRef, testTenants(), nil, 3, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for nil features, got %d", len(events))
	}
	if events := GenerateNormalEvents(testRNG(), testRef, testTenants(), testFeatures(), 0, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for 0 days, got %d", len(events))
	}
}

func TestGenerateNormalEvents_OccurredAtWithinWindow(t *testing.T) {
	tenants := testTenants()
	features := testFeatures()
	days := 5

	// every event must fall strictly before ref — an event dated after its
	// own ingestion time would get a negative ingestion lag
	lowerBound := testRef.AddDate(0, 0, -days)

	events := GenerateNormalEvents(testRNG(), testRef, tenants, features, days, 3)

	for _, e := range events {
		if !e.OccurredAt.Before(testRef) {
			t.Fatalf("event at %v is not before the reference time %v", e.OccurredAt, testRef)
		}
		if e.OccurredAt.Before(lowerBound) {
			t.Fatalf("event occurred before the allowed window: %v (lower bound %v)", e.OccurredAt, lowerBound)
		}
	}
}

func TestGenerateNormalEvents_SameSeedAndRefGiveIdenticalEvents(t *testing.T) {
	// the reproducibility guarantee: nothing read from the wall clock
	a := GenerateNormalEvents(testRNG(), testRef, testTenants(), testFeatures(), 7, 10)
	b := GenerateNormalEvents(testRNG(), testRef, testTenants(), testFeatures(), 7, 10)

	if len(a) != len(b) {
		t.Fatalf("lengths differ: %d vs %d", len(a), len(b))
	}
	for i := range a {
		if a[i] != b[i] {
			t.Fatalf("event %d differs between identical runs: %+v vs %+v", i, a[i], b[i])
		}
	}
}
