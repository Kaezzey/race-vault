export type View = "search" | "sources" | "compare";

export interface SearchFilters {
  source_sha256?: string;
  source_role?: string;
  document_class?: string;
  authority?: string;
  vehicle_generation?: string;
  championship?: string;
  season?: number;
  revision?: string;
  page_number?: number;
  chunk_kind?: string;
  oversize?: boolean;
}

export interface BoundingBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  coordinate_origin: string;
}

export interface ProvenanceRef {
  page_number: number;
  bbox: BoundingBox;
  char_start: number | null;
  char_end: number | null;
}

export interface Citation {
  chunk_id: string;
  source_sha256: string;
  source_path: string;
  source_filename: string;
  page_start: number;
  page_end: number;
  page_numbers: number[];
  section_path: string[];
  clause_reference: string | null;
  evidence_sha256: string;
  element_ids: string[];
  table_ids: string[];
  provenance: ProvenanceRef[];
}

export interface RetrievalDiagnostics {
  lexical_rank: number | null;
  lexical_score: number | null;
  semantic_rank: number | null;
  semantic_score: number | null;
  fused_rank: number;
  rrf_score: number;
  reranker_score: number;
}

export interface RetrievalResult {
  rank: number;
  evidence_text: string;
  document_class: string;
  chunk_kind: string;
  source_role: string | null;
  source_metadata: Record<string, unknown>;
  citation: Citation;
  diagnostics: RetrievalDiagnostics;
}

export interface RetrievalResponse {
  query: string;
  filters: SearchFilters;
  counts: {
    lexical: number;
    semantic: number;
    fused: number;
    reranked: number;
  };
  embedding_model: { model_id: string; model_revision: string };
  reranker_model: { model_id: string; model_revision: string };
  results: RetrievalResult[];
}

export interface SourceSummary {
  source_sha256: string;
  source_path: string;
  filename: string;
  source_role: string | null;
  title: string | null;
  document_type: string;
  vehicle_generation: string | null;
  championship: string | null;
  season: number | null;
  revision: string | null;
  authority: string;
  language: string | null;
  page_count: number | null;
  extra_metadata: Record<string, unknown>;
  chunk_count: number;
  embedding_count: number;
}

export interface SourceListResponse {
  total: number;
  limit: number;
  offset: number;
  sources: SourceSummary[];
}

export interface CorpusStatus {
  documents: number;
  chunks: number;
  embeddings: number;
  embedded_documents: number;
  opensearch_chunks: number;
  consistent: boolean;
  embedding_model_id: string;
  embedding_model_revision: string;
}

export interface ComparisonResponse {
  query: string;
  left: RetrievalResponse;
  right: RetrievalResponse;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
}
