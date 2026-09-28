import type {
  ApiErrorBody,
  ComparisonResponse,
  CorpusStatus,
  GenerationStatus,
  GroundedAnswerResponse,
  SearchFilters,
  SourceDeletionResult,
  SourceListResponse,
  SourceUploadStatus,
} from "@/lib/types";

const API_URL =
  process.env.NEXT_PUBLIC_RACEVAULT_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class RaceVaultApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
    public readonly reason?: string,
  ) {
    super(message);
  }
}

function apiErrorReason(details: unknown): string | undefined {
  if (typeof details !== "object" || details === null || !("reason" in details)) {
    return undefined;
  }
  const reason = details.reason;
  return typeof reason === "string" && reason.length > 0 ? reason : undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new RaceVaultApiError(
      body.error?.message ?? "RaceVault could not complete the request.",
      body.error?.code ?? "request_failed",
      response.status,
      apiErrorReason(body.error?.details),
    );
  }
  return (await response.json()) as T;
}

export function getCorpusStatus(): Promise<CorpusStatus> {
  return request<CorpusStatus>("/v1/corpus/status");
}

export function getGenerationStatus(): Promise<GenerationStatus> {
  return request<GenerationStatus>("/v2/generation/status");
}

export function listSources(limit = 100): Promise<SourceListResponse> {
  return request<SourceListResponse>(`/v1/sources?limit=${limit}`);
}

export function uploadSource(
  file: File,
  documentType: string,
): Promise<SourceUploadStatus> {
  const body = new FormData();
  body.append("file", file);
  body.append("document_type", documentType);
  body.append("authority", "unknown");
  return request<SourceUploadStatus>("/v1/sources/uploads", {
    method: "POST",
    body,
  });
}

export function getSourceUpload(runId: string): Promise<SourceUploadStatus> {
  return request<SourceUploadStatus>(`/v1/sources/uploads/${runId}`);
}

export function deleteSource(
  sourceSha256: string,
): Promise<SourceDeletionResult> {
  return request<SourceDeletionResult>(`/v1/sources/${sourceSha256}`, {
    method: "DELETE",
  });
}


export async function generateGroundedAnswer(
  query: string,
  filters: SearchFilters,
  onDraft: (text: string) => void,
  signal?: AbortSignal,
): Promise<GroundedAnswerResponse> {
  const response = await fetch(`${API_URL}/v2/answers/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    signal,
    body: JSON.stringify({ query, filters }),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new RaceVaultApiError(
      body.error?.message ?? "RaceVault could not complete the request.",
      body.error?.code ?? "request_failed", response.status,
      apiErrorReason(body.error?.details),
    );
  }
  if (!response.body) throw new Error("The answer stream is unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart()).join("\n");
        if (!data) continue;
        const event = JSON.parse(data) as
          | { type: "draft"; text: string }
          | { type: "complete"; response: GroundedAnswerResponse }
          | { type: "error"; status: number; error: NonNullable<ApiErrorBody["error"]> };
        if (event.type === "draft") onDraft(event.text);
        if (event.type === "complete") return event.response;
        if (event.type === "error") {
          throw new RaceVaultApiError(
            event.error.message ?? "Answer generation failed.",
            event.error.code ?? "request_failed", event.status,
            apiErrorReason(event.error.details),
          );
        }
      }
      if (done) throw new Error("The answer stream ended before completion. Please retry.");
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function compareSources(
  query: string,
  leftSourceSha256: string,
  rightSourceSha256: string,
): Promise<ComparisonResponse> {
  return request<ComparisonResponse>("/v1/sources/compare", {
    method: "POST",
    body: JSON.stringify({
      query,
      left_source_sha256: leftSourceSha256,
      right_source_sha256: rightSourceSha256,
      result_limit: 5,
    }),
  });
}
