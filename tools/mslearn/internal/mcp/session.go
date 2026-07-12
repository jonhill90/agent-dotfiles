package mcp

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// sessionData is the on-disk session persistence format.
type sessionData struct {
	SessionID string `json:"session_id"`
	Endpoint  string `json:"endpoint"`
	StartedAt string `json:"started_at"`
}

// SessionFile returns the default session file path.
func SessionFile() (string, error) {
	dir, err := os.UserCacheDir()
	if err != nil {
		return "", &AppError{Code: "E_CACHE", Message: "get cache dir", Cause: err}
	}
	return filepath.Join(dir, "mslearn", "session.json"), nil
}

// SaveSession persists the current session to disk.
func SaveSession(sessionID, endpoint string) error {
	path, err := SessionFile()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return &AppError{Code: "E_CACHE", Message: "create session dir", Cause: err}
	}
	data := sessionData{
		SessionID: sessionID,
		Endpoint:  endpoint,
		StartedAt: time.Now().UTC().Format(time.RFC3339),
	}
	b, _ := json.MarshalIndent(data, "", "  ")
	return os.WriteFile(path, b, 0o644)
}

// LoadSession loads a persisted session. Returns empty strings if none found.
func LoadSession() (sessionID, endpoint string, err error) {
	path, err := SessionFile()
	if err != nil {
		return "", "", err
	}
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return "", "", nil
		}
		return "", "", &AppError{Code: "E_CACHE", Message: "read session", Cause: err}
	}
	var data sessionData
	if err := json.Unmarshal(b, &data); err != nil {
		return "", "", &AppError{Code: "E_CACHE", Message: "decode session", Cause: err}
	}
	return data.SessionID, data.Endpoint, nil
}

// ClearSession removes the persisted session file.
func ClearSession() error {
	path, err := SessionFile()
	if err != nil {
		return err
	}
	err = os.Remove(path)
	if err != nil && !os.IsNotExist(err) {
		return &AppError{Code: "E_CACHE", Message: "remove session", Cause: err}
	}
	return nil
}

// SessionStatus returns a human-readable session status.
func SessionStatus() (string, error) {
	path, err := SessionFile()
	if err != nil {
		return "", err
	}
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return "no active session", nil
		}
		return "", &AppError{Code: "E_CACHE", Message: "read session", Cause: err}
	}
	var data sessionData
	if err := json.Unmarshal(b, &data); err != nil {
		return "corrupt session file", nil
	}
	return "active: session_id=" + data.SessionID + " endpoint=" + data.Endpoint + " started=" + data.StartedAt, nil
}
