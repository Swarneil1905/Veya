package remoteauth

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fixtureLogin struct{}

func (fixtureLogin) Start(binding, tenant string) (string, error) {
	return "https://identity.example/authorize", nil
}
func (fixtureLogin) Complete(context.Context, string, string, string) (string, error) {
	return "fixture-session", nil
}
func (fixtureLogin) Authenticate(value, tenant string) (Session, error) {
	if value != "fixture-session" || tenant != "acme" {
		return Session{}, ErrDenied
	}
	return Session{Subject: "alice", Tenant: "acme", Role: "operator"}, nil
}
func (fixtureLogin) Revoke(string) {}

func TestGatewayUsesOnlyServerMembershipAndBoundsRoutes(t *testing.T) {
	calls := 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("X-Veya-Tenant") != "acme" || r.Header.Get("X-Veya-Role") != "operator" ||
			r.Header.Get("X-Veya-Subject") != "alice" || r.Header.Get("Authorization") != "Bearer "+strings.Repeat("s", 32) {
			t.Error("gateway forwarded attacker-controlled identity")
		}
		_, _ = io.WriteString(w, `{"id":"task"}`)
	}))
	defer backend.Close()
	gateway, err := NewGateway(fixtureLogin{}, "https://veya.example", backend.URL, strings.Repeat("s", 32))
	if err != nil {
		t.Fatal(err)
	}
	for _, scenario := range []struct {
		path, method, origin, tenant string
		status                       int
	}{
		{"/api/tasks/task", "GET", "", "acme", 200},
		{"/api/tasks/task", "GET", "", "other", 401},
		{"/api/tasks", "POST", "https://attacker.example", "acme", 403},
		{"/api/admin", "POST", "https://veya.example", "acme", 404},
		{"/api/tasks/task?tenant=other", "GET", "", "acme", 400},
	} {
		r := httptest.NewRequest(scenario.method, "https://veya.example"+scenario.path, strings.NewReader(`{}`))
		r.Header.Set("Origin", scenario.origin)
		r.Header.Set("X-Veya-Workspace", scenario.tenant)
		r.Header.Set("X-Veya-Tenant", "other")
		r.Header.Set("X-Veya-Role", "admin")
		r.AddCookie(&http.Cookie{Name: "__Host-veya_session", Value: "fixture-session"})
		w := httptest.NewRecorder()
		gateway.ServeHTTP(w, r)
		if w.Code != scenario.status {
			t.Errorf("%s: got %d, want %d", scenario.path, w.Code, scenario.status)
		}
	}
	if calls != 1 {
		t.Fatal("forbidden routes reached private backend", calls)
	}
}

func TestGatewayLoginCookieAndInvalidConfiguration(t *testing.T) {
	for _, origin := range []string{"http://veya.example", "https://user@veya.example", "https://veya.example/path"} {
		if _, err := NewGateway(fixtureLogin{}, origin, "http://127.0.0.1:8080", strings.Repeat("s", 32)); err == nil {
			t.Fatal("invalid public origin accepted")
		}
	}
	g, err := NewGateway(fixtureLogin{}, "https://veya.example", "http://127.0.0.1:8080", strings.Repeat("s", 32))
	if err != nil {
		t.Fatal(err)
	}
	r := httptest.NewRequest("POST", "https://veya.example/auth/start", strings.NewReader(`{"tenant":"acme"}`))
	r.Header.Set("Origin", "https://veya.example")
	w := httptest.NewRecorder()
	g.ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatal(w.Code)
	}
	cookies := w.Result().Cookies()
	if len(cookies) != 1 || !cookies[0].Secure || !cookies[0].HttpOnly || cookies[0].Path != "/" {
		t.Fatal("login binding cookie is not protected")
	}
}
