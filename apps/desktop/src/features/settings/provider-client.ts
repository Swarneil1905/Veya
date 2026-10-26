import { call } from "../../workspace/client";
import { object } from "../documents/client";
export type Provider = {
  id: string;
  provider_id: string;
  model_name: string;
  profile: "local" | "remote";
  endpoint: string;
  credential_ref: string | null;
  capabilities: {
    tools: boolean;
    streaming: boolean;
    context_tokens: number;
    max_output_tokens: number;
  };
};
export type Connections = {
  profiles: {
    config: Provider;
    check: { fingerprint: string; checked_at: string };
  }[];
  active: Provider[];
  active_fingerprints: string[];
};
export async function connections(): Promise<Connections> {
  const v = object(await call("connections"));
  if (
    !Array.isArray(v["profiles"]) ||
    !Array.isArray(v["active"]) ||
    !Array.isArray(v["active_fingerprints"])
  )
    throw Error("invalid_response");
  for (const entry of v["profiles"]) {
    const row = object(entry);
    const check = object(row["check"]);
    if (typeof check["fingerprint"] !== "string")
      throw Error("invalid_response");
  }
  for (const row of [
    ...v["active"],
    ...v["profiles"].map((p: unknown) => object(p)["config"]),
  ]) {
    const item = object(row);
    if (
      !["id", "model_name", "endpoint", "profile"].every(
        (k) => typeof item[k] === "string",
      )
    )
      throw Error("invalid_response");
  }
  return v as Connections;
}
export function providerError(error: unknown) {
  const key = error instanceof Error ? error.message : "";
  const messages: Record<string, string> = {
    provider_transient:
      "The model did not respond in time. Check the server and try again.",
    model_missing: "That model is not available at this endpoint.",
    model_unsupported:
      "The model did not pass the streaming and tool-use check.",
    credential_missing: "Save a valid provider credential first.",
    vault_unavailable:
      "Credential storage requires Windows Credential Manager.",
    forbidden: "Check the endpoint and permission to send data.",
    invalid_input: "Check the connection fields and configured limits.",
    conflict: "The configuration changed. Refresh and test it again.",
    provider_required: "Test and activate a provider in Connection first.",
    model_unknown: "Configure the model context and output limits.",
    provider_rejected:
      "The provider rejected the request. Check the model and limits.",
  };
  return (
    messages[key] ??
    "Connection check failed. Your active provider is unchanged."
  );
}
