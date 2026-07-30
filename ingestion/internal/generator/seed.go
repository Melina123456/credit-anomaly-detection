package generator

import (
	"context"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Tenant struct {
	ID       string
	Name     string
	PlanTier string
}

type Feature struct {
	ID  string
	Key string
}

func SeedTenantsAndFeatures(ctx context.Context, pool *pgxpool.Pool) ([]Tenant, []Feature, error) {
	tenantSpecs := []struct{ Name, Tier string }{
		{"Acme Corp", "enterprise"},
		{"Bright Labs", "pro"},
		{"Nimbus Inc", "pro"},
		{"Tiny Startup", "free"},
		{"Sunrise Tech", "free"},
	}
	featureSpecs := []string{"api_calls", "storage_gb", "compute_minutes", "export_jobs"}

	var tenants []Tenant
	for _, t := range tenantSpecs {
		var id string
		err := pool.QueryRow(ctx,
			`INSERT INTO tenant (name, plan_tier) VALUES ($1, $2) RETURNING id`,
			t.Name, t.Tier).Scan(&id)
		if err != nil {
			return nil, nil, err
		}
		tenants = append(tenants, Tenant{ID: id, Name: t.Name, PlanTier: t.Tier})
	}

	var features []Feature
	for _, key := range featureSpecs {
		var id string
		err := pool.QueryRow(ctx,
			`INSERT INTO feature (key, description) VALUES ($1, $1) RETURNING id`,
			key).Scan(&id)
		if err != nil {
			return nil, nil, err
		}
		features = append(features, Feature{ID: id, Key: key})
	}

	return tenants, features, nil
}