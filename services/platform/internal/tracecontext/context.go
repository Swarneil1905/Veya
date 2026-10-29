// Package tracecontext carries only W3C correlation IDs, never baggage or credentials.
package tracecontext

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"regexp"
	"strings"
)

type key struct{}

var pattern = regexp.MustCompile(`^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$`)

func With(ctx context.Context, incoming string) context.Context {
	if !pattern.MatchString(incoming) || strings.Split(incoming, "-")[1] == strings.Repeat("0", 32) || strings.Split(incoming, "-")[2] == strings.Repeat("0", 16) {
		bytes := make([]byte, 24)
		if _, err := rand.Read(bytes); err != nil {
			return ctx
		}
		incoming = "00-" + hex.EncodeToString(bytes[:16]) + "-" + hex.EncodeToString(bytes[16:]) + "-01"
	}
	return context.WithValue(ctx, key{}, incoming)
}

func Header(ctx context.Context) string {
	value, _ := ctx.Value(key{}).(string)
	return value
}
