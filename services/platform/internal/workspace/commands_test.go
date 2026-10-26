package workspace

import (
	"encoding/json"
	"strings"
	"testing"
)

func command(op, args string) Command {
	var c Command
	_ = json.Unmarshal([]byte(`{"operation":"`+op+`","args":`+args+`}`), &c)
	return c
}
func TestCommandCapabilities(t *testing.T) {
	for _, tc := range []struct{ op, args, path string }{
		{"list_tasks", `{}`, "/v1/tasks?limit=10"},
		{"get_task", `{"task_id":"task_a"}`, "/v1/tasks/task_a"},
		{"list_tasks", `{"status":"attention","sort":"oldest","search":"a&b"}`, "/v1/tasks?limit=10&search=a%26b&sort=oldest&status=attention"},
		{"list_approvals", `{"after":2}`, "/v1/approvals?limit=25&after=2"},
		{"get_approval", `{"id":"review_1"}`, "/v1/approvals/review_1"},
		{"decide_approval", `{"id":"review_1","revision":1,"decision":"reject","note":"Reviewed"}`, "/v1/approvals/review_1/decision"},
		{"recovery", `{}`, "/v1/workspace/recovery"},
		{"latest_run", `{"task_id":"task_a"}`, "/v1/tasks/task_a/latest-run"},
		{"events", `{"run_id":"run_a","after":"run_a:2"}`, "/v1/runs/run_a/event-page?after=run_a%3A2"},
		{"submit_task", `{"client_request_id":"r_1","title":"Title","instruction":"Do work"}`, "/v1/tasks"},
	} {
		t.Run(tc.op, func(t *testing.T) {
			_, path, _, err := Route(command(tc.op, tc.args))
			if err != nil || path != tc.path {
				t.Fatalf("route: %s %v", path, err)
			}
		})
	}
	for _, tc := range []struct{ op, args string }{
		{"list_tasks", `{"status":""}`}, {"list_tasks", `{"sort":"random"}`}, {"list_tasks", `{"search":2}`},
		{"get_task", `{"task_id":"../vault"}`}, {"list_approvals", `{"after":-1}`},
		{"decide_approval", `{"id":"r","revision":0,"decision":"approve","note":"ok"}`},
		{"decide_approval", `{"id":"r","revision":1,"decision":"approve","note":"  "}`},
		{"decide_approval", `{"id":"r","revision":1,"decision":"approve","note":"ok","actor_id":"other"}`},
		{"approve", `{}`}, {"execute", `{}`}, {"list_tasks", `{"tenant_id":"other"}`}, {"list_tasks", `null`},
		{"latest_run", `{"task_id":"../../secrets"}`}, {"latest_run", `{}`},
		{"events", `{"run_id":"run_a","after":"run_b:1"}`}, {"events", `{"run_id":"run_a","after":3}`},
		{"events", `{"run_id":"run_a","after":"run_a:1\r\nX: y"}`},
		{"submit_task", `{"client_request_id":"r_1","title":"  ","instruction":"Do work"}`},
		{"submit_task", `{"client_request_id":"r_1","title":"x","instruction":false}`},
	} {
		if _, _, _, err := Route(command(tc.op, tc.args)); err == nil {
			t.Errorf("accepted %s %s", tc.op, tc.args)
		}
	}
}
func TestUnicodeAndRequestLimits(t *testing.T) {
	c := command("submit_task", `{"client_request_id":"r_1","title":"x","instruction":"x"}`)
	c.Args["title"], _ = json.Marshal(strings.Repeat("界", 200))
	if _, _, _, err := Route(c); err != nil {
		t.Fatal(err)
	}
	c.Args["title"], _ = json.Marshal(strings.Repeat("界", 201))
	if _, _, _, err := Route(c); err == nil {
		t.Fatal("accepted oversized title")
	}
}

func TestDocumentCommands(t *testing.T) {
	for _, tc := range []struct{ op, args, path string }{
		{"import_document", `{"request_id":"r","name":"a.csv","content":"YQ=="}`, "/v1/documents"},
		{"process_document", `{"id":"doc_a"}`, "/v1/documents/doc_a/process"},
		{"task_documents", `{"task_id":"task_a"}`, "/v1/tasks/task_a/documents"},
		{"resolve_citation", `{"citation":"doc_a:0"}`, "/v1/citations/doc_a:0"},
		{"list_results", `{"run_id":"run_a","after":0}`, "/v1/runs/run_a/results?after=0"},
	} {
		_, path, _, err := Route(command(tc.op, tc.args))
		if err != nil || path != tc.path {
			t.Fatalf("%s: %s %v", tc.op, path, err)
		}
	}
	for _, tc := range []struct{ op, args string }{
		{"import_document", `{"request_id":"r","name":"../a.csv","content":"YQ=="}`},
		{"import_document", `{"request_id":"r","name":"a.csv","content":"not base64"}`},
		{"get_document", `{"id":"../secret"}`},
		{"resolve_citation", `{"citation":"doc_a:../path"}`},
		{"submit_task", `{"client_request_id":"r","title":"t","instruction":"i","document_ids":["a","a"]}`},
	} {
		if _, _, _, err := Route(command(tc.op, tc.args)); err == nil {
			t.Fatalf("accepted %s", tc.op)
		}
	}
}

func TestProviderCommandsRemainExplicit(t *testing.T) {
	for _, tc := range []struct{ op, args, method, path string }{
		{"connections", `{}`, "GET", "/v1/connections"},
		{"check_connection", `{"config":{},"consent":false}`, "POST", "/v1/connections/check"},
		{"activate_connection", `{"fingerprints":["snapshot"]}`, "POST", "/v1/connections/activate"},
		{"save_credential", `{"reference":"vault:fixture","secret":"synthetic"}`, "POST", "/v1/connections/credential"},
		{"execute_run", `{"run_id":"run_a","expected_selection":["snapshot"],"allow_remote":false}`, "POST", "/v1/runs/run_a/execute"},
		{"cancel_run", `{"run_id":"run_a"}`, "POST", "/v1/runs/run_a/cancel"},
		{"document_chunks", `{"id":"doc_a","after":"20"}`, "GET", "/v1/documents/doc_a/chunks?after=20"},
	} {
		method, path, body, err := Route(command(tc.op, tc.args))
		if err != nil || method != tc.method || path != tc.path {
			t.Fatalf("route %s: %v", tc.op, err)
		}
		if tc.op == "execute_run" && strings.Contains(string(body), "run_id") {
			t.Fatal("run ID leaked into execute payload")
		}
	}
	for _, tc := range []struct{ op, args string }{
		{"read_credential", `{}`}, {"execute_run", `{"run_id":"../secrets"}`},
		{"execute_run", `{"run_id":"r","tenant_id":"other"}`},
		{"document_chunks", `{"id":"doc_a","after":2}`},
		{"document_chunks", `{"id":"doc_a","after":null}`},
		{"document_chunks", `{"id":"doc_a","after":"-1"}`},
		{"save_credential", `{"reference":"vault:a","secret":"synthetic","path":"/arbitrary"}`},
	} {
		if _, _, _, err := Route(command(tc.op, tc.args)); err == nil {
			t.Fatalf("accepted %s", tc.op)
		}
	}
}
