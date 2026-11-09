package remoteauth

import (
	"context"
	"net/http"
	"net/url"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"golang.org/x/oauth2"
)

// Login exchanges authorization codes only with administrator-configured HTTPS
// endpoints. Its callbacks must be exposed behind a TLS application boundary.
type Login struct {
	manager *Manager
	oauth   oauth2.Config
}

func NewLogin(ctx context.Context, issuer, clientID, redirectURI string, lookup Lookup) (*Login, error) {
	for _, raw := range []string{issuer, redirectURI} {
		parsed, err := url.Parse(raw)
		if err != nil || parsed.Scheme != "https" || parsed.Host == "" ||
			parsed.User != nil || parsed.Fragment != "" {
			return nil, ErrDenied
		}
	}
	client := &http.Client{Timeout: 10 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	ctx = oidc.ClientContext(ctx, client)
	provider, err := oidc.NewProvider(ctx, issuer)
	if err != nil {
		return nil, err
	}
	endpoint := provider.Endpoint()
	for _, raw := range []string{endpoint.AuthURL, endpoint.TokenURL} {
		parsed, err := url.Parse(raw)
		if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil {
			return nil, ErrDenied
		}
	}
	var metadata struct {
		JWKS string `json:"jwks_uri"`
	}
	if provider.Claims(&metadata) != nil {
		return nil, ErrDenied
	}
	keys, err := url.Parse(metadata.JWKS)
	if err != nil || keys.Scheme != "https" || keys.Host == "" || keys.User != nil {
		return nil, ErrDenied
	}
	manager, err := New(issuer, clientID, oidc.NewRemoteKeySet(ctx, metadata.JWKS), lookup)
	if err != nil {
		return nil, err
	}
	return &Login{manager: manager, oauth: oauth2.Config{
		ClientID: clientID, RedirectURL: redirectURI, Endpoint: endpoint,
		Scopes: []string{oidc.ScopeOpenID},
	}}, nil
}

func (l *Login) Start(binding, tenant string) (string, error) {
	challenge, err := l.manager.Begin(binding, tenant)
	if err != nil {
		return "", err
	}
	return l.oauth.AuthCodeURL(challenge.State,
		oidc.Nonce(challenge.Nonce),
		oauth2.S256ChallengeOption(challenge.Verifier),
	), nil
}

func (l *Login) Complete(ctx context.Context, state, binding, code string) (string, error) {
	if len(code) < 1 || len(code) > 4096 {
		return "", ErrDenied
	}
	// Consume before the network call so concurrent callbacks cannot exchange twice.
	l.manager.mu.Lock()
	challenge, ok := l.manager.pending[state]
	delete(l.manager.pending, state)
	l.manager.mu.Unlock()
	if !ok || !challenge.expires.After(time.Now()) {
		return "", ErrDenied
	}
	if !bindingMatches(binding, challenge.binding) {
		return "", ErrDenied
	}
	client := &http.Client{Timeout: 10 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	ctx = context.WithValue(ctx, oauth2.HTTPClient, client)
	token, err := l.oauth.Exchange(ctx, code, oauth2.VerifierOption(challenge.challenge.Verifier))
	if err != nil {
		return "", ErrDenied
	}
	raw, ok := token.Extra("id_token").(string)
	if !ok {
		return "", ErrDenied
	}
	// Use a fresh internal state, never reinstate the public consumed state.
	internal, err := secret()
	if err != nil {
		return "", err
	}
	l.manager.mu.Lock()
	l.manager.pending[internal] = challenge
	l.manager.mu.Unlock()
	return l.manager.Finish(ctx, internal, binding, raw)
}

func (l *Login) Authenticate(value, tenant string) (Session, error) {
	return l.manager.Authenticate(value, tenant)
}

func (l *Login) Revoke(value string) { l.manager.Revoke(value) }
