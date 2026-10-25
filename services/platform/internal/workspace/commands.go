// Package workspace defines the application commands available to both clients.
// Python remains the private durable execution store; callers cannot select a
// tenant, upstream address, reviewer identity, or arbitrary worker operation.
package workspace

import (
	"encoding/json"
	"errors"
	"net/url"
	"regexp"
	"strings"
	"unicode/utf8"
)

var ErrInput = errors.New("invalid_input")
var ErrForbidden = errors.New("forbidden")
var identifier = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)
var cursorNumber = regexp.MustCompile(`^[0-9]{1,18}$`)

type Command struct {
	Operation string                     `json:"operation"`
	Args      map[string]json.RawMessage `json:"args"`
}

// Route is an explicit capability boundary, not a general reverse proxy.
func Route(c Command) (method, path string, body []byte, err error) {
	allowed, ok := map[string][]string{
		"list_tasks": {}, "recovery": {},
		"submit_task": {"client_request_id", "title", "instruction"},
		"latest_run":  {"task_id"}, "events": {"run_id", "after"},
	}[c.Operation]
	if !ok {
		return "", "", nil, ErrForbidden
	}
	if c.Args == nil {
		return "", "", nil, ErrInput
	}
	for key := range c.Args {
		found := false
		for _, name := range allowed {
			if key == name {
				found = true
			}
		}
		if !found {
			return "", "", nil, ErrInput
		}
	}
	text := func(key string) string { var s string; _ = json.Unmarshal(c.Args[key], &s); return s }
	switch c.Operation {
	case "list_tasks":
		return "GET", "/v1/tasks?limit=10", nil, nil
	case "recovery":
		return "GET", "/v1/workspace/recovery", nil, nil
	case "submit_task":
		if !identifier.MatchString(text("client_request_id")) {
			return "", "", nil, ErrInput
		}
		for key, max := range map[string]int{"title": 200, "instruction": 20000} {
			s := text(key)
			if strings.TrimSpace(s) == "" || utf8.RuneCountInString(s) > max {
				return "", "", nil, ErrInput
			}
		}
		body, err = json.Marshal(c.Args)
		return "POST", "/v1/tasks", body, err
	case "latest_run":
		if !identifier.MatchString(text("task_id")) {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/tasks/" + text("task_id") + "/latest-run", nil, nil
	case "events":
		run := text("run_id")
		if !identifier.MatchString(run) {
			return "", "", nil, ErrInput
		}
		path = "/v1/runs/" + run + "/event-page"
		if raw, exists := c.Args["after"]; exists && string(raw) != "null" {
			cursor := text("after")
			name, number, ok := strings.Cut(cursor, ":")
			if !ok || name != run || !cursorNumber.MatchString(number) {
				return "", "", nil, ErrInput
			}
			path += "?after=" + url.QueryEscape(cursor)
		}
		return "GET", path, nil, nil
	}
	return "", "", nil, ErrForbidden
}
