// The optional TLS team gateway is separate from the loopback desktop process.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"time"

	"veya/platform/internal/remoteauth"
)

type member struct{ Issuer, Subject, Tenant, Role string }

func run() error {
	for _, name := range []string{
		"VEYA_TEAM_ISSUER", "VEYA_TEAM_CLIENT_ID", "VEYA_TEAM_ORIGIN", "VEYA_TEAM_BACKEND",
		"VEYA_TEAM_GATEWAY_TOKEN", "VEYA_TEAM_MEMBERSHIPS", "VEYA_TEAM_TLS_CERT", "VEYA_TEAM_TLS_KEY",
	} {
		if os.Getenv(name) == "" {
			return errors.New("required team gateway configuration is missing")
		}
	}
	lookup := func(issuer, subject, tenant string) (remoteauth.Membership, bool) {
		// Read on every authorization so a reviewed membership change revokes access
		// without waiting for the session's expiry. The file is administrator-owned.
		path := os.Getenv("VEYA_TEAM_MEMBERSHIPS")
		info, err := os.Stat(path)
		if err != nil || !info.Mode().IsRegular() || info.Size() > 1048576 {
			return remoteauth.Membership{}, false
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return remoteauth.Membership{}, false
		}
		var members []member
		if json.Unmarshal(data, &members) != nil {
			return remoteauth.Membership{}, false
		}
		var match remoteauth.Membership
		count := 0
		for _, row := range members {
			if row.Issuer == issuer && row.Subject == subject && row.Tenant == tenant {
				match = remoteauth.Membership{Tenant: row.Tenant, Role: row.Role}
				count++
			}
		}
		return match, count == 1
	}
	origin := os.Getenv("VEYA_TEAM_ORIGIN")
	flow, err := remoteauth.NewLogin(context.Background(), os.Getenv("VEYA_TEAM_ISSUER"),
		os.Getenv("VEYA_TEAM_CLIENT_ID"), origin+"/auth/callback", lookup)
	if err != nil {
		return errors.New("identity provider could not be initialized")
	}
	gateway, err := remoteauth.NewGateway(flow, origin, os.Getenv("VEYA_TEAM_BACKEND"), os.Getenv("VEYA_TEAM_GATEWAY_TOKEN"))
	if err != nil {
		return err
	}
	address := os.Getenv("VEYA_TEAM_LISTEN")
	if address == "" {
		address = "127.0.0.1:8443"
	}
	server := &http.Server{Addr: address, Handler: gateway, ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second,
		MaxHeaderBytes: 16384,
	}
	return server.ListenAndServeTLS(os.Getenv("VEYA_TEAM_TLS_CERT"), os.Getenv("VEYA_TEAM_TLS_KEY"))
}

func main() {
	if err := run(); err != nil {
		log.Fatal("Team gateway stopped; verify configuration and dependencies")
	}
}
