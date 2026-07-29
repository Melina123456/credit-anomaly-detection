package main

import (
	"context"
	"log"
	"os"

	"github.com/joho/godotenv"
	"github.com/Melina123456/credit-anomaly-detection/ingestion/internal/db"
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

	// hardcoded test insert — replace with real generator tomorrow
	var tenantID, featureID string
	err = pgPool.QueryRow(ctx, `SELECT id FROM tenant LIMIT 1`).Scan(&tenantID)
	if err != nil {
		log.Fatalf("no tenant found — insert a test tenant first: %v", err)
	}
	err = pgPool.QueryRow(ctx, `SELECT id FROM feature LIMIT 1`).Scan(&featureID)
	if err != nil {
		log.Fatalf("no feature found — insert a test feature first: %v", err)
	}

	_, err = pgPool.Exec(ctx, `
		INSERT INTO usage_event (tenant_id, feature_id, quantity, occurred_at, source)
		VALUES ($1, $2, $3, now(), 'manual-test')
	`, tenantID, featureID, 5)
	if err != nil {
		log.Fatalf("insert failed: %v", err)
	}
	log.Println("test usage_event inserted successfully")
}