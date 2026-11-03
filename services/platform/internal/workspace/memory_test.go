package workspace

import (
	"encoding/json"
	"testing"
)

func TestMemoryAndRetrievalCommands(t *testing.T) {
	for _, raw := range []string{
		`{"operation":"list_memories","args":{}}`,
		`{"operation":"propose_memory","args":{"run_id":"run_1"}}`,
		`{"operation":"review_memory","args":{"id":"mem_1","revision":1,"content":"Check this source first.","action":"activate"}}`,
		`{"operation":"erase_memory","args":{"id":"mem_1","revision":2}}`,
		`{"operation":"memory_evidence","args":{"run_id":"run_1"}}`,
		`{"operation":"index_document","args":{"id":"doc_1"}}`,
		`{"operation":"search_evidence","args":{"task_id":"task_1","query":"invoice amount","mode":"hybrid"}}`,
	} {
		var c Command
		if err := json.Unmarshal([]byte(raw), &c); err != nil {
			t.Fatal(err)
		}
		if _, _, _, err := Route(c); err != nil {
			t.Fatalf("%s: %v", c.Operation, err)
		}
	}
	for _, raw := range []string{
		`{"operation":"list_memories","args":{"owner":"someone_else"}}`,
		`{"operation":"propose_memory","args":{"run_id":"../other"}}`,
		`{"operation":"review_memory","args":{"id":"mem_1","revision":0,"content":"Check this source first.","action":"activate"}}`,
		`{"operation":"review_memory","args":{"id":"mem_1","revision":1,"content":"Check this source first.","action":"grant_tools"}}`,
		`{"operation":"search_evidence","args":{"task_id":"task_1","query":"invoice","mode":"all_tenants"}}`,
	} {
		var c Command
		if err := json.Unmarshal([]byte(raw), &c); err != nil {
			t.Fatal(err)
		}
		if _, _, _, err := Route(c); err == nil {
			t.Fatalf("unsafe command accepted: %s", raw)
		}
	}
}
