package tracecontext

import (
	"context"
	"strings"
	"testing"
)

func TestParentValidationAndFreshCorrelation(t *testing.T) {
	parent := "00-" + strings.Repeat("a", 32) + "-" + strings.Repeat("b", 16) + "-00"
	if Header(With(context.Background(), parent)) != parent {
		t.Fatal("valid unsampled parent lost")
	}
	seen := map[string]bool{}
	for _, bad := range []string{"", "secret", "00-" + strings.Repeat("0", 32) + "-" + strings.Repeat("b", 16) + "-01", parent + "\r\nBaggage: private"} {
		header := Header(With(context.Background(), bad))
		if !pattern.MatchString(header) || seen[header] || header == bad {
			t.Fatal("invalid parent reused or correlation duplicated")
		}
		seen[header] = true
	}
}
