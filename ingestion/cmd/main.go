package main

import (
	"context"
	"log"
	"math/rand"
	"os"
	"strconv"
	"time"

	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/cache"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/db"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/generator"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/ledger"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
)

// newRNG builds the single *rand.Rand threaded through every generator call.
// SEED makes a run reproducible; without it, results still work but can't be
// replayed, so the resolved seed is always logged.
func newRNG() *rand.Rand {
	seed := time.Now().UnixNano()
	if raw := os.Getenv("SEED"); raw != "" {
		parsed, err := strconv.ParseInt(raw, 10, 64)
		if err != nil {
			log.Fatalf("invalid SEED %q: %v", raw, err)
		}
		seed = parsed
	}
	log.Printf("generator RNG seed: %d (set SEED=%d to reproduce this run)", seed, seed)
	return rand.New(rand.NewSource(seed))
}

func main() {
	ctx := context.Background()
	_ = godotenv.Load("./.env")

	pgPool, err := db.NewPostgresPool(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatalf("postgres connection failed: %v", err)
	}
	defer pgPool.Close()
	log.Println("connected to postgres")

	if err := db.RunMigrations(ctx, pgPool, "migrations"); err != nil {
		log.Fatalf("migrations failed: %v", err)
	}
	log.Println("migrations applied")

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

	// Seeding is one-shot: this service runs on every `docker-compose up`, and
	// without this guard each start appended another full batch of events and
	// anomalies to the same volume. That silently grew the dataset and shifted
	// every measured metric, so no result in the README was reproducible.
	var eventCount int
	if err := pgPool.QueryRow(ctx, `SELECT COUNT(*) FROM usage_event`).Scan(&eventCount); err != nil {
		log.Fatalf("usage event count failed: %v", err)
	}
	if eventCount > 0 {
		log.Printf("usage events already seeded (%d rows), skipping generation", eventCount)
		return
	}

	rng := newRNG()

	events := generator.GenerateNormalEvents(rng, tenants, features, 7, 10) // 7 days, 10 events/day/tenant/feature
	log.Printf("generated %d synthetic events", len(events))

	if err := generator.InsertEvents(ctx, pgPool, events); err != nil {
		log.Fatalf("insert failed: %v", err)
	}
	log.Println("all events inserted successfully")

	// Must run before anomalies are injected: InjectNegativeBalanceAttempts
	// reads credit_pool_balance to pick a quantity that exceeds what the
	// tenant actually has left.
	if err := reconcileLedgerAndCaches(ctx, pgPool); err != nil {
		log.Fatalf("ledger/cache reconciliation failed: %v", err)
	}

	var allAnomalies []generator.AnomalyEvent
	allAnomalies = append(allAnomalies, generator.InjectSpikes(rng, tenants, features, 7, 15)...)
	allAnomalies = append(allAnomalies, generator.InjectReplays(rng, events, 15)...)

	negBalance, err := generator.InjectNegativeBalanceAttempts(ctx, pgPool, rng, tenants, features, 10)
	if err != nil {
		log.Fatalf("negative balance injection failed: %v", err)
	}
	allAnomalies = append(allAnomalies, negBalance...)
	allAnomalies = append(allAnomalies, generator.InjectOutOfOrderEvents(rng, tenants, features, 15)...)

	anomalyCount, err := generator.InsertAnomalies(ctx, pgPool, allAnomalies)
	if err != nil {
		log.Fatalf("anomaly insertion failed: %v", err)
	}
	log.Printf("inserted and labeled %d anomalies", anomalyCount)

	// Anomaly rows are usage events too, so they need debits and cache entries
	// of their own — otherwise a single seeding run leaves them unledgered.
	if err := reconcileLedgerAndCaches(ctx, pgPool); err != nil {
		log.Fatalf("ledger/cache reconciliation failed: %v", err)
	}
}

// reconcileLedgerAndCaches writes a debit for every usage event that doesn't
// have one yet, then rebuilds the read caches from the ledger. Safe to call
// repeatedly — WriteDebitsFromEvents skips events already in the ledger.
func reconcileLedgerAndCaches(ctx context.Context, pgPool *pgxpool.Pool) error {
	debitCount, err := ledger.WriteDebitsFromEvents(ctx, pgPool)
	if err != nil {
		return err
	}
	log.Printf("wrote %d debit transactions to ledger", debitCount)

	balanceCount, err := cache.UpdateCreditPoolBalances(ctx, pgPool)
	if err != nil {
		return err
	}
	log.Printf("updated %d pool balances", balanceCount)

	usageCount, err := cache.UpdateEntitlementUsage(ctx, pgPool)
	if err != nil {
		return err
	}
	log.Printf("updated %d entitlement usage records", usageCount)

	return nil
}
