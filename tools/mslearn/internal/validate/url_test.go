package validate

import "testing"

func TestIsPrivateHost(t *testing.T) {
	tests := []struct {
		host string
		want bool
	}{
		{"localhost", true},
		{"127.0.0.1", true},
		{"0.0.0.0", true},
		{"::1", true},
		{"10.0.0.1", true},
		{"127.0.0.2", true},
		{"192.168.1.1", true},
		{"169.254.0.1", true},
		{"172.16.0.1", true},
		{"172.31.255.255", true},
		{"172.15.0.1", false},
		{"172.32.0.1", false},
		{"8.8.8.8", false},
		{"learn.microsoft.com", false},
	}
	for _, tt := range tests {
		if got := isPrivateHost(tt.host); got != tt.want {
			t.Errorf("isPrivateHost(%q) = %v, want %v", tt.host, got, tt.want)
		}
	}
}

func TestURL(t *testing.T) {
	tests := []struct {
		url     string
		wantErr bool
		errMsg  string
	}{
		// Valid
		{"https://learn.microsoft.com/en-us/azure/functions", false, ""},
		{"https://microsoft.com/something", false, ""},
		{"https://docs.microsoft.com/en-us/dotnet", false, ""},
		// Invalid scheme
		{"http://learn.microsoft.com/foo", true, `scheme must be https, got "http"`},
		{"ftp://learn.microsoft.com/foo", true, `scheme must be https, got "ftp"`},
		// Missing host
		{"https:///path", true, "missing host"},
		// Credential injection
		{"https://evil@learn.microsoft.com/foo", true, "credential injection: '@' in authority"},
		// Private address
		{"https://localhost/foo", true, "private/loopback address: localhost"},
		{"https://127.0.0.1/foo", true, "private/loopback address: 127.0.0.1"},
		{"https://10.0.0.1/foo", true, "private/loopback address: 10.0.0.1"},
		// Wrong domain
		{"https://evil.com/foo", true, `host must be microsoft.com or *.microsoft.com, got "evil.com"`},
		{"https://microsoft.com.evil.com/foo", true, `host must be microsoft.com or *.microsoft.com, got "microsoft.com.evil.com"`},
	}
	for _, tt := range tests {
		got := URL(tt.url)
		if tt.wantErr && got == "" {
			t.Errorf("URL(%q) = empty, want error", tt.url)
		} else if !tt.wantErr && got != "" {
			t.Errorf("URL(%q) = %q, want empty", tt.url, got)
		} else if tt.wantErr && tt.errMsg != "" && got != tt.errMsg {
			t.Errorf("URL(%q) = %q, want %q", tt.url, got, tt.errMsg)
		}
	}
}
