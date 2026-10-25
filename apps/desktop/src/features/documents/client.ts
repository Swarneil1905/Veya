import { call } from "../../workspace/client";
export type Block = {
  locator: string;
  text: string;
  citation: string;
  value_type?: string | null;
};
export type Document = {
  id: string;
  name: string;
  kind: string;
  version: number;
  state: string;
  error: string;
  blocks: Block[];
  issues: { code: string; locator: string }[];
};
export type Citation = {
  available: boolean;
  citation: string;
  text: string;
  source: string;
  locator: string;
  version: number;
  reason: string;
};
export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid_response");
  return value as Record<string, unknown>;
}
export function document(value: unknown): Document {
  const v = object(value);
  if (
    !["id", "name", "kind", "state"].every((k) => typeof v[k] === "string") ||
    !Number.isInteger(v["version"])
  )
    throw new Error("invalid_response");
  const blocks = v["blocks"] ?? [],
    issues = v["issues"] ?? [];
  if (!Array.isArray(blocks) || !Array.isArray(issues))
    throw new Error("invalid_response");
  for (const raw of blocks) {
    const b = object(raw);
    if (!["locator", "text", "citation"].every((k) => typeof b[k] === "string"))
      throw new Error("invalid_response");
  }
  for (const raw of issues) {
    const b = object(raw);
    if (typeof b["code"] !== "string" || typeof b["locator"] !== "string")
      throw new Error("invalid_response");
  }
  return {
    ...v,
    blocks,
    issues,
    error: typeof v["error"] === "string" ? v["error"] : "",
  } as Document;
}
export async function getDocument(id: string, process = false) {
  return document(
    await call(process ? "process_document" : "get_document", { id }),
  );
}
export async function citation(id: string): Promise<Citation> {
  const v = object(await call("resolve_citation", { citation: id }));
  if (
    typeof v["available"] !== "boolean" ||
    !["citation", "text", "source", "locator", "reason"].every(
      (k) => typeof v[k] === "string",
    ) ||
    typeof v["version"] !== "number"
  )
    throw new Error("invalid_response");
  return v as Citation;
}
export function documentError(cause: unknown) {
  const code = cause instanceof Error ? cause.message : String(cause);
  return code === "invalid_input"
    ? "This file could not be imported. Choose a text PDF, UTF-8 CSV or safe XLSX workbook."
    : code === "too_large"
      ? "Choose a document up to 512 KiB."
      : code === "not_found"
        ? "Source access is unavailable. Remove it from this task."
        : code === "conflict"
          ? "This import conflicts with saved work. Reselect the document."
          : "Document access was interrupted. Retry when connected.";
}
export async function encoded(file: File) {
  if (!file.size || file.size > 524288) throw new Error("too_large");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let start = 0; start < bytes.length; start += 8192)
    binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
  return btoa(binary);
}
