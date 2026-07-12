// Package cache provides a disk-based cache with SHA256 keys and TTL expiry.
package cache

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// entry is the on-disk cache format.
type entry struct {
	Data      json.RawMessage `json:"data"`
	Timestamp time.Time       `json:"timestamp"`
}

// Cache is a disk-based cache using SHA256(key) filenames with TTL expiry.
// Directory layout uses git object store convention: {key[:2]}/{key}.json
type Cache struct {
	dir string
	ttl time.Duration
	now func() time.Time // injectable for tests
}

// New creates a cache in dir with the given TTL.
func New(dir string, ttl time.Duration) *Cache {
	return &Cache{dir: dir, ttl: ttl, now: time.Now}
}

func (c *Cache) key(tool string, args map[string]any) string {
	h := sha256.New()
	h.Write([]byte(tool))
	h.Write([]byte{0})
	// Deterministic JSON encoding of args
	b, _ := json.Marshal(args)
	h.Write(b)
	return fmt.Sprintf("%x", h.Sum(nil))
}

func (c *Cache) path(k string) string {
	return filepath.Join(c.dir, k[:2], k+".json")
}

// Get retrieves a cached value. Returns nil if not found or expired.
func (c *Cache) Get(tool string, args map[string]any) json.RawMessage {
	k := c.key(tool, args)
	data, err := os.ReadFile(c.path(k))
	if err != nil {
		return nil
	}
	var e entry
	if err := json.Unmarshal(data, &e); err != nil {
		return nil
	}
	if c.now().Sub(e.Timestamp) > c.ttl {
		return nil
	}
	return e.Data
}

// Put stores a value in the cache.
func (c *Cache) Put(tool string, args map[string]any, data json.RawMessage) error {
	k := c.key(tool, args)
	p := c.path(k)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	e := entry{Data: data, Timestamp: c.now()}
	b, err := json.Marshal(e)
	if err != nil {
		return err
	}
	return os.WriteFile(p, b, 0o644)
}

// Stats returns cache statistics: total entries and total size in bytes.
func (c *Cache) Stats() (entries int, sizeBytes int64) {
	filepath.Walk(c.dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if !info.IsDir() {
			entries++
			sizeBytes += info.Size()
		}
		return nil
	})
	return
}

// Clear removes all cached entries.
func (c *Cache) Clear() error {
	return os.RemoveAll(c.dir)
}
