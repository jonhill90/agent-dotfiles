package mcp

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

// mockMCPServer creates a test server that simulates the MCP protocol.
func mockMCPServer(t *testing.T) *httptest.Server {
	t.Helper()
	var initialized atomic.Bool

	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.Method != "POST" {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		body, _ := io.ReadAll(r.Body)
		var req jsonrpcRequest
		json.Unmarshal(body, &req)

		w.Header().Set("Mcp-Session-Id", "test-session-123")

		switch req.Method {
		case "initialize":
			initialized.Store(true)
			resp := jsonrpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Result:  json.RawMessage(fmt.Sprintf(`{"protocolVersion":"%s","capabilities":{},"serverInfo":{"name":"test","version":"1.0"}}`, protocolVersion)),
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)

		case "notifications/initialized":
			w.WriteHeader(http.StatusAccepted)

		case "tools/call":
			if !initialized.Load() {
				http.Error(w, "not initialized", http.StatusBadRequest)
				return
			}
			resp := jsonrpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Result:  json.RawMessage(`{"content":[{"type":"text","text":"Azure Functions is a serverless compute service."}],"isError":false}`),
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)

		default:
			http.Error(w, "unknown method", http.StatusBadRequest)
		}
	}))
}

// mockSSEServer returns a server that responds with SSE for tools/call.
func mockSSEServer(t *testing.T) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		body, _ := io.ReadAll(r.Body)
		var req jsonrpcRequest
		json.Unmarshal(body, &req)

		w.Header().Set("Mcp-Session-Id", "sse-session")

		switch req.Method {
		case "initialize":
			w.Header().Set("Content-Type", "application/json")
			resp := jsonrpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Result:  json.RawMessage(fmt.Sprintf(`{"protocolVersion":"%s"}`, protocolVersion)),
			}
			json.NewEncoder(w).Encode(resp)

		case "notifications/initialized":
			w.WriteHeader(http.StatusAccepted)

		case "tools/call":
			w.Header().Set("Content-Type", "text/event-stream")
			id := 0
			if req.ID != nil {
				id = *req.ID
			}
			fmt.Fprintf(w, ": keepalive\n")
			fmt.Fprintf(w, "data: {\"jsonrpc\":\"2.0\",\"id\":%d,\"result\":{\"content\":[{\"type\":\"text\",\"text\":\"SSE result\"}],\"isError\":false}}\n\n", id)
		}
	}))
}

func TestClient_InitializeAndCallTool(t *testing.T) {
	srv := mockMCPServer(t)
	defer srv.Close()

	c := NewClient(srv.URL)
	if err := c.Initialize(); err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if c.SessionID() != "test-session-123" {
		t.Errorf("session ID = %q, want %q", c.SessionID(), "test-session-123")
	}

	result, err := c.CallTool("microsoft_docs_search", map[string]any{"query": "Azure Functions"})
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}
	if len(result.Content) != 1 {
		t.Fatalf("content length = %d, want 1", len(result.Content))
	}
	if result.Content[0].Text != "Azure Functions is a serverless compute service." {
		t.Errorf("text = %q", result.Content[0].Text)
	}

	c.Terminate() // should not error
}

func TestClient_SSEResponse(t *testing.T) {
	srv := mockSSEServer(t)
	defer srv.Close()

	c := NewClient(srv.URL)
	if err := c.Initialize(); err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	result, err := c.CallTool("microsoft_docs_search", map[string]any{"query": "test"})
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}
	if len(result.Content) != 1 || result.Content[0].Text != "SSE result" {
		t.Errorf("unexpected result: %+v", result)
	}
}

func TestClient_RetryOn5xx(t *testing.T) {
	attempts := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		// Third attempt succeeds
		body, _ := io.ReadAll(r.Body)
		var req jsonrpcRequest
		json.Unmarshal(body, &req)
		w.Header().Set("Content-Type", "application/json")
		resp := jsonrpcResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result:  json.RawMessage(fmt.Sprintf(`{"protocolVersion":"%s"}`, protocolVersion)),
		}
		json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	c := NewClient(srv.URL)
	c.Retry.SleepFn = func(d time.Duration) {} // no-op for tests

	id := c.makeID()
	_, err := c.post(jsonrpcRequest{JSONRPC: "2.0", ID: &id, Method: "initialize"}, true)
	if err != nil {
		t.Fatalf("expected success after retries, got: %v", err)
	}
	if attempts != 3 {
		t.Errorf("attempts = %d, want 3", attempts)
	}
}

func TestClient_4xxNoRetry(t *testing.T) {
	attempts := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		http.Error(w, "bad request", http.StatusBadRequest)
	}))
	defer srv.Close()

	c := NewClient(srv.URL)
	c.Retry.SleepFn = func(d time.Duration) {}

	id := c.makeID()
	_, err := c.post(jsonrpcRequest{JSONRPC: "2.0", ID: &id, Method: "test"}, true)
	if err == nil {
		t.Fatal("expected error for 4xx")
	}
	if attempts != 1 {
		t.Errorf("attempts = %d, want 1 (no retry on 4xx)", attempts)
	}
	appErr, ok := err.(*AppError)
	if !ok {
		t.Fatalf("expected *AppError, got %T", err)
	}
	if appErr.Code != "E_PROTOCOL" {
		t.Errorf("code = %q, want E_PROTOCOL", appErr.Code)
	}
}

func TestClient_ToolError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "DELETE" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		body, _ := io.ReadAll(r.Body)
		var req jsonrpcRequest
		json.Unmarshal(body, &req)

		w.Header().Set("Mcp-Session-Id", "err-session")
		w.Header().Set("Content-Type", "application/json")

		switch req.Method {
		case "initialize":
			json.NewEncoder(w).Encode(jsonrpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Result:  json.RawMessage(fmt.Sprintf(`{"protocolVersion":"%s"}`, protocolVersion)),
			})
		case "notifications/initialized":
			w.WriteHeader(http.StatusAccepted)
		case "tools/call":
			json.NewEncoder(w).Encode(jsonrpcResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Result:  json.RawMessage(`{"content":[{"type":"text","text":"something went wrong"}],"isError":true}`),
			})
		}
	}))
	defer srv.Close()

	c := NewClient(srv.URL)
	c.Initialize()

	_, err := c.CallTool("bad_tool", nil)
	if err == nil {
		t.Fatal("expected error for isError=true")
	}
	appErr, ok := err.(*AppError)
	if !ok {
		t.Fatalf("expected *AppError, got %T", err)
	}
	if appErr.Code != "E_PROTOCOL" {
		t.Errorf("code = %q", appErr.Code)
	}
}

func TestClient_JSONRPCError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req jsonrpcRequest
		json.Unmarshal(body, &req)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(jsonrpcResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   &jsonrpcError{Code: -32600, Message: "invalid request"},
		})
	}))
	defer srv.Close()

	c := NewClient(srv.URL)
	err := c.Initialize()
	if err == nil {
		t.Fatal("expected error for JSON-RPC error response")
	}
}

func TestClient_Trace(t *testing.T) {
	srv := mockMCPServer(t)
	defer srv.Close()

	var traces []string
	c := NewClient(srv.URL)
	c.Trace = func(format string, args ...any) {
		traces = append(traces, fmt.Sprintf(format, args...))
	}

	c.Initialize()
	if len(traces) == 0 {
		t.Error("expected trace output")
	}
}
