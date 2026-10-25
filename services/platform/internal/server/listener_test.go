package server

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWebOriginSurvivesRestartAndBusyPortFailsClosed(t *testing.T) {
	root := t.TempDir()
	first, err := Listen(root, true)
	if err != nil {
		t.Fatal(err)
	}
	address := first.Addr().String()
	if extra, err := Listen(root, true); err == nil {
		extra.Close()
		first.Close()
		t.Fatal("busy origin silently changed")
	}
	first.Close()
	second, err := Listen(root, true)
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	if second.Addr().String() != address {
		t.Fatal("browser origin changed")
	}
}

func TestInvalidSavedPortIsNotReplaced(t *testing.T) {
	root := t.TempDir()
	file := filepath.Join(root, "platform-http-port")
	for _, value := range []string{"", "80", "65536", "localhost:1234", "-1"} {
		if err := os.WriteFile(file, []byte(value), 0600); err != nil {
			t.Fatal(err)
		}
		if listener, err := Listen(root, true); err == nil {
			listener.Close()
			t.Fatal("invalid port accepted")
		}
		content, _ := os.ReadFile(file)
		if string(content) != value {
			t.Fatal("invalid port silently replaced")
		}
	}
}
