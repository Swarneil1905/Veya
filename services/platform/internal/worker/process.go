// Package worker owns a private Python process and its independent credential.
package worker

import (
	"bufio"
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
	"veya/platform/internal/tracecontext"
)

type Process struct {
	cmd           *exec.Cmd
	input         io.WriteCloser
	done          chan struct{}
	once          sync.Once
	port          int
	token         string
	reviewerToken string
	client        *http.Client
}

func Start(ctx context.Context, python, source, storage string) (*Process, error) {
	if !filepath.IsAbs(storage) {
		return nil, errors.New("storage must be absolute")
	}
	secret := make([]byte, 64)
	if _, err := rand.Read(secret); err != nil {
		return nil, err
	}
	p := &Process{token: hex.EncodeToString(secret[:32]), reviewerToken: hex.EncodeToString(secret[32:]), done: make(chan struct{}), client: &http.Client{Timeout: 10 * time.Second, Transport: &http.Transport{Proxy: nil}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
	p.cmd = exec.Command(python, "-u", "-m", "veya.desktop")
	hideWindow(p.cmd)
	p.cmd.Dir = source
	p.cmd.Env = append(os.Environ(), "PYTHONPATH="+source, "PYTHONUTF8=1")
	var err error
	p.input, err = p.cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := p.cmd.StdoutPipe()
	if err != nil {
		p.input.Close()
		return nil, err
	}
	if err = p.cmd.Start(); err != nil {
		p.input.Close()
		out.Close()
		return nil, err
	}
	go func() { _ = p.cmd.Wait(); close(p.done) }()
	failed := true
	defer func() {
		if failed {
			p.Close()
		}
	}()
	err = json.NewEncoder(p.input).Encode(map[string]any{"protocol": 1, "storage_root": storage, "session_token": p.token, "reviewer_token": p.reviewerToken})
	if err != nil {
		return nil, err
	}
	type ready struct {
		Status   string `json:"status"`
		Protocol int    `json:"protocol"`
		Port     int    `json:"port"`
	}
	result := make(chan ready, 1)
	go func() {
		var r ready
		line, _ := bufio.NewReader(io.LimitReader(out, 4096)).ReadBytes('\n')
		_ = json.Unmarshal(line, &r)
		result <- r
	}()
	select {
	case r := <-result:
		if r.Status != "ready" || r.Protocol != 1 || r.Port < 1 || r.Port > 65535 {
			return nil, errors.New("worker readiness failed")
		}
		p.port = r.Port
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(10 * time.Second):
		return nil, errors.New("worker startup timeout")
	}
	status, body, err := p.Request(ctx, "GET", "/v1/health", nil)
	var health struct {
		Protocol int `json:"protocol"`
	}
	if err != nil || status != 200 || json.Unmarshal(body, &health) != nil || health.Protocol != 1 {
		return nil, errors.New("worker health failed")
	}
	failed = false
	return p, nil
}

func (p *Process) Done() <-chan struct{} { return p.done }

func (p *Process) Request(ctx context.Context, method, path string, body []byte) (int, []byte, error) {
	select {
	case <-p.done:
		return 0, nil, errors.New("worker stopped")
	default:
	}
	req, err := http.NewRequestWithContext(ctx, method, "http://127.0.0.1:"+strconv.Itoa(p.port)+path, bytes.NewReader(body))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Authorization", "Bearer "+p.token)
	if parent := tracecontext.Header(ctx); parent != "" {
		req.Header.Set("Traceparent", parent)
	}
	if path == "/v1/approvals" || strings.HasPrefix(path, "/v1/approvals/") || strings.HasPrefix(path, "/v1/approvals?") {
		req.Header.Set("X-Veya-Reviewer-Token", p.reviewerToken)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := p.client.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 4*1024*1024+1))
	if len(data) > 4*1024*1024 {
		return 0, nil, errors.New("worker response too large")
	}
	return resp.StatusCode, data, err
}

func (p *Process) Close() {
	p.once.Do(func() {
		_ = p.input.Close()
		select {
		case <-p.done:
		case <-time.After(3500 * time.Millisecond):
			_ = p.cmd.Process.Kill()
			<-p.done
		}
		p.client.CloseIdleConnections()
	})
}
