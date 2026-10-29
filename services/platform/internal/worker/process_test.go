package worker

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
	"veya/platform/internal/tracecontext"
)

func settings(t *testing.T) (string, string) {
	t.Helper()
	python := os.Getenv("VEYA_PYTHON")
	if python == "" {
		python = "python"
	}
	source, err := filepath.Abs("../../../runtime")
	if err != nil {
		t.Fatal(err)
	}
	return python, source
}

func TestPrivateWorkerDurabilityAndIsolation(t *testing.T) {
	python, source := settings(t)
	storage := t.TempDir()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	p, err := Start(ctx, python, source, storage)
	if err != nil {
		t.Fatal(err)
	}
	defer p.Close()
	parent := "00-" + strings.Repeat("a", 32) + "-" + strings.Repeat("b", 16) + "-01"
	_, _, err = p.Request(tracecontext.With(ctx, parent), "GET", "/v1/health", nil)
	if err != nil {
		t.Fatal(err)
	}
	statusDiag, diagnostics, err := p.Request(ctx, "POST", "/v1/diagnostics/export", []byte(`{}`))
	if err != nil || statusDiag != 200 || !strings.Contains(string(diagnostics), strings.Repeat("a", 32)) || strings.Contains(string(diagnostics), p.token) {
		t.Fatal("private trace propagation or diagnostic redaction failed")
	}
	request := []byte(`{"client_request_id":"migration_test","title":"Saved across Go restart","instruction":"Keep the same submission identity"}`)
	status, first, err := p.Request(ctx, "POST", "/v1/tasks", request)
	if err != nil || status != 201 {
		t.Fatalf("save %d %s %v", status, first, err)
	}
	var saved map[string]any
	_ = json.Unmarshal(first, &saved)
	// The worker rejects the platform's caller credential: only its own private token works.
	req, _ := http.NewRequestWithContext(ctx, "GET", "http://127.0.0.1:"+strconv.Itoa(p.port)+"/v1/health", nil)
	req.Header.Set("Authorization", "Bearer caller-token-that-is-not-the-worker-token")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 401 {
		t.Fatal("worker accepted public credential")
	}
	// Review credentials are injected only by the private Go worker boundary.
	status, _, err = p.Request(ctx, "GET", "/v1/approvals?limit=25", nil)
	if err != nil || status != 200 {
		t.Fatalf("review inbox %d %v", status, err)
	}
	req, _ = http.NewRequestWithContext(ctx, "GET", "http://127.0.0.1:"+strconv.Itoa(p.port)+"/v1/approvals", nil)
	req.Header.Set("Authorization", "Bearer "+p.token)
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 403 {
		t.Fatal("ordinary worker credential authorized review")
	}
	oldToken := p.token
	p.Close()
	select {
	case <-p.Done():
	default:
		t.Fatal("worker not reaped")
	}
	p2, err := Start(ctx, python, source, storage)
	if err != nil {
		t.Fatal(err)
	}
	defer p2.Close()
	if p2.token == oldToken {
		t.Fatal("worker credential reused")
	}
	status, second, err := p2.Request(ctx, "POST", "/v1/tasks", request)
	if err != nil || status >= 300 {
		t.Fatalf("retry %d %s %v", status, second, err)
	}
	var retried map[string]any
	_ = json.Unmarshal(second, &retried)
	if saved["task"].(map[string]any)["id"] != retried["task"].(map[string]any)["id"] {
		t.Fatal("retry duplicated task")
	}
	_, items, err := p2.Request(ctx, "GET", "/v1/tasks?limit=10", nil)
	if err != nil {
		t.Fatal(err)
	}
	var list struct {
		Items []json.RawMessage `json:"items"`
	}
	_ = json.Unmarshal(items, &list)
	if len(list.Items) != 1 {
		t.Fatalf("lost or duplicated work: %s", items)
	}
}

func TestMissingAndInvalidWorkersFailClosed(t *testing.T) {
	python, _ := settings(t)
	root := t.TempDir()
	if p, err := Start(context.Background(), filepath.Join(root, "missing"), root, root); err == nil {
		p.Close()
		t.Fatal("missing executable accepted")
	}
	pkg := filepath.Join(root, "veya")
	if err := os.Mkdir(pkg, 0700); err != nil {
		t.Fatal(err)
	}
	_ = os.WriteFile(filepath.Join(pkg, "__init__.py"), nil, 0600)
	_ = os.WriteFile(filepath.Join(pkg, "desktop.py"), []byte("import sys,time\nsys.stdin.readline()\nprint('{\"protocol\":2,\"status\":\"ready\",\"port\":12345}',flush=True)\ntime.sleep(60)\n"), 0600)
	started := time.Now()
	if p, err := Start(context.Background(), python, root, root); err == nil {
		p.Close()
		t.Fatal("invalid protocol accepted")
	}
	if time.Since(started) > 8*time.Second {
		t.Fatal("failed worker not bounded")
	}
}
