package generator

import "testing"

func TestParseAnomalyCounts_EmptyGivesTheDefaultSplit(t *testing.T) {
	got, err := ParseAnomalyCounts("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != DefaultAnomalyCounts {
		t.Fatalf("got %v, want default %v", got, DefaultAnomalyCounts)
	}
	if got.Total() != 55 {
		t.Fatalf("default total is %d, want 55 — earlier results all assume 55", got.Total())
	}
}

func TestParseAnomalyCounts_FullSpec(t *testing.T) {
	got, err := ParseAnomalyCounts("spike=40, replay=5,negative_balance=5,out_of_order=5")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := AnomalyCounts{Spike: 40, Replay: 5, NegativeBalance: 5, OutOfOrder: 5}
	if got != want {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestParseAnomalyCounts_OmittedTypesKeepTheirDefault(t *testing.T) {
	got, err := ParseAnomalyCounts("spike=2")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := DefaultAnomalyCounts
	want.Spike = 2
	if got != want {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestParseAnomalyCounts_StringRoundTrips(t *testing.T) {
	want := AnomalyCounts{Spike: 1, Replay: 2, NegativeBalance: 0, OutOfOrder: 52}
	got, err := ParseAnomalyCounts(want.String())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != want {
		t.Fatalf("got %v, want %v", got, want)
	}
}

func TestParseAnomalyCounts_RejectsBadInput(t *testing.T) {
	for _, raw := range []string{
		"spikes=10",       // typo must not silently fall back to the default
		"spike=-1",        // negative
		"spike=ten",       // not a number
		"spike",           // no count
		"spike=1,spike=2", // ambiguous
		"spike=1.5",       // not whole
	} {
		if _, err := ParseAnomalyCounts(raw); err == nil {
			t.Errorf("ParseAnomalyCounts(%q) accepted bad input", raw)
		}
	}
}
