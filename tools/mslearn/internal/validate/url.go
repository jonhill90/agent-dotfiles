// Package validate provides SSRF-safe URL validation for Microsoft Learn URLs.
package validate

import (
	"fmt"
	"net/url"
	"strconv"
	"strings"
)

// isPrivateHost reports whether host is a private, loopback, or link-local address.
func isPrivateHost(host string) bool {
	switch host {
	case "localhost", "127.0.0.1", "0.0.0.0", "::1":
		return true
	}
	for _, prefix := range []string{"10.", "127.", "192.168.", "169.254."} {
		if strings.HasPrefix(host, prefix) {
			return true
		}
	}
	// 172.16.0.0/12 = 172.16.* through 172.31.*
	if strings.HasPrefix(host, "172.") {
		parts := strings.SplitN(host, ".", 3)
		if len(parts) >= 2 {
			if n, err := strconv.Atoi(parts[1]); err == nil && n >= 16 && n <= 31 {
				return true
			}
		}
	}
	return false
}

// URL validates a URL for microsoft_docs_fetch. Returns an error message or empty string.
func URL(raw string) string {
	parsed, err := url.Parse(raw)
	if err != nil {
		return "invalid URL"
	}
	if parsed.Scheme != "https" {
		return fmt.Sprintf("scheme must be https, got %q", parsed.Scheme)
	}
	host := strings.ToLower(parsed.Hostname())
	if host == "" {
		return "missing host"
	}
	// Check for credential injection
	authority := raw
	if idx := strings.Index(raw, "//"); idx >= 0 {
		authority = raw[idx+2:]
	}
	if slash := strings.IndexByte(authority, '/'); slash >= 0 {
		authority = authority[:slash]
	}
	if strings.ContainsRune(authority, '@') {
		return "credential injection: '@' in authority"
	}
	if isPrivateHost(host) {
		return fmt.Sprintf("private/loopback address: %s", host)
	}
	if host != "microsoft.com" && !strings.HasSuffix(host, ".microsoft.com") {
		return fmt.Sprintf("host must be microsoft.com or *.microsoft.com, got %q", host)
	}
	return ""
}
