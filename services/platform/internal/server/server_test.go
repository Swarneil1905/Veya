package server

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type fakeBackend struct {
	calls        int
	method, path string
	body         []byte
}

func (b *fakeBackend) Request(_ context.Context, method, path string, body []byte) (int, []byte, error) {
	b.calls++
	b.method = method
	b.path = path
	b.body = body
	return 200, []byte(`{"items":[]}`), nil
}
func TestSessionAndCapabilityIsolation(t *testing.T) {
	b := &fakeBackend{}
	token := strings.Repeat("a", 64)
	s, _ := New(b, token, "127.0.0.1:4321", "")
	request := func(path, auth, origin, cookie, body string) *httptest.ResponseRecorder {
		r := httptest.NewRequest("POST", "http://127.0.0.1:4321"+path, strings.NewReader(body))
		r.Header.Set("Authorization", auth)
		r.Header.Set("Origin", origin)
		r.Header.Set("Content-Type", "application/json")
		if cookie != "" {
			r.Header.Set("Cookie", cookie)
		}
		w := httptest.NewRecorder()
		s.ServeHTTP(w, r)
		return w
	}
	body := `{"operation":"list_tasks","args":{}}`
	if w := request("/api/workspace", "", "", "", body); w.Code != 401 {
		t.Fatal(w.Code)
	}
	if w := request("/api/workspace", "Bearer "+token, "https://evil.invalid", "", body); w.Code != 403 {
		t.Fatal(w.Code)
	}
	if w := request("/api/session", "Bearer "+token, "", "", ""); w.Code != 401 {
		t.Fatal(w.Code)
	}
	w := request("/api/session", "Bearer "+token, "http://127.0.0.1:4321", "", "")
	if w.Code != 200 {
		t.Fatal(w.Code)
	}
	c := w.Result().Cookies()[0]
	if !c.HttpOnly || c.SameSite != http.SameSiteStrictMode || strings.Contains(c.Value, token) {
		t.Fatal("unsafe cookie")
	}
	if w := request("/api/workspace", "", "", c.String(), body); w.Code != 401 {
		t.Fatal("cookie write without origin", w.Code)
	}
	if w := request("/api/workspace", "", "http://127.0.0.1:4321", c.String(), body); w.Code != 200 {
		t.Fatal(w.Code)
	}
	if b.calls != 1 || b.path != "/v1/tasks?limit=10" {
		t.Fatal("wrong backend call")
	}
	for _, bad := range []string{`{"operation":"approve","args":{}}`, `{"operation":"list_tasks","args":{"tenant_id":"other"}}`, body + body, `{"operation":"list_tasks","args":{},"url":"https://evil.invalid"}`, strings.Repeat("x", 131073)} {
		if w := request("/api/workspace", "Bearer "+token, "", "", bad); w.Code < 400 {
			t.Fatal("invalid command accepted")
		}
	}
	if b.calls != 1 {
		t.Fatal("forbidden request reached backend")
	}
	r := httptest.NewRequest("GET", "http://evil.invalid/api/health", nil)
	r.Header.Set("Authorization", "Bearer "+token)
	w = httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 403 {
		t.Fatal("DNS rebinding accepted")
	}
	r = httptest.NewRequest("GET", "http://127.0.0.1:4321/v1/tasks", nil)
	w = httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 404 {
		t.Fatal("private endpoint exposed")
	}
	result, _ := io.ReadAll(w.Result().Body)
	if strings.Contains(string(result), token) {
		t.Fatal("token leaked")
	}
}
