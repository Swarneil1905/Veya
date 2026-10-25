package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"time"

	"veya/platform/internal/server"
	"veya/platform/internal/worker"
)

func run() error {
	python := flag.String("python", "python", "Python executable with locked runtime dependencies")
	source := flag.String("runtime", "services/runtime", "Private Python runtime directory")
	assets := flag.String("assets", "", "Angular browser build directory (optional)")
	flag.Parse()
	input := bufio.NewReader(os.Stdin)
	line, err := input.ReadSlice('\n')
	if err != nil || len(line) > 4096 {
		return fmt.Errorf("bootstrap failed")
	}
	var config struct {
		Protocol int    `json:"protocol"`
		Storage  string `json:"storage_root"`
		Token    string `json:"session_token"`
	}
	if json.Unmarshal(line, &config) != nil || config.Protocol != 1 || len(config.Token) < 32 || len(config.Token) > 256 || !filepath.IsAbs(config.Storage) {
		return fmt.Errorf("invalid bootstrap")
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	go func() { _, _ = io.Copy(io.Discard, input); cancel() }() // Parent pipe closure also stops the private worker.
	process, err := worker.Start(ctx, *python, *source, config.Storage)
	if err != nil {
		return fmt.Errorf("private runtime failed to start")
	}
	defer process.Close()
	listener, err := server.Listen(config.Storage, *assets != "")
	if err != nil {
		return fmt.Errorf("platform bind failed")
	}
	defer listener.Close()
	handler, err := server.New(process, config.Token, listener.Addr().String(), *assets)
	if err != nil {
		return err
	}
	httpServer := &http.Server{Handler: handler, ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 12 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16384}
	failure := make(chan error, 1)
	go func() { failure <- httpServer.Serve(listener) }()
	if err = json.NewEncoder(os.Stdout).Encode(map[string]any{"status": "ready", "protocol": 1, "port": listener.Addr().(*net.TCPAddr).Port}); err != nil {
		return err
	}
	select {
	case <-ctx.Done():
	case <-process.Done():
	case <-failure:
	}
	shutdown, stop := context.WithTimeout(context.Background(), 2*time.Second)
	defer stop()
	_ = httpServer.Shutdown(shutdown)
	return nil
}

func main() {
	if run() != nil {
		fmt.Fprintln(os.Stderr, "Veya platform stopped: check the configured runtime and workspace.")
		os.Exit(1)
	}
}
