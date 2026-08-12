package db

import (
	"context"
	"os"
	"path/filepath"
	"sort"

	"github.com/jackc/pgx/v5/pgxpool"
)

// RunMigrations reads all .sql files in migrationsDir, sorted by filename,
// and executes them in order. Safe to run multiple times if SQL uses
// "IF NOT EXISTS".
func RunMigrations(ctx context.Context, pool *pgxpool.Pool, migrationsDir string) error {
	entries, err := os.ReadDir(migrationsDir)
	if err != nil {
		return err
	}

	var files []string
	for _, e := range entries {
		if !e.IsDir() && filepath.Ext(e.Name()) == ".sql" {
			files = append(files, e.Name())
		}
	}
	sort.Strings(files) // 001_..., 002_... run in order

	for _, f := range files {
		content, err := os.ReadFile(filepath.Join(migrationsDir, f))
		if err != nil {
			return err
		}
		if _, err := pool.Exec(ctx, string(content)); err != nil {
			return err
		}
	}
	return nil
}
