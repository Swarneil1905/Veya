// Package workspace defines the application commands available to both clients.
// Python remains the private durable execution store; callers cannot select a
// tenant, upstream address, reviewer identity, or arbitrary worker operation.
package workspace

import (
	"encoding/json"
	"errors"
	"net/url"
	"regexp"
	"strconv"
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
		"list_tasks": {"status", "search", "sort", "cursor"}, "recovery": {},
		"get_task":       {"task_id"},
		"list_approvals": {"after"}, "get_approval": {"id"}, "decide_approval": {"id", "revision", "decision", "note"},
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
	case "list_approvals":
		path = "/v1/approvals?limit=25"
		if raw, exists := c.Args["after"]; exists && string(raw) != "null" {
			var after int64
			if json.Unmarshal(raw, &after) != nil || after < 0 {
				return "", "", nil, ErrInput
			}
			path += "&after=" + strconv.FormatInt(after, 10)
		}
		return "GET", path, nil, nil
	case "get_approval", "decide_approval":
		if !identifier.MatchString(text("id")) {
			return "", "", nil, ErrInput
		}
		path = "/v1/approvals/" + text("id")
		if c.Operation == "get_approval" {
			return "GET", path, nil, nil
		}
		var revision int64
		if json.Unmarshal(c.Args["revision"], &revision) != nil || revision < 1 ||
			(text("decision") != "approve" && text("decision") != "reject") || strings.TrimSpace(text("note")) == "" || utf8.RuneCountInString(text("note")) > 2000 {
			return "", "", nil, ErrInput
		}
		body, err = json.Marshal(map[string]any{"revision": revision, "decision": text("decision"), "note": text("note")})
		return "POST", path + "/decision", body, err

	case "list_tasks":
		query := url.Values{"limit": {"10"}}
		for _, key := range []string{"search", "cursor", "sort", "status"} {
			raw, exists := c.Args[key]
			if !exists || string(raw) == "null" {
				continue
			}
			var value string
			if json.Unmarshal(raw, &value) != nil {
				return "", "", nil, ErrInput
			}
			maximum := 200
			if key == "cursor" {
				maximum = 2048
			}
			if utf8.RuneCountInString(value) > maximum {
				return "", "", nil, ErrInput
			}
			if key == "sort" && value != "newest" && value != "oldest" {
				return "", "", nil, ErrInput
			}
			if key == "status" && !strings.Contains("|queued|running|waiting|succeeded|failed|cancelled|active|attention|completed|", "|"+value+"|") {
				return "", "", nil, ErrInput
			}
			query.Set(key, value)
		}
		return "GET", "/v1/tasks?" + query.Encode(), nil, nil
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
	case "get_task":
		if !identifier.MatchString(text("task_id")) {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/tasks/" + text("task_id"), nil, nil
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
