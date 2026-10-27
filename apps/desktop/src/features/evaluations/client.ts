import { call as command } from "../../workspace/client";
export type Summary = {
  id: string;
  title: string;
  source: "synthetic" | "model" | "mixed" | "unrecorded";
  count: number;
  status: string;
};
export type Page = { items: Summary[]; next_cursor: number | null };
export type Outcome = {
  id: string;
  case_id: string;
  family: string;
  candidate: string;
  repetition: number;
  status: string;
  source: string;
  duration_ms: number;
  tokens: number | null;
  cost_microunits: number | null;
  violations: number;
  evidence_ids: string[];
};
export type Report = {
  id: string;
  title: string;
  spec_hash: string;
  expected_ids: string[];
  expected_runs: { id: string; candidate: string; family: string }[];
  outcomes: Outcome[];
  baseline: string;
  candidate: string;
  interval: {
    status: string;
    delta: number | null;
    low: number | null;
    high: number | null;
    independent_units: number;
  };
};
export type Review = {
  revision: number;
  reviewer: string;
  decision: string;
  tags: string[];
  note: string;
  source_hash: string;
};
export type TraceView = {
  fingerprint: string;
  authorized: boolean;
  review: Review | null;
  history: Review[];
  trace: {
    id: string;
    case_id: string;
    source: string;
    family: string;
    split: string;
    source_ids: string[];
    events: {
      sequence: number;
      run_id: string;
      attempt: number;
      model_id: string;
      kind: string;
      operation: string | null;
      effect: string | null;
      content: string;
    }[];
  };
};
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw Error("invalid_response");
  return value as Record<string, unknown>;
}
export async function listing(
  kind: "evaluations" | "trajectories",
  after = 0,
): Promise<Page> {
  const value = object(await command("list_" + kind, { after }));
  if (
    !Array.isArray(value["items"]) ||
    !(value["next_cursor"] === null || typeof value["next_cursor"] === "number")
  )
    throw Error("invalid_response");
  return value as unknown as Page;
}
export async function report(id: string): Promise<Report> {
  const value = object(await command("get_evaluation", { id }));
  if (
    value["id"] !== id ||
    !Array.isArray(value["outcomes"]) ||
    !Array.isArray(value["expected_ids"]) ||
    !Array.isArray(value["expected_runs"]) ||
    !value["interval"]
  )
    throw Error("invalid_response");
  return value as unknown as Report;
}
export async function trajectory(id: string): Promise<TraceView> {
  return checkedTrace(await command("get_trajectory", { id }));
}
function checkedTrace(raw: unknown): TraceView {
  const value = object(raw),
    trace = object(value["trace"]);
  if (
    !Array.isArray(trace["events"]) ||
    !Array.isArray(value["history"]) ||
    typeof value["authorized"] !== "boolean" ||
    typeof value["fingerprint"] !== "string"
  )
    throw Error("invalid_response");
  return value as unknown as TraceView;
}
export async function reviewTrace(
  value: TraceView,
  decision: "approved" | "rejected",
  note: string,
  tags: string[],
): Promise<TraceView> {
  return checkedTrace(
    await command("review_trajectory", {
      id: value.trace.id,
      revision: value.review?.revision ?? 0,
      fingerprint: value.fingerprint,
      decision,
      tags,
      note,
    }),
  );
}
