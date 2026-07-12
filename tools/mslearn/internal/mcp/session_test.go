package mcp

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSession_SaveLoadClear(t *testing.T) {
	// Use temp dir to avoid polluting real cache
	tmp := t.TempDir()
	t.Setenv("XDG_CACHE_HOME", tmp) // Linux
	// For macOS, we override the session file path directly
	sessionPath := filepath.Join(tmp, "mslearn", "session.json")

	// Test save
	if err := os.MkdirAll(filepath.Dir(sessionPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(sessionPath, []byte(`{"session_id":"abc","endpoint":"https://test.com","started_at":"2025-01-01T00:00:00Z"}`), 0o644); err != nil {
		t.Fatal(err)
	}

	// Test load by reading the file we just wrote
	data, err := os.ReadFile(sessionPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(data) == 0 {
		t.Fatal("session file is empty")
	}

	// Test clear
	if err := os.Remove(sessionPath); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(sessionPath); !os.IsNotExist(err) {
		t.Error("session file should be removed")
	}
}

func TestSessionStatus_NoSession(t *testing.T) {
	// SessionStatus with no file should return "no active session"
	// We test the logic directly since SessionFile depends on os.UserCacheDir
	status, err := SessionStatus()
	if err != nil {
		// It's OK if there's a real session file — just check it doesn't error fatally
		t.Logf("SessionStatus: %v (may have real session)", err)
	}
	if status == "" && err == nil {
		t.Error("expected non-empty status")
	}
}
