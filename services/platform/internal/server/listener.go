package server

import (
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Listen retains a web workspace's origin so localStorage drafts and immutable
// retry IDs survive process restarts. A busy saved port fails closed: silently
// selecting another origin would strand those drafts. Native IPC needs no origin.
func Listen(storage string, web bool) (net.Listener, error) {
	if !web {
		return net.Listen("tcp4", "127.0.0.1:0")
	}
	if err := os.MkdirAll(storage, 0700); err != nil {
		return nil, err
	}
	file := filepath.Join(storage, "platform-http-port")
	data, err := os.ReadFile(file)
	if err == nil {
		port, err := strconv.Atoi(strings.TrimSpace(string(data)))
		if err != nil || port < 1024 || port > 65535 {
			return nil, fmt.Errorf("invalid saved platform port")
		}
		return net.Listen("tcp4", "127.0.0.1:"+strconv.Itoa(port))
	}
	if !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	// Publish the complete file atomically without replacing another launch's port.
	tmp, err := os.CreateTemp(storage, ".platform-port-*")
	if err != nil {
		listener.Close()
		return nil, err
	}
	defer os.Remove(tmp.Name())
	_, err = fmt.Fprintln(tmp, listener.Addr().(*net.TCPAddr).Port)
	if err == nil {
		err = tmp.Sync()
	}
	closeErr := tmp.Close()
	if err == nil {
		err = closeErr
	}
	if err == nil {
		err = os.Link(tmp.Name(), file)
	}
	if err != nil {
		listener.Close()
		if errors.Is(err, os.ErrExist) {
			return Listen(storage, web)
		}
		return nil, err
	}
	return listener, nil
}
