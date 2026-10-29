// Package server is the local platform's authenticated application boundary.
package server

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"veya/platform/internal/tracecontext"
	"veya/platform/internal/workspace"
)

type Backend interface {
	Request(context.Context, string, string, []byte) (int, []byte, error)
}
type Server struct {
	backend                     Backend
	token, cookie, host, assets string
}

func New(backend Backend, token, host, assets string) (*Server, error) {
	if len(token) < 32 || len(token) > 256 {
		return nil, workspace.ErrInput
	}
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	return &Server{backend: backend, token: token, cookie: hex.EncodeToString(b), host: host, assets: assets}, nil
}

func equal(a, b string) bool {
	x, y := sha256.Sum256([]byte(a)), sha256.Sum256([]byte(b))
	return subtle.ConstantTimeCompare(x[:], y[:]) == 1
}
func reply(w http.ResponseWriter, status int, body []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Length", strconv.Itoa(len(body)))
	w.WriteHeader(status)
	_, _ = w.Write(body)
}
func failure(w http.ResponseWriter, status int, code string) {
	reply(w, status, []byte(`{"error":{"code":"`+code+`"}}`))
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'")
	// Exact Host blocks DNS rebinding. No CORS, forwarded identity, or tenant headers.
	if r.Host != s.host {
		failure(w, 403, "forbidden")
		return
	}
	origin := r.Header.Get("Origin")
	if origin != "" && origin != "http://"+s.host {
		failure(w, 403, "forbidden")
		return
	}
	if r.Header.Get("Sec-Fetch-Site") == "cross-site" {
		failure(w, 403, "forbidden")
		return
	}
	if r.URL.RawQuery != "" {
		failure(w, 400, "invalid_input")
		return
	}
	if r.URL.Path == "/api/session" && r.Method == "POST" {
		if origin != "http://"+s.host || !equal(r.Header.Get("Authorization"), "Bearer "+s.token) {
			failure(w, 401, "unauthenticated")
			return
		}
		http.SetCookie(w, &http.Cookie{Name: "veya_session", Value: s.cookie, HttpOnly: true, SameSite: http.SameSiteStrictMode, Path: "/api", MaxAge: 0})
		reply(w, 200, []byte(`{"connected":true}`))
		return
	}
	if strings.HasPrefix(r.URL.Path, "/api/") || r.URL.Path == "/v1/health" {
		authorized := equal(r.Header.Get("Authorization"), "Bearer "+s.token)
		if c, err := r.Cookie("veya_session"); err == nil && equal(c.Value, s.cookie) {
			// Cookie-authenticated writes always require an exact same-origin request.
			authorized = r.Method == "GET" || origin == "http://"+s.host
		}
		if !authorized {
			failure(w, 401, "unauthenticated")
			return
		}
		if (r.URL.Path == "/api/health" || r.URL.Path == "/v1/health") && r.Method == "GET" {
			s.forward(w, r, "GET", "/v1/health", nil)
			return
		}
		if r.URL.Path == "/api/workspace" && r.Method == "POST" {
			if strings.Split(r.Header.Get("Content-Type"), ";")[0] != "application/json" {
				failure(w, 415, "invalid_input")
				return
			}
			data, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 786432))
			if err != nil {
				failure(w, 413, "too_large")
				return
			}
			dec := json.NewDecoder(bytes.NewReader(data))
			dec.DisallowUnknownFields()
			var command workspace.Command
			if dec.Decode(&command) != nil || dec.Decode(new(any)) != io.EOF {
				failure(w, 400, "invalid_input")
				return
			}
			method, path, body, err := workspace.Route(command)
			if err != nil {
				status := 400
				if err == workspace.ErrForbidden {
					status = 403
				}
				failure(w, status, err.Error())
				return
			}
			s.forward(w, r, method, path, body)
			return
		}
		failure(w, 404, "not_found")
		return
	}
	if s.assets == "" || (r.Method != "GET" && r.Method != "HEAD") {
		failure(w, 404, "not_found")
		return
	}
	if r.URL.Path == "/" {
		body, err := os.ReadFile(filepath.Join(s.assets, "index.html"))
		if err != nil {
			failure(w, 503, "frontend_unavailable")
			return
		}
		body = bytes.Replace(body, []byte("<head>"), []byte(`<head><meta name="veya-platform" content="local">`), 1)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write(body)
		return
	}
	// Built assets only. No directory browsing, source files, or SPA path fallback.
	name := strings.TrimPrefix(r.URL.Path, "/")
	if name == "" || strings.Contains(name, "..") || strings.ContainsAny(name, "\\:") || strings.HasPrefix(name, ".") {
		failure(w, 404, "not_found")
		return
	}
	ext := filepath.Ext(name)
	if ext != ".js" && ext != ".css" && ext != ".woff2" && ext != ".woff" && ext != ".svg" && ext != ".ico" {
		failure(w, 404, "not_found")
		return
	}
	http.ServeFile(w, r, filepath.Join(s.assets, filepath.FromSlash(name)))
}

func (s *Server) forward(w http.ResponseWriter, r *http.Request, method, path string, body []byte) {
	ctx := tracecontext.With(r.Context(), r.Header.Get("Traceparent"))
	status, data, err := s.backend.Request(ctx, method, path, body)
	if err != nil || status < 200 || status >= 500 || !json.Valid(data) {
		failure(w, 503, "runtime_unavailable")
		return
	}
	if status >= 300 && status < 400 {
		failure(w, 503, "runtime_unavailable")
		return
	}
	reply(w, status, data)
}
