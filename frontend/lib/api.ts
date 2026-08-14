import type {
  ApiErrorBody,
  ComparisonResponse,
  CorpusStatus,
  RetrievalResponse,
  SearchFilters,
  SourceListResponse,
} from "@/lib/types";

const API_URL =
  process.env.NEXT_PUBLIC_RACEVAULT_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class RaceVaultApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new RaceVaultApiError(
      body.error?.message ?? "RaceVault could not complete the request.",
      body.error?.code ?? "request_failed",
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function getCorpusStatus(): Promise<CorpusStatus> {
  return request<CorpusStatus>("/v1/corpus/status");
}

export function listSources(limit = 100): Promise<SourceListResponse> {
  return request<SourceListResponse>(`/v1/sources?limit=${limit}`);
}

export function searchEvidence(
  query: string,
  filters: SearchFilters,
): Promise<RetrievalResponse> {
  return request<RetrievalResponse>("/v1/retrieval/search", {
    method: "POST",
    body: JSON.stringify({
      query,
      filters,
      options: {
        channel_limit: 50,
        fusion_limit: 30,
        rerank_limit: 15,
        result_limit: 10,
      },
    }),
  });
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
