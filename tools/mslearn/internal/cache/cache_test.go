package cache

import (
	"encoding/json"
	"os"
	"testing"
	"time"
)

func TestCache_PutGet(t *testing.T) {
	dir := t.TempDir()
	c := New(dir, time.Hour)

	args := map[string]any{"query": "azure functions"}
	data := json.RawMessage(`{"result":"ok"}`)

	if got := c.Get("search", args); got != nil {
		t.Fatal("expected nil for cache miss")
	}

	if err := c.Put("search", args, data); err != nil {
		t.Fatal(err)
	}

	got := c.Get("search", args)
	if got == nil {
		t.Fatal("expected cache hit")
	}
	if string(got) != string(data) {
		t.Errorf("got %s, want %s", got, data)
	}
}

func TestCache_TTLExpiry(t *testing.T) {
	dir := t.TempDir()
	c := New(dir, time.Second)

	now := time.Now()
	c.now = func() time.Time { return now }

	args := map[string]any{"query": "test"}
	data := json.RawMessage(`{"x":1}`)
	if err := c.Put("tool", args, data); err != nil {
		t.Fatal(err)
	}

	// Advance time past TTL
	c.now = func() time.Time { return now.Add(2 * time.Second) }
	if got := c.Get("tool", args); got != nil {
		t.Fatal("expected nil for expired entry")
	}
}

func TestCache_DifferentKeys(t *testing.T) {
	dir := t.TempDir()
	c := New(dir, time.Hour)

	data1 := json.RawMessage(`"one"`)
	data2 := json.RawMessage(`"two"`)

	c.Put("tool", map[string]any{"q": "a"}, data1)
	c.Put("tool", map[string]any{"q": "b"}, data2)

	got1 := c.Get("tool", map[string]any{"q": "a"})
	got2 := c.Get("tool", map[string]any{"q": "b"})

	if string(got1) != `"one"` {
		t.Errorf("got1 = %s", got1)
	}
	if string(got2) != `"two"` {
		t.Errorf("got2 = %s", got2)
	}
}

func TestCache_Stats(t *testing.T) {
	dir := t.TempDir()
	c := New(dir, time.Hour)

	c.Put("a", map[string]any{}, json.RawMessage(`1`))
	c.Put("b", map[string]any{}, json.RawMessage(`2`))

	entries, size := c.Stats()
	if entries != 2 {
		t.Errorf("entries = %d, want 2", entries)
	}
	if size == 0 {
		t.Error("size should be > 0")
	}
}

func TestCache_Clear(t *testing.T) {
	dir := t.TempDir()
	c := New(dir, time.Hour)

	c.Put("a", map[string]any{}, json.RawMessage(`1`))
	if err := c.Clear(); err != nil {
		t.Fatal(err)
	}

	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Error("cache dir should be removed after clear")
	}
}
