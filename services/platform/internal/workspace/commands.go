// Package workspace defines the application commands available to both clients.
// Python remains the private durable execution store; callers cannot select a
// tenant, upstream address, reviewer identity, or arbitrary worker operation.
package workspace

import (
	"encoding/base64"
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
		"get_task":    {"task_id"},
		"connections": {}, "check_connection": {"config", "consent"}, "activate_connection": {"fingerprints"}, "save_credential": {"reference", "secret"},
		"execute_run": {"run_id", "expected_selection", "allow_remote"}, "cancel_run": {"run_id"}, "document_chunks": {"id", "after"},
		"import_document": {"request_id", "name", "content"},
		"get_document":    {"id"}, "process_document": {"id"}, "retry_document": {"id"}, "revoke_document": {"id"}, "document_versions": {"id"},
		"task_documents": {"task_id"}, "resolve_citation": {"citation"},
		"list_results": {"run_id", "after"}, "download_artifact": {"id"},
		"list_approvals": {"after"}, "get_approval": {"id"}, "decide_approval": {"id", "revision", "decision", "note"},
		"submit_task": {"client_request_id", "title", "instruction", "document_ids"},
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
	case "connections":
		return "GET", "/v1/connections", nil, nil
	case "check_connection", "activate_connection", "save_credential":
		suffix := map[string]string{"check_connection": "check", "activate_connection": "activate", "save_credential": "credential"}[c.Operation]
		body, err = json.Marshal(c.Args)
		if len(body) > 16384 {
			return "", "", nil, ErrInput
		}
		return "POST", "/v1/connections/" + suffix, body, err
	case "execute_run", "cancel_run":
		if !identifier.MatchString(text("run_id")) {
			return "", "", nil, ErrInput
		}
		path = "/v1/runs/" + text("run_id")
		if c.Operation == "cancel_run" {
			return "POST", path + "/cancel", []byte(`{}`), nil
		}
		payload := make(map[string]json.RawMessage)
		for k, v := range c.Args {
			if k != "run_id" {
				payload[k] = v
			}
		}
		body, err = json.Marshal(payload)
		return "POST", path + "/execute", body, err
	case "document_chunks":
		if !identifier.MatchString(text("id")) {
			return "", "", nil, ErrInput
		}
		if value, present := c.Args["after"]; present {
			var cursor string
			if json.Unmarshal(value, &cursor) != nil || cursor == "" {
				return "", "", nil, ErrInput
			}
		}
		after := text("after")
		if after == "" {
			after = "0"
		}
		if !cursorNumber.MatchString(after) {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/documents/" + text("id") + "/chunks?after=" + after, nil, nil
	case "import_document":
		name, content := text("name"), text("content")
		if !identifier.MatchString(text("request_id")) || name == "" || utf8.RuneCountInString(name) > 200 || strings.ContainsAny(name, "/\\:") || len(content) > 699052 {
			return "", "", nil, ErrInput
		}
		raw, decodeErr := base64.StdEncoding.Strict().DecodeString(content)
		if decodeErr != nil || len(raw) == 0 || len(raw) > 524288 {
			return "", "", nil, ErrInput
		}
		body, err = json.Marshal(c.Args)
		return "POST", "/v1/documents", body, err
	case "get_document", "process_document", "retry_document", "revoke_document", "document_versions", "download_artifact":
		if !identifier.MatchString(text("id")) {
			return "", "", nil, ErrInput
		}
		path = "/v1/documents/" + text("id")
		switch c.Operation {
		case "process_document":
			return "POST", path + "/process", []byte(`{}`), nil
		case "retry_document":
			return "POST", path + "/retry", []byte(`{}`), nil
		case "revoke_document":
			return "POST", path + "/revoke", []byte(`{}`), nil
		case "document_versions":
			return "GET", path + "/versions", nil, nil
		case "download_artifact":
			return "GET", "/v1/artifacts/" + text("id") + "/download", nil, nil
		}
		return "GET", path, nil, nil
	case "task_documents":
		if !identifier.MatchString(text("task_id")) {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/tasks/" + text("task_id") + "/documents", nil, nil
	case "resolve_citation":
		id, index, found := strings.Cut(text("citation"), ":")
		if !found || !identifier.MatchString(id) || !cursorNumber.MatchString(index) || len(index) > 6 {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/citations/" + id + ":" + index, nil, nil
	case "list_results":
		if !identifier.MatchString(text("run_id")) {
			return "", "", nil, ErrInput
		}
		var after int64
		if raw, exists := c.Args["after"]; exists && (json.Unmarshal(raw, &after) != nil || after < 0) {
			return "", "", nil, ErrInput
		}
		return "GET", "/v1/runs/" + text("run_id") + "/results?after=" + strconv.FormatInt(after, 10), nil, nil
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
		if raw, exists := c.Args["document_ids"]; exists {
			var ids []string
			if string(raw) == "null" || json.Unmarshal(raw, &ids) != nil || len(ids) > 10 {
				return "", "", nil, ErrInput
			}
			seen := map[string]bool{}
			for _, id := range ids {
				if !identifier.MatchString(id) || seen[id] {
					return "", "", nil, ErrInput
				}
				seen[id] = true
			}
		}
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
