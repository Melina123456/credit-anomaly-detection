package main

import (
	"context"
	"log"
	"os"

	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/cache"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/db"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/generator"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/ledger"
	"github.com/joho/godotenv"
)

func main() {
	ctx := context.Background()
	_ = godotenv.Load("./.env")

	pgPool, err := db.NewPostgresPool(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatalf("postgres connection failed: %v", err)
	}
	defer pgPool.Close()
	log.Println("connected to postgres")

	rdb, err := db.NewRedisClient(ctx, os.Getenv("REDIS_ADDR"))
	if err != nil {
		log.Fatalf("redis connection failed: %v", err)
	}
	defer rdb.Close()
	log.Println("connected to redis")

	tenants, features, err := generator.GetOrSeedTenantsAndFeatures(ctx, pgPool)
	if err != nil {
		log.Fatalf("seeding failed: %v", err)
	}
	log.Printf("seeded %d tenants, %d features", len(tenants), len(features))

	var poolCount int
	pgPool.QueryRow(ctx, `SELECT COUNT(*) FROM credit_pool`).Scan(&poolCount)
	if poolCount == 0 {
		if err := generator.SeedCreditPoolsAndGrants(ctx, pgPool, tenants, features); err != nil {
			log.Fatalf("seeding pools/grants failed: %v", err)
		}
		log.Println("seeded credit pools and entitlement grants")
	} else {
		log.Println("credit pools already seeded, skipping")
	}

	events := generator.GenerateNormalEvents(tenants, features, 7, 10) // 7 days, 10 events/day/tenant/feature
	log.Printf("generated %d synthetic events", len(events))

	if err := generator.InsertEvents(ctx, pgPool, events); err != nil {
		log.Fatalf("insert failed: %v", err)
	}
	log.Println("all events inserted successfully")

	debitCount, err := ledger.WriteDebitsFromEvents(ctx, pgPool)
	if err != nil {
		log.Fatalf("ledger write failed: %v", err)
	}
	log.Printf("wrote %d debit transactions to ledger", debitCount)

	balanceCount, err := cache.UpdateCreditPoolBalances(ctx, pgPool)
	if err != nil {
		log.Fatalf("balance update failed: %v", err)
	}
	log.Printf("updated %d pool balances", balanceCount)

	usageCount, err := cache.UpdateEntitlementUsage(ctx, pgPool)
	if err != nil {
		log.Fatalf("entitlement usage update failed: %v", err)
	}
	log.Printf("updated %d entitlement usage records", usageCount)

	spikes := generator.InjectSpikes(tenants, features, 7, 5)
	for _, s := range spikes {
		log.Printf("SPIKE: tenant=%s feature=%s qty=%.2f", s.TenantID, s.FeatureID, s.Quantity)
	}

	replays := generator.InjectReplays(events, 5)
	for _, r := range replays {
		log.Printf("REPLAY: tenant=%s feature=%s qty=%.2f time=%s", r.TenantID, r.FeatureID, r.Quantity, r.OccurredAt)
	}

	negBalance, err := generator.InjectNegativeBalanceAttempts(ctx, pgPool, tenants, features, 3)
	if err != nil {
		log.Fatalf("negative balance injection failed: %v", err)
	}
	for _, n := range negBalance {
		log.Printf("NEG_BALANCE: tenant=%s feature=%s qty=%.2f", n.TenantID, n.FeatureID, n.Quantity)
	}
}
