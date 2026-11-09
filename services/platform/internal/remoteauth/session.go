// Package remoteauth validates OIDC login results and issues scoped opaque sessions.
// Membership comes from the server registry, never from a token's role or tenant claim.
package remoteauth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"errors"
	"sync"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
)

var ErrDenied = errors.New("remote session denied")

func bindingMatches(binding string, expected [32]byte) bool {
	actual := sha256.Sum256([]byte(binding))
	return subtle.ConstantTimeCompare(actual[:], expected[:]) == 1
}

type Membership struct {
	Tenant string
	Role   string
}

type Lookup func(issuer, subject, tenant string) (Membership, bool)

type Challenge struct {
	State         string
	Nonce         string
	Verifier      string
	CodeChallenge string
}

type pending struct {
	challenge Challenge
	binding   [32]byte
	tenant    string
	expires   time.Time
}

type Session struct {
	Subject string
	Tenant  string
	Role    string
	Expires time.Time
}

type Manager struct {
	mu       sync.Mutex
	verifier *oidc.IDTokenVerifier
	issuer   string
	clientID string
	lookup   Lookup
	pending  map[string]pending
	sessions map[[32]byte]Session
}

func New(issuer, clientID string, keys oidc.KeySet, lookup Lookup) (*Manager, error) {
	if issuer == "" || clientID == "" || keys == nil || lookup == nil {
		return nil, ErrDenied
	}
	return &Manager{
		verifier: oidc.NewVerifier(issuer, keys, &oidc.Config{
			ClientID:             clientID,
			SupportedSigningAlgs: []string{oidc.RS256},
		}),
		issuer:   issuer,
		clientID: clientID,
		lookup:   lookup,
		pending:  make(map[string]pending),
		sessions: make(map[[32]byte]Session),
	}, nil
}

func secret() (string, error) {
	value := make([]byte, 32)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(value), nil
}

func (m *Manager) Begin(binding, tenant string) (Challenge, error) {
	if len(binding) < 32 || len(binding) > 256 || len(tenant) < 1 || len(tenant) > 64 {
		return Challenge{}, ErrDenied
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	now := time.Now()
	for key, value := range m.pending {
		if !value.expires.After(now) {
			delete(m.pending, key)
		}
	}
	if len(m.pending) >= 1000 {
		return Challenge{}, ErrDenied
	}
	state, err := secret()
	if err != nil {
		return Challenge{}, err
	}
	nonce, err := secret()
	if err != nil {
		return Challenge{}, err
	}
	verifier, err := secret()
	if err != nil {
		return Challenge{}, err
	}
	digest := sha256.Sum256([]byte(verifier))
	challenge := Challenge{state, nonce, verifier, base64.RawURLEncoding.EncodeToString(digest[:])}
	m.pending[state] = pending{
		challenge: challenge,
		binding:   sha256.Sum256([]byte(binding)),
		tenant:    tenant,
		expires:   now.Add(5 * time.Minute),
	}
	return challenge, nil
}

// Finish is called by a trusted authorization-code exchange callback. The caller
// must send Challenge.Verifier to the fixed provider token endpoint and must not
// expose it to the browser. Failed callbacks consume the one-use login state.
func (m *Manager) Finish(ctx context.Context, state, binding, rawIDToken string) (string, error) {
	m.mu.Lock()
	login, ok := m.pending[state]
	delete(m.pending, state)
	m.mu.Unlock()
	bound := sha256.Sum256([]byte(binding))
	if !ok || !login.expires.After(time.Now()) ||
		subtle.ConstantTimeCompare(bound[:], login.binding[:]) != 1 || len(rawIDToken) > 16384 {
		return "", ErrDenied
	}
	token, err := m.verifier.Verify(ctx, rawIDToken)
	if err != nil || token.Subject == "" || len(token.Subject) > 255 ||
		token.Nonce != login.challenge.Nonce || token.IssuedAt.IsZero() ||
		token.IssuedAt.After(time.Now().Add(30*time.Second)) {
		return "", ErrDenied
	}
	var claims struct {
		AuthorizedParty string `json:"azp"`
	}
	if token.Claims(&claims) != nil ||
		(len(token.Audience) > 1 && claims.AuthorizedParty != m.clientID) ||
		(claims.AuthorizedParty != "" && claims.AuthorizedParty != m.clientID) {
		return "", ErrDenied
	}
	member, ok := m.lookup(m.issuer, token.Subject, login.tenant)
	if !ok || member.Tenant != login.tenant || !validRole(member.Role) {
		return "", ErrDenied
	}
	value, err := secret()
	if err != nil {
		return "", err
	}
	expires := time.Now().Add(time.Hour)
	if token.Expiry.Before(expires) {
		expires = token.Expiry
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	for key, session := range m.sessions {
		if !session.Expires.After(time.Now()) {
			delete(m.sessions, key)
		}
	}
	if len(m.sessions) >= 10000 {
		return "", ErrDenied
	}
	m.sessions[sha256.Sum256([]byte(value))] = Session{
		Subject: token.Subject, Tenant: member.Tenant, Role: member.Role, Expires: expires,
	}
	return value, nil
}

func validRole(role string) bool {
	return role == "operator" || role == "reviewer" || role == "admin"
}

func (m *Manager) Authenticate(value, tenant string) (Session, error) {
	if len(value) != 43 {
		return Session{}, ErrDenied
	}
	m.mu.Lock()
	session, ok := m.sessions[sha256.Sum256([]byte(value))]
	m.mu.Unlock()
	if !ok || !session.Expires.After(time.Now()) || session.Tenant != tenant {
		return Session{}, ErrDenied
	}
	member, ok := m.lookup(m.issuer, session.Subject, tenant)
	if !ok || member.Tenant != tenant || !validRole(member.Role) {
		return Session{}, ErrDenied
	}
	session.Role = member.Role
	return session, nil
}

func (m *Manager) Revoke(value string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.sessions, sha256.Sum256([]byte(value)))
}
