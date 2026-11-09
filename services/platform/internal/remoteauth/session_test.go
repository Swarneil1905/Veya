package remoteauth

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
)

func signed(t *testing.T, key *rsa.PrivateKey, claims map[string]any) string {
	t.Helper()
	body, err := json.Marshal(claims)
	if err != nil {
		t.Fatal(err)
	}
	header := base64.RawURLEncoding.EncodeToString([]byte(`{"alg":"RS256","typ":"JWT"}`))
	message := header + "." + base64.RawURLEncoding.EncodeToString(body)
	digest := sha256.Sum256([]byte(message))
	signature, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if err != nil {
		t.Fatal(err)
	}
	return message + "." + base64.RawURLEncoding.EncodeToString(signature)
}

func TestOIDCSessionValidation(t *testing.T) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	for _, scenario := range []string{
		"valid", "issuer", "audience", "expired", "nonce", "binding", "state", "signature", "azp",
	} {
		t.Run(scenario, func(t *testing.T) {
			allowed := true
			manager, err := New("https://identity.example", "veya", &oidc.StaticKeySet{
				PublicKeys: []crypto.PublicKey{&key.PublicKey},
			}, func(issuer, subject, tenant string) (Membership, bool) {
				return Membership{Tenant: "acme", Role: "operator"},
					allowed && subject == "alice" && tenant == "acme"
			})
			if err != nil {
				t.Fatal(err)
			}
			binding := strings.Repeat("b", 32)
			challenge, err := manager.Begin(binding, "acme")
			if err != nil {
				t.Fatal(err)
			}
			claims := map[string]any{
				"iss": "https://identity.example", "aud": "veya", "sub": "alice",
				"exp": time.Now().Add(time.Hour).Unix(), "iat": time.Now().Unix(),
				"nonce":  challenge.Nonce,
				"tenant": "other", "role": "admin",
			}
			state := challenge.State
			switch scenario {
			case "issuer":
				claims["iss"] = "https://attacker.example"
			case "audience":
				claims["aud"] = "other"
			case "expired":
				claims["exp"] = time.Now().Add(-time.Minute).Unix()
			case "nonce":
				claims["nonce"] = "other"
			case "binding":
				binding = "wrong-browser"
			case "state":
				state = "wrong-state"
			case "azp":
				claims["azp"] = "other"
			}
			raw := signed(t, key, claims)
			if scenario == "signature" {
				raw = raw[:len(raw)-10] + "invalidsig"
			}
			value, err := manager.Finish(context.Background(), state, binding, raw)
			if scenario != "valid" {
				if err == nil {
					t.Fatal("invalid login accepted")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			session, err := manager.Authenticate(value, "acme")
			if err != nil || session.Role != "operator" {
				t.Fatal(session, err)
			}
			if _, err := manager.Authenticate(value, "other"); err == nil {
				t.Fatal("cross-tenant session accepted")
			}
			if _, err := manager.Finish(context.Background(), state, binding, raw); err == nil {
				t.Fatal("login replay accepted")
			}
			allowed = false
			if _, err := manager.Authenticate(value, "acme"); err == nil {
				t.Fatal("revoked membership accepted")
			}
			allowed = true
			manager.Revoke(value)
			if _, err := manager.Authenticate(value, "acme"); err == nil {
				t.Fatal("revoked session accepted")
			}
		})
	}
}
