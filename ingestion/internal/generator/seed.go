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

func GetOrSeedTenantsAndFeatures(ctx context.Context, pool *pgxpool.Pool) ([]Tenant, []Feature, error) {
	var count int
	pool.QueryRow(ctx, `SELECT COUNT(*) FROM tenant`).Scan(&count)

	if count > 0 {
		return fetchExistingTenantsAndFeatures(ctx, pool)
	}
	return SeedTenantsAndFeatures(ctx, pool)
}

func fetchExistingTenantsAndFeatures(ctx context.Context, pool *pgxpool.Pool) ([]Tenant, []Feature, error) {
	var tenants []Tenant
	rows, err := pool.Query(ctx, `SELECT id, name, plan_tier FROM tenant`)
	if err != nil {
		return nil, nil, err
	}
	for rows.Next() {
		var t Tenant
		rows.Scan(&t.ID, &t.Name, &t.PlanTier)
		tenants = append(tenants, t)
	}
	rows.Close()

	var features []Feature
	rows, err = pool.Query(ctx, `SELECT id, key FROM feature`)
	if err != nil {
		return nil, nil, err
	}
	for rows.Next() {
		var f Feature
		rows.Scan(&f.ID, &f.Key)
		features = append(features, f)
	}
	rows.Close()

	return tenants, features, nil
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

func SeedCreditPoolsAndGrants(ctx context.Context, pool *pgxpool.Pool, tenants []Tenant, features []Feature) error {
	const startingBalance = 1000.0

	for _, t := range tenants {
		// create wallet
		var poolID string
		err := pool.QueryRow(ctx,
			`INSERT INTO credit_pool (tenant_id, currency) VALUES ($1, 'credits') RETURNING id`,
			t.ID).Scan(&poolID)
		if err != nil {
			return err
		}

		// fund it — this IS the starting balance, recorded as a ledger entry
		_, err = pool.Exec(ctx, `
			INSERT INTO credit_transaction (pool_id, amount, type)
			VALUES ($1, $2, 'initial_grant')
		`, poolID, startingBalance)
		if err != nil {
			return err
		}

		// set daily limits per feature, a bit above normal usage
		limit := tierBaseline[t.PlanTier] * 1.2
		for _, f := range features {
			_, err = pool.Exec(ctx, `
				INSERT INTO entitlement_grant (tenant_id, feature_id, usage_limit, period)
				VALUES ($1, $2, $3, 'daily')
			`, t.ID, f.ID, limit)
			if err != nil {
				return err
			}
		}
	}
	return nil
}
