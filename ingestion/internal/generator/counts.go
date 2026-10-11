package generator

import (
	"fmt"
	"strconv"
	"strings"
)

// AnomalyCounts is how many anomalies of each type get planted. Changing the
// split while keeping the total fixed controls how strongly same-type
// anomalies clump together, without also changing the overall anomaly rate.
type AnomalyCounts struct {
	Spike           int
	Replay          int
	NegativeBalance int
	OutOfOrder      int
}

// DefaultAnomalyCounts is the split every earlier result was measured on.
var DefaultAnomalyCounts = AnomalyCounts{Spike: 15, Replay: 15, NegativeBalance: 10, OutOfOrder: 15}

func (c AnomalyCounts) Total() int {
	return c.Spike + c.Replay + c.NegativeBalance + c.OutOfOrder
}

func (c AnomalyCounts) String() string {
	return fmt.Sprintf("spike=%d,replay=%d,negative_balance=%d,out_of_order=%d",
		c.Spike, c.Replay, c.NegativeBalance, c.OutOfOrder)
}

// ParseAnomalyCounts reads "spike=15,replay=15,negative_balance=10,out_of_order=15".
// Types left out keep their default, so "spike=40" changes only spikes. Unknown
// names and negative counts are errors rather than being ignored: a typo that
// silently fell back to the default would measure the wrong dataset.
func ParseAnomalyCounts(raw string) (AnomalyCounts, error) {
	counts := DefaultAnomalyCounts
	if strings.TrimSpace(raw) == "" {
		return counts, nil
	}

	fields := map[string]*int{
		"spike":            &counts.Spike,
		"replay":           &counts.Replay,
		"negative_balance": &counts.NegativeBalance,
		"out_of_order":     &counts.OutOfOrder,
	}
	seen := map[string]bool{}

	for _, part := range strings.Split(raw, ",") {
		name, value, ok := strings.Cut(strings.TrimSpace(part), "=")
		if !ok {
			return AnomalyCounts{}, fmt.Errorf("%q: want name=count", part)
		}
		name = strings.TrimSpace(name)
		target, known := fields[name]
		if !known {
			return AnomalyCounts{}, fmt.Errorf("unknown anomaly type %q (want spike, replay, negative_balance or out_of_order)", name)
		}
		if seen[name] {
			return AnomalyCounts{}, fmt.Errorf("anomaly type %q given twice", name)
		}
		seen[name] = true

		n, err := strconv.Atoi(strings.TrimSpace(value))
		if err != nil {
			return AnomalyCounts{}, fmt.Errorf("%s: %q is not a whole number", name, value)
		}
		if n < 0 {
			return AnomalyCounts{}, fmt.Errorf("%s: count %d is negative", name, n)
		}
		*target = n
	}
	return counts, nil
}
