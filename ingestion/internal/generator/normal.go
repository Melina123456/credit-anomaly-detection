package generator

import (
	"math/rand"
	"time"
)

type EventSpec struct {
	TenantID   string
	FeatureID  string
	Quantity   float64
	OccurredAt time.Time
}

// baseline usage per plan tier per feature — rough daily volume
var tierBaseline = map[string]float64{
	"enterprise": 500,
	"pro":        150,
	"free":       20,
}

// GenerateNormalEvents produces `eventsPerTenantPerDay` events per tenant
// per feature per day, over `days` days ending today, with gaussian noise
// around each tenant's baseline.
func GenerateNormalEvents(tenants []Tenant, features []Feature, days int, eventsPerDay int) []EventSpec {
	var events []EventSpec
	now := time.Now().UTC()

	for _, t := range tenants {
		baseline := tierBaseline[t.PlanTier]
		for _, f := range features {
			for d := 0; d < days; d++ {
				dayStart := now.AddDate(0, 0, -d)
				for i := 0; i < eventsPerDay; i++ {
					// spread events randomly through the day
					offset := time.Duration(rand.Intn(24*60)) * time.Minute
					occurredAt := time.Date(dayStart.Year(), dayStart.Month(), dayStart.Day(), 0, 0, 0, 0, time.UTC).Add(offset)

					// gaussian noise around baseline/eventsPerDay, floor at 1
					mean := baseline / float64(eventsPerDay)
					qty := mean + rand.NormFloat64()*(mean*0.2)
					if qty < 1 {
						qty = 1
					}

					events = append(events, EventSpec{
						TenantID:   t.ID,
						FeatureID:  f.ID,
						Quantity:   qty,
						OccurredAt: occurredAt,
					})
				}
			}
		}
	}
	return events
}