package remoteauth

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

type LoginFlow interface {
	Start(binding, tenant string) (string, error)
	Complete(context.Context, string, string, string) (string, error)
	Authenticate(value, tenant string) (Session, error)
	Revoke(value string)
}

type Gateway struct {
	login        LoginFlow
	origin       *url.URL
	backend      *url.URL
	backendToken string
	client       *http.Client
}

func NewGateway(login LoginFlow, origin, backend, backendToken string) (*Gateway, error) {
	public, err := url.Parse(origin)
	if err != nil || public.Scheme != "https" || public.Host == "" ||
		public.User != nil || public.Path != "" || public.RawQuery != "" || public.Fragment != "" {
		return nil, ErrDenied
	}
	private, err := url.Parse(backend)
	if err != nil || private.Host == "" || private.User != nil || private.Path != "" ||
		private.RawQuery != "" || private.Fragment != "" ||
		(private.Scheme != "https" && !(private.Scheme == "http" && private.Hostname() == "127.0.0.1")) {
		return nil, ErrDenied
	}
	if login == nil || len(backendToken) < 32 || len(backendToken) > 256 {
		return nil, ErrDenied
	}
	return &Gateway{login, public, private, backendToken, &http.Client{
		Timeout:       15 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}}, nil
}

func denied(w http.ResponseWriter, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(`{"error":"request_denied"}`))
}

func cookie(w http.ResponseWriter, name, value string, age int) {
	http.SetCookie(w, &http.Cookie{
		Name: name, Value: value, Path: "/", Secure: true, HttpOnly: true,
		SameSite: http.SameSiteLaxMode, MaxAge: age,
	})
}

var identity = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)

func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	if r.Host != g.origin.Host {
		denied(w, 403)
		return
	}
	if r.Method != "GET" && r.Header.Get("Origin") != g.origin.String() {
		denied(w, 403)
		return
	}
	if r.URL.Path == "/auth/start" && r.Method == "POST" {
		var input struct {
			Tenant string `json:"tenant"`
		}
		decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1024))
		decoder.DisallowUnknownFields()
		if decoder.Decode(&input) != nil || decoder.Decode(new(any)) != io.EOF || !identity.MatchString(input.Tenant) {
			denied(w, 400)
			return
		}
		binding, err := secret()
		if err != nil {
			denied(w, 503)
			return
		}
		location, err := g.login.Start(binding, input.Tenant)
		if err != nil {
			denied(w, 403)
			return
		}
		cookie(w, "__Host-veya_login", binding, 300)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"authorization_url": location})
		return
	}
	if r.URL.Path == "/auth/callback" && r.Method == "GET" {
		binding, err := r.Cookie("__Host-veya_login")
		if err != nil {
			denied(w, 401)
			return
		}
		cookie(w, "__Host-veya_login", "", -1)
		value, err := g.login.Complete(r.Context(), r.URL.Query().Get("state"), binding.Value, r.URL.Query().Get("code"))
		if err != nil {
			denied(w, 401)
			return
		}
		cookie(w, "__Host-veya_session", value, 3600)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"authenticated":true}`))
		return
	}
	if r.URL.RawQuery != "" {
		denied(w, 400)
		return
	}
	credential, err := r.Cookie("__Host-veya_session")
	if err != nil {
		denied(w, 401)
		return
	}
	tenant := r.Header.Get("X-Veya-Workspace")
	if !identity.MatchString(tenant) {
		denied(w, 403)
		return
	}
	session, err := g.login.Authenticate(credential.Value, tenant)
	if err != nil {
		denied(w, 401)
		return
	}
	if r.URL.Path == "/auth/logout" && r.Method == "POST" {
		g.login.Revoke(credential.Value)
		cookie(w, "__Host-veya_session", "", -1)
		w.WriteHeader(204)
		return
	}
	path := strings.TrimPrefix(r.URL.Path, "/api")
	allowed := r.Method == "POST" && (r.URL.Path == "/api/tasks" || r.URL.Path == "/api/search")
	if r.Method == "GET" && strings.HasPrefix(r.URL.Path, "/api/tasks/") {
		allowed = identity.MatchString(strings.TrimPrefix(r.URL.Path, "/api/tasks/"))
	}
	if !allowed {
		denied(w, 404)
		return
	}
	if path == "/tasks" && session.Role != "operator" && session.Role != "admin" {
		denied(w, 403)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 131072))
	if err != nil {
		denied(w, 413)
		return
	}
	request, err := http.NewRequestWithContext(r.Context(), r.Method, g.backend.String()+path, bytes.NewReader(body))
	if err != nil {
		denied(w, 400)
		return
	}
	request.Header.Set("Authorization", "Bearer "+g.backendToken)
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Veya-Tenant", session.Tenant)
	request.Header.Set("X-Veya-Subject", session.Subject)
	request.Header.Set("X-Veya-Role", session.Role)
	response, err := g.client.Do(request)
	if err != nil {
		denied(w, 503)
		return
	}
	defer response.Body.Close()
	result, err := io.ReadAll(io.LimitReader(response.Body, 1048577))
	if err != nil || len(result) > 1048576 {
		denied(w, 502)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(response.StatusCode)
	_, _ = w.Write(result)
}
