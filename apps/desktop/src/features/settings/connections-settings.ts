import { Component, Input, OnInit, signal } from "@angular/core";
import { call } from "../../workspace/client";
import {
  connections,
  Connections,
  Provider,
  providerError,
} from "./provider-client";
@Component({
  selector: "veya-connections-settings",
  template: ` <section
    class="work-provider-settings"
    aria-labelledby="provider-heading"
  >
    <h3 id="provider-heading">Model connections</h3>
    <p class="work-muted">
      Test a connection before using it. The active provider stays unchanged
      until you choose Use provider.
    </p>
    @if (loading()) {
      <p role="status">Loading providers…</p>
    }
    @if (state(); as s) {
      <p class="work-notice">
        Active order: {{ activeNames() || "No provider selected" }}
      </p>
      <ul class="work-provider-list">
        @for (row of s.profiles; track row.config.id) {
          <li>
            <div>
              <strong>{{ row.config.model_name }}</strong
              ><small
                >{{
                  row.config.profile === "local" ? "On this device" : "Hosted"
                }}
                · {{ row.config.id }}</small
              >
            </div>
            <div class="work-actions">
              <button
                class="work-secondary"
                [disabled]="disabled || pending()"
                (click)="edit(row.config)"
              >
                Edit {{ row.config.id }}</button
              ><button
                class="work-secondary"
                [disabled]="disabled || pending()"
                (click)="activate([row.check.fingerprint])"
              >
                Use provider {{ row.config.id }}</button
              ><button
                class="work-link-button"
                [disabled]="
                  disabled ||
                  pending() ||
                  s.active_fingerprints.length >= 3 ||
                  s.active_fingerprints.includes(row.check.fingerprint)
                "
                (click)="fallback(row.check.fingerprint)"
              >
                Add fallback {{ row.config.id }}
              </button>
            </div>
          </li>
        }
      </ul>
    }
    <form class="work-provider-form" (submit)="test($event)">
      <label for="provider-profile">Connection type</label
      ><select
        id="provider-profile"
        [value]="profile"
        [disabled]="disabled || pending()"
        (change)="setProfile($event)"
      >
        <option value="local">Local model server</option>
        <option value="remote">OpenAI hosted API</option>
      </select>
      <label for="provider-id">Connection name</label
      ><input
        id="provider-id"
        maxlength="64"
        pattern="[a-zA-Z0-9_-]+"
        required
        [value]="id"
        [disabled]="disabled || pending()"
        (input)="id = value($event)"
      />
      <label for="provider-endpoint">Endpoint</label
      ><input
        id="provider-endpoint"
        type="url"
        required
        [value]="endpoint"
        [readOnly]="profile === 'remote'"
        [disabled]="disabled || pending()"
        (input)="endpoint = value($event)"
      />
      <label for="provider-model">Installed model name</label
      ><input
        id="provider-model"
        required
        maxlength="200"
        [value]="model"
        [disabled]="disabled || pending()"
        (input)="model = value($event)"
      />
      <label for="provider-context">Model context limit (tokens)</label
      ><input
        id="provider-context"
        type="number"
        min="2048"
        max="1000000"
        required
        [value]="context"
        [disabled]="disabled || pending()"
        (input)="context = number($event)"
      />
      <p class="work-muted">
        Use the server's configured context limit. Each run allows up to 8
        cycles, 16 tool calls and 120 seconds. Token reservations are capped at
        65,536; this is not a currency spending limit.
      </p>
      @if (profile === "remote") {
        <label for="provider-key">API credential</label
        ><input
          id="provider-key"
          type="password"
          autocomplete="new-password"
          maxlength="2048"
          [value]="secret"
          [disabled]="disabled || pending()"
          (input)="secret = value($event)"
        />
        <button
          type="button"
          class="work-secondary"
          [disabled]="disabled || pending() || !secret || !id"
          (click)="saveCredential()"
        >
          Save credential in Windows vault
        </button>
        <p class="work-muted">
          The saved credential is never returned to this screen. Leave this
          field empty to use it again.
        </p>
        <label class="work-check-label"
          ><input
            type="checkbox"
            [checked]="consent"
            [disabled]="disabled || pending()"
            (change)="consent = checked($event)"
          />Allow a small synthetic connection test to OpenAI. Provider charges
          may apply.</label
        >
      }
      @if (error()) {
        <p id="provider-error" class="work-error" role="alert">{{ error() }}</p>
      }
      @if (notice()) {
        <p role="status">{{ notice() }}</p>
      }
      <button
        class="work-primary"
        type="submit"
        [disabled]="disabled || pending() || (profile === 'remote' && !consent)"
      >
        {{ pending() ? "Checking…" : "Test and save connection" }}
      </button>
    </form>
    <button class="work-link-button" [disabled]="pending()" (click)="load()">
      Refresh providers
    </button>
  </section>`,
})
export class ConnectionsSettings implements OnInit {
  @Input() disabled = false;
  readonly state = signal<Connections | null>(null);
  readonly loading = signal(false);
  readonly pending = signal(false);
  readonly error = signal("");
  readonly notice = signal("");
  profile: "local" | "remote" = "local";
  id = "local";
  endpoint = "http://127.0.0.1:1234/v1";
  model = "";
  context = 32768;
  secret = "";
  consent = false;
  ngOnInit() {
    void this.load();
  }
  value(event: Event) {
    return (event.target as HTMLInputElement).value;
  }
  number(event: Event) {
    return Number(this.value(event));
  }
  checked(event: Event) {
    return (event.target as HTMLInputElement).checked;
  }
  setProfile(event: Event) {
    this.profile = this.value(event) === "remote" ? "remote" : "local";
    this.endpoint =
      this.profile === "remote"
        ? "https://api.openai.com/v1"
        : "http://127.0.0.1:1234/v1";
    this.id = this.profile;
    this.secret = "";
    this.consent = false;
  }
  activeNames() {
    return this.state()
      ?.active.map((p) => p.model_name)
      .join(" → ");
  }
  edit(p: Provider) {
    this.profile = p.profile;
    this.id = p.id;
    this.model = p.model_name;
    this.endpoint = p.endpoint;
    this.context = p.capabilities.context_tokens;
    this.secret = "";
    this.consent = false;
  }
  async load() {
    this.loading.set(true);
    try {
      this.state.set(await connections());
    } catch (e) {
      this.error.set(providerError(e));
    } finally {
      this.loading.set(false);
    }
  }
  async perform(action: () => Promise<void>) {
    if (this.disabled || this.pending()) return;
    this.pending.set(true);
    this.error.set("");
    this.notice.set("");
    try {
      await action();
    } catch (e) {
      this.error.set(providerError(e));
    } finally {
      this.pending.set(false);
    }
  }
  async test(event: Event) {
    event.preventDefault();
    await this.perform(async () => {
      await call("check_connection", {
        config: {
          id: this.id,
          provider_id: this.profile,
          model_name: this.model,
          profile: this.profile,
          endpoint: this.endpoint,
          credential_ref: this.profile === "remote" ? "vault:" + this.id : null,
          capabilities: {
            tools: true,
            streaming: true,
            context_tokens: this.context,
            max_output_tokens: 1024,
          },
        },
        consent: this.consent,
      });
      this.notice.set("Connection passed. Choose Use provider to activate it.");
      await this.load();
    });
  }
  async saveCredential() {
    const secret = this.secret;
    this.secret = "";
    await this.perform(async () => {
      await call("save_credential", { reference: "vault:" + this.id, secret });
      this.notice.set("Credential saved in Windows Credential Manager.");
    });
  }
  async activate(fingerprints: string[]) {
    await this.perform(async () => {
      await call("activate_connection", { fingerprints });
      await this.load();
      this.notice.set(
        "Active provider order updated. Running tasks keep their original selection.",
      );
    });
  }
  fallback(fingerprint: string) {
    void this.activate([
      ...(this.state()?.active_fingerprints ?? []),
      fingerprint,
    ]);
  }
}
