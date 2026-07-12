// Package mcp implements a JSON-RPC 2.0 client for the MCP Streamable HTTP transport.
package mcp

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math/rand/v2"
	"net/http"
	"strings"
	"time"
)

const (
	defaultEndpoint  = "https://learn.microsoft.com/api/mcp"
	protocolVersion  = "2025-03-26"
	clientName       = "mslearn-cli"
	clientVersion    = "1.0.0"
	defaultTimeout   = 30 * time.Second
	terminateTimeout = 5 * time.Second
)

// RetryConfig controls retry behavior.
type RetryConfig struct {
	MaxAttempts int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
	SleepFn     func(time.Duration) // injectable for tests
}

// DefaultRetry returns the default retry configuration.
func DefaultRetry() RetryConfig {
	return RetryConfig{
		MaxAttempts: 3,
		BaseDelay:   500 * time.Millisecond,
		MaxDelay:    10 * time.Second,
		SleepFn:     time.Sleep,
	}
}

// AppError is a structured error with a code for exit code mapping.
type AppError struct {
	Code    string // E_NETWORK, E_PROTOCOL, E_VALIDATION, E_CACHE
	Message string
	Cause   error
}

func (e *AppError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.Cause)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func (e *AppError) Unwrap() error { return e.Cause }

// ContentPart is a single content element in a tool result.
type ContentPart struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

// ToolResult is the result of a tools/call invocation.
type ToolResult struct {
	Content []ContentPart
	IsError bool
}

// Client is an MCP JSON-RPC client over Streamable HTTP.
type Client struct {
	Endpoint   string
	HTTPClient *http.Client
	Trace      func(string, ...any)
	Retry      RetryConfig
	sessionID  string
	nextID     int
}

// NewClient creates a client with default settings.
func NewClient(endpoint string) *Client {
	if endpoint == "" {
		endpoint = defaultEndpoint
	}
	return &Client{
		Endpoint: endpoint,
		HTTPClient: &http.Client{
			Timeout: defaultTimeout,
		},
		Retry:  DefaultRetry(),
		nextID: 1,
	}
}

func (c *Client) trace(format string, args ...any) {
	if c.Trace != nil {
		c.Trace(format, args...)
	}
}

func (c *Client) makeID() int {
	id := c.nextID
	c.nextID++
	return id
}

// jsonrpcRequest is a JSON-RPC 2.0 request.
type jsonrpcRequest struct {
	JSONRPC string `json:"jsonrpc"`
	ID      *int   `json:"id,omitempty"` // nil omits id for notifications
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

// jsonrpcResponse is a JSON-RPC 2.0 response.
type jsonrpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      *int            `json:"id,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *jsonrpcError   `json:"error,omitempty"`
}

type jsonrpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// post sends a JSON-RPC request and returns the response.
// For notifications (id==nil), it drains the response and returns nil.
func (c *Client) post(req jsonrpcRequest, expectResponse bool) (*jsonrpcResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, &AppError{Code: "E_PROTOCOL", Message: "marshal request", Cause: err}
	}

	c.trace("POST %s method=%s", c.Endpoint, req.Method)

	httpReq, err := http.NewRequest("POST", c.Endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, &AppError{Code: "E_NETWORK", Message: "create request", Cause: err}
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "application/json, text/event-stream")
	if c.sessionID != "" {
		httpReq.Header.Set("Mcp-Session-Id", c.sessionID)
	}

	resp, err := c.doWithRetry(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	// Capture session ID
	if sid := resp.Header.Get("Mcp-Session-Id"); sid != "" {
		c.sessionID = sid
	}

	if !expectResponse {
		io.Copy(io.Discard, resp.Body) // drain
		return nil, nil
	}

	ct := resp.Header.Get("Content-Type")
	if strings.Contains(strings.ToLower(ct), "text/event-stream") {
		return c.handleSSEResponse(resp.Body, req.ID)
	}

	// Plain JSON
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, &AppError{Code: "E_NETWORK", Message: "read response", Cause: err}
	}
	var rpcResp jsonrpcResponse
	if err := json.Unmarshal(data, &rpcResp); err != nil {
		return nil, &AppError{Code: "E_PROTOCOL", Message: "decode response", Cause: err}
	}
	return &rpcResp, nil
}

func (c *Client) handleSSEResponse(body io.Reader, requestID *int) (*jsonrpcResponse, error) {
	payloads := ParseSSE(body)
	for _, raw := range payloads {
		var resp jsonrpcResponse
		if err := json.Unmarshal(raw, &resp); err != nil {
			continue
		}
		// Match response ID to request ID
		if requestID != nil && resp.ID != nil && *resp.ID == *requestID {
			return &resp, nil
		}
	}
	return nil, nil
}

func (c *Client) doWithRetry(req *http.Request) (*http.Response, error) {
	var lastErr error
	bodyBytes, _ := io.ReadAll(req.Body)

	for attempt := range c.Retry.MaxAttempts {
		req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		resp, err := c.HTTPClient.Do(req)
		if err != nil {
			lastErr = &AppError{Code: "E_NETWORK", Message: "request failed", Cause: err}
			c.retrySleep(attempt)
			continue
		}
		if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			resp.Body.Close()
			lastErr = &AppError{Code: "E_NETWORK", Message: fmt.Sprintf("HTTP %d", resp.StatusCode)}
			c.retrySleep(attempt)
			continue
		}
		if resp.StatusCode >= 400 {
			body, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			return nil, &AppError{Code: "E_PROTOCOL", Message: fmt.Sprintf("HTTP %d: %s", resp.StatusCode, string(body))}
		}
		return resp, nil
	}
	return nil, lastErr
}

func (c *Client) retrySleep(attempt int) {
	if attempt >= c.Retry.MaxAttempts-1 {
		return // don't sleep after last attempt
	}
	delay := c.Retry.BaseDelay << uint(attempt)
	if delay > c.Retry.MaxDelay {
		delay = c.Retry.MaxDelay
	}
	// Add jitter: 50-150% of delay
	jitter := time.Duration(float64(delay) * (0.5 + rand.Float64()))
	c.Retry.SleepFn(jitter)
}

// Initialize performs the MCP handshake.
func (c *Client) Initialize() error {
	id := c.makeID()
	resp, err := c.post(jsonrpcRequest{
		JSONRPC: "2.0",
		ID:      &id,
		Method:  "initialize",
		Params: map[string]any{
			"protocolVersion": protocolVersion,
			"capabilities":   map[string]any{},
			"clientInfo": map[string]string{
				"name":    clientName,
				"version": clientVersion,
			},
		},
	}, true)
	if err != nil {
		return err
	}
	if resp != nil && resp.Error != nil {
		return &AppError{Code: "E_PROTOCOL", Message: fmt.Sprintf("initialize error %d: %s", resp.Error.Code, resp.Error.Message)}
	}

	// Check protocol version
	if resp != nil && resp.Result != nil {
		var result struct {
			ProtocolVersion string `json:"protocolVersion"`
		}
		json.Unmarshal(resp.Result, &result)
		if result.ProtocolVersion != "" && result.ProtocolVersion != protocolVersion {
			c.trace("warning: server protocol %s != client %s", result.ProtocolVersion, protocolVersion)
		}
	}

	// Send initialized notification (no id)
	_, err = c.post(jsonrpcRequest{
		JSONRPC: "2.0",
		Method:  "notifications/initialized",
	}, false)
	// Accept any 2xx (200/202/204 all valid)
	return err
}

// CallTool invokes a tool and returns the result.
func (c *Client) CallTool(name string, arguments map[string]any) (*ToolResult, error) {
	id := c.makeID()
	resp, err := c.post(jsonrpcRequest{
		JSONRPC: "2.0",
		ID:      &id,
		Method:  "tools/call",
		Params: map[string]any{
			"name":      name,
			"arguments": arguments,
		},
	}, true)
	if err != nil {
		return nil, err
	}
	if resp == nil {
		return nil, &AppError{Code: "E_PROTOCOL", Message: "no response from tools/call"}
	}
	if resp.Error != nil {
		return nil, &AppError{Code: "E_PROTOCOL", Message: fmt.Sprintf("JSON-RPC error %d: %s", resp.Error.Code, resp.Error.Message)}
	}

	var result struct {
		Content []ContentPart `json:"content"`
		IsError bool          `json:"isError"`
	}
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		return nil, &AppError{Code: "E_PROTOCOL", Message: "decode tool result", Cause: err}
	}

	if result.IsError {
		var texts []string
		for _, c := range result.Content {
			texts = append(texts, c.Text)
		}
		return nil, &AppError{Code: "E_PROTOCOL", Message: fmt.Sprintf("tool error: %s", strings.Join(texts, " "))}
	}

	return &ToolResult{Content: result.Content, IsError: false}, nil
}

// Terminate sends a DELETE to end the session. Errors are swallowed.
func (c *Client) Terminate() {
	if c.sessionID == "" {
		return
	}
	req, err := http.NewRequest("DELETE", c.Endpoint, nil)
	if err != nil {
		return
	}
	req.Header.Set("Mcp-Session-Id", c.sessionID)

	client := &http.Client{Timeout: terminateTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return
	}
	resp.Body.Close()
}

// SessionID returns the current session ID, if any.
func (c *Client) SessionID() string {
	return c.sessionID
}

// SetSessionID sets the session ID (for restoring persisted sessions).
func (c *Client) SetSessionID(id string) {
	c.sessionID = id
}
