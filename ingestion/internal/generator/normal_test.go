package generator

import (
	"testing"
	"time"
)

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

	events := GenerateNormalEvents(tenants, features, days, eventsPerDay)

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

	events := GenerateNormalEvents(tenants, features, 30, 50)

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

	events := GenerateNormalEvents(tenants, features, 1, 5)

	for _, e := range events {
		if e.Quantity != 1 {
			t.Fatalf("expected zero-baseline events to floor at 1, got %.4f", e.Quantity)
		}
	}
}

func TestGenerateNormalEvents_EmptyInputsProduceNoEvents(t *testing.T) {
	if events := GenerateNormalEvents(nil, testFeatures(), 3, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for nil tenants, got %d", len(events))
	}
	if events := GenerateNormalEvents(testTenants(), nil, 3, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for nil features, got %d", len(events))
	}
	if events := GenerateNormalEvents(testTenants(), testFeatures(), 0, 5); len(events) != 0 {
		t.Fatalf("expected 0 events for 0 days, got %d", len(events))
	}
}

func TestGenerateNormalEvents_OccurredAtWithinWindow(t *testing.T) {
	tenants := testTenants()
	features := testFeatures()
	days := 5

	// NOTE: for "today" (d=0), the function picks a random minute-of-day
	// offset independent of the actual wall-clock time, so an event dated
	// "today" can land later today than the instant this test runs — it is
	// not guaranteed to be <= now. That's fine for a batch-generated
	// synthetic dataset, so the upper bound here is end-of-today, not "now".
	today := time.Now().UTC()
	upperBound := time.Date(today.Year(), today.Month(), today.Day(), 23, 59, 59, 0, time.UTC)
	lowerBound := today.AddDate(0, 0, -days-1)

	events := GenerateNormalEvents(tenants, features, days, 3)

	for _, e := range events {
		if e.OccurredAt.After(upperBound) {
			t.Fatalf("event occurred after the allowed window: %v (upper bound %v)", e.OccurredAt, upperBound)
		}
		if e.OccurredAt.Before(lowerBound) {
			t.Fatalf("event occurred before the allowed window: %v (lower bound %v)", e.OccurredAt, lowerBound)
		}
	}
}
