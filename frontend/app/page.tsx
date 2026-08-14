"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ChevronIcon,
  CloseIcon,
  CompareIcon,
  FileIcon,
  FilterIcon,
  LibraryIcon,
  SearchIcon,
  SendIcon,
  SlidersIcon,
} from "@/components/icons";
import {
  compareSources,
  getCorpusStatus,
  listSources,
  RaceVaultApiError,
  searchEvidence,
} from "@/lib/api";
import type {
  ComparisonResponse,
  CorpusStatus,
  RetrievalResponse,
  RetrievalResult,
  SearchFilters,
  SourceSummary,
  View,
} from "@/lib/types";

const SUGGESTIONS = [
  "How is brake balance adjusted?",
  "What is a Joker Tyre?",
  "Find the ABS M5 setup procedure",
  "What are the cold tyre pressure recommendations?",
];

function label(value: string | null | undefined): string {
  if (!value) return "Not specified";
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function sourceName(source: SourceSummary): string {
  return source.title || source.filename;
}

function shortHash(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function uniqueValues(
  sources: SourceSummary[],
  field: keyof SourceSummary,
): string[] {
  return Array.from(
    new Set(
      sources
        .map((source) => source[field])
        .filter((value): value is string | number =>
          typeof value === "string" || typeof value === "number",
        )
        .map(String),
    ),
  ).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

function MetadataPills({ result }: { result: RetrievalResult }) {
  const metadata = result.source_metadata;
  const values = [
    metadata.vehicle_generation,
    metadata.championship,
    metadata.season,
    metadata.revision,
  ].filter((value) => typeof value === "string" || typeof value === "number");

  return (
    <div className="metadata-pills">
      <span>{label(result.document_class)}</span>
      {values.map((value) => (
        <span key={String(value)}>{String(value)}</span>
      ))}
    </div>
  );
}

function EvidenceCard({
  result,
  selected,
  onSelect,
  side,
}: {
  result: RetrievalResult;
  selected?: boolean;
  onSelect?: () => void;
  side?: "left" | "right";
}) {
  const score = Math.round(result.diagnostics.reranker_score * 100);
  const className = `evidence-card ${selected ? "selected" : ""} ${side ?? ""}`;
  const content = (
    <>
      <div className="evidence-head">
        <span className="rank">{result.rank}</span>
        <div className="evidence-source">
          <strong>{result.citation.source_filename}</strong>
          <span>
            Page {result.citation.page_numbers.join(", ")}
            {result.citation.clause_reference
              ? ` · Clause ${result.citation.clause_reference}`
              : ""}
          </span>
        </div>
        <span className="score" title="Normalized reranker score">
          {score}%
        </span>
      </div>
      <p className="evidence-text">{result.evidence_text}</p>
      <div className="evidence-foot">
        <MetadataPills result={result} />
        {onSelect && (
          <span className="inspect-link">
            Inspect <ChevronIcon aria-hidden="true" />
          </span>
        )}
      </div>
    </>
  );
  if (!onSelect) {
    return <article className={className}>{content}</article>;
  }
  return (
    <button className={className} onClick={onSelect} type="button">
      {content}
    </button>
  );
}

function CitationInspector({ result }: { result: RetrievalResult | null }) {
  if (!result) {
    return (
      <aside className="inspector empty-inspector">
        <FileIcon aria-hidden="true" />
        <h2>Citation inspector</h2>
        <p>Select an evidence card to inspect its source and retrieval trace.</p>
      </aside>
    );
  }

  const citation = result.citation;
  const diagnostics = [
    ["BM25", result.diagnostics.lexical_rank, result.diagnostics.lexical_score],
    ["BGE-M3", result.diagnostics.semantic_rank, result.diagnostics.semantic_score],
    ["RRF", result.diagnostics.fused_rank, result.diagnostics.rrf_score],
    ["Reranker", result.rank, result.diagnostics.reranker_score],
  ] as const;

  return (
    <aside className="inspector">
      <div className="inspector-title">
        <div className="file-mark"><FileIcon aria-hidden="true" /></div>
        <div>
          <span>Selected evidence</span>
          <h2>{citation.source_filename}</h2>
        </div>
      </div>

      <dl className="citation-grid">
        <div><dt>Page</dt><dd>{citation.page_numbers.join(", ")}</dd></div>
        <div><dt>Kind</dt><dd>{label(result.chunk_kind)}</dd></div>
        <div className="wide">
          <dt>Section</dt>
          <dd>{citation.section_path.join(" / ") || "Not specified"}</dd>
        </div>
        {citation.clause_reference && (
          <div className="wide"><dt>Clause</dt><dd>{citation.clause_reference}</dd></div>
        )}
      </dl>

      <section className="trace-section">
        <h3>Retrieval trace</h3>
        {diagnostics.map(([name, rank, score]) => (
          <div className="trace-row" key={name}>
            <span>{name}</span>
            <div className="trace-bar">
              <i style={{ width: `${Math.max(4, (score ?? 0) * 100)}%` }} />
            </div>
            <b>{rank ? `#${rank}` : "—"}</b>
          </div>
        ))}
      </section>

      <section className="trace-section">
        <h3>Provenance</h3>
        <div className="provenance-line">
          <span>Source SHA-256</span><code>{shortHash(citation.source_sha256)}</code>
        </div>
        <div className="provenance-line">
          <span>Evidence SHA-256</span><code>{shortHash(citation.evidence_sha256)}</code>
        </div>
        <div className="provenance-line">
          <span>Chunk</span><code>{citation.chunk_id}</code>
        </div>
        <div className="provenance-line">
          <span>Page regions</span><code>{citation.provenance.length}</code>
        </div>
      </section>

      <div className="source-path">
        <span>Source path</span>
        <p>{citation.source_path}</p>
      </div>
    </aside>
  );
}

function FilterPanel({
  filters,
  sources,
  onChange,
  onClose,
}: {
  filters: SearchFilters;
  sources: SourceSummary[];
  onChange: (filters: SearchFilters) => void;
  onClose: () => void;
}) {
  const fields: Array<{
    key: keyof SearchFilters;
    title: string;
    sourceField: keyof SourceSummary;
  }> = [
    { key: "document_class", title: "Document type", sourceField: "document_type" },
    { key: "vehicle_generation", title: "Vehicle", sourceField: "vehicle_generation" },
    { key: "championship", title: "Championship", sourceField: "championship" },
    { key: "season", title: "Season", sourceField: "season" },
    { key: "revision", title: "Revision", sourceField: "revision" },
    { key: "authority", title: "Authority", sourceField: "authority" },
  ];

  return (
    <div className="filter-panel">
      <div className="panel-heading">
        <div><span>Search scope</span><h2>Metadata filters</h2></div>
        <button aria-label="Close filters" className="icon-button" onClick={onClose} type="button">
          <CloseIcon aria-hidden="true" />
        </button>
      </div>
      <p>Filters run in BM25 and BGE-M3 before result fusion.</p>
      <div className="filter-fields">
        {fields.map((field) => (
          <label key={field.key}>
            {field.title}
            <select
              value={filters[field.key] == null ? "" : String(filters[field.key])}
              onChange={(event) => {
                const value = event.target.value;
                const next = { ...filters };
                if (!value) delete next[field.key];
                else if (field.key === "season") next.season = Number(value);
                else Object.assign(next, { [field.key]: value });
                onChange(next);
              }}
            >
              <option value="">All</option>
              {uniqueValues(sources, field.sourceField).map((value) => (
                <option key={value} value={value}>{label(value)}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <button className="clear-button" onClick={() => onChange({})} type="button">
        Clear all filters
      </button>
    </div>
  );
}

function SourcesView({ sources }: { sources: SourceSummary[] }) {
  const [term, setTerm] = useState("");
  const visible = sources.filter((source) =>
    [sourceName(source), source.document_type, source.vehicle_generation, source.revision]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(term.toLowerCase()),
  );

  return (
    <main className="catalog-view">
      <header className="view-header">
        <div><span>Corpus catalogue</span><h1>Sources</h1></div>
        <div className="catalog-search">
          <SearchIcon aria-hidden="true" />
          <input
            aria-label="Filter sources"
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Filter by title, type, vehicle, or revision"
            value={term}
          />
        </div>
      </header>
      <div className="catalog-summary">
        Showing <strong>{visible.length}</strong> of {sources.length} loaded sources
      </div>
      <div className="source-list">
        {visible.map((source) => {
          const coverage = source.chunk_count
            ? Math.round((source.embedding_count / source.chunk_count) * 100)
            : 0;
          return (
            <article className="source-row" key={source.source_sha256}>
              <div className="source-file-icon"><FileIcon aria-hidden="true" /></div>
              <div className="source-main">
                <h2>{sourceName(source)}</h2>
                <div className="source-meta">
                  <span>{label(source.document_type)}</span>
                  {source.vehicle_generation && <span>{source.vehicle_generation}</span>}
                  {source.season && <span>{source.season}</span>}
                  {source.revision && <span>{source.revision}</span>}
                </div>
              </div>
              <div className="source-stat"><strong>{source.page_count ?? "—"}</strong><span>pages</span></div>
              <div className="source-stat"><strong>{source.chunk_count}</strong><span>chunks</span></div>
              <div className="coverage">
                <div><span>Vector coverage</span><b>{coverage}%</b></div>
                <i><em style={{ width: `${coverage}%` }} /></i>
              </div>
              <code>{shortHash(source.source_sha256)}</code>
            </article>
          );
        })}
      </div>
    </main>
  );
}

function CompareView({ sources }: { sources: SourceSummary[] }) {
  const [query, setQuery] = useState("How is brake balance adjusted?");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [response, setResponse] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defaultLeft =
    sources.find(
      (source) =>
        source.document_type === "technical_manual" &&
        source.vehicle_generation === "992.1",
    )?.source_sha256 || sources[0]?.source_sha256 || "";
  const selectedLeft = left || defaultLeft;
  const selectedRight =
    right ||
    sources.find(
      (source) =>
        source.source_sha256 !== selectedLeft &&
        source.document_type === "technical_manual" &&
        source.vehicle_generation === "992.2",
    )?.source_sha256 ||
    sources.find((source) => source.source_sha256 !== selectedLeft)?.source_sha256 ||
    "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (
      !query.trim() ||
      !selectedLeft ||
      !selectedRight ||
      selectedLeft === selectedRight
    ) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(
        await compareSources(query.trim(), selectedLeft, selectedRight),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="compare-view">
      <header className="view-header">
        <div><span>Source-scoped retrieval</span><h1>Compare documents</h1></div>
        <p>Run the same question against two sources without mixing their evidence.</p>
      </header>
      <form className="compare-form" onSubmit={submit}>
        <div className="source-select left-select">
          <label htmlFor="left-source">Source A</label>
          <select id="left-source" onChange={(e) => setLeft(e.target.value)} value={selectedLeft}>
            {sources.map((source) => (
              <option disabled={source.source_sha256 === selectedRight} key={source.source_sha256} value={source.source_sha256}>
                {sourceName(source)}
              </option>
            ))}
          </select>
        </div>
        <div className="source-select right-select">
          <label htmlFor="right-source">Source B</label>
          <select id="right-source" onChange={(e) => setRight(e.target.value)} value={selectedRight}>
            {sources.map((source) => (
              <option disabled={source.source_sha256 === selectedLeft} key={source.source_sha256} value={source.source_sha256}>
                {sourceName(source)}
              </option>
            ))}
          </select>
        </div>
        <div className="compare-query">
          <SearchIcon aria-hidden="true" />
          <input aria-label="Comparison question" onChange={(e) => setQuery(e.target.value)} value={query} />
          <button disabled={loading || selectedLeft === selectedRight} type="submit">
            {loading ? "Comparing…" : "Compare"}
          </button>
        </div>
      </form>
      {error && <div className="error-banner">{error}</div>}
      {!response && !loading && (
        <div className="compare-empty">
          <CompareIcon aria-hidden="true" />
          <h2>Compare evidence, not summaries</h2>
          <p>Select two manuals, revisions, or regulations and ask one focused question.</p>
        </div>
      )}
      {response && (
        <div className="comparison-grid">
          <section>
            <div className="comparison-heading left-heading">
              <span>A</span><div><strong>{response.left.results[0]?.citation.source_filename || "Source A"}</strong><small>{response.left.results.length} results</small></div>
            </div>
            {response.left.results.map((result) => <EvidenceCard key={result.citation.chunk_id} result={result} side="left" />)}
          </section>
          <section>
            <div className="comparison-heading right-heading">
              <span>B</span><div><strong>{response.right.results[0]?.citation.source_filename || "Source B"}</strong><small>{response.right.results.length} results</small></div>
            </div>
            {response.right.results.map((result) => <EvidenceCard key={result.citation.chunk_id} result={result} side="right" />)}
          </section>
        </div>
      )}
    </main>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("search");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [response, setResponse] = useState<RetrievalResponse | null>(null);
  const [selected, setSelected] = useState<RetrievalResult | null>(null);
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getCorpusStatus(), listSources()])
      .then(([status, sourceList]) => {
        if (!active) return;
        setCorpus(status);
        setSources(sourceList.sources);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "The API is unavailable.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [view]);

  const filterCount = Object.keys(filters).length;
  const statusText = corpus?.consistent ? "Corpus ready" : corpus ? "Check corpus" : "Connecting";
  const activeFilterLabels = useMemo(
    () => Object.entries(filters).map(([key, value]) => `${label(key)}: ${label(String(value))}`),
    [filters],
  );

  async function runSearch(searchQuery: string) {
    const normalized = searchQuery.trim();
    if (!normalized || loading) return;
    setView("search");
    setQuery(normalized);
    setLoading(true);
    setError(null);
    try {
      const result = await searchEvidence(normalized, filters);
      setResponse(result);
      setSelected(result.results[0] ?? null);
      setRecent((items) => [normalized, ...items.filter((item) => item !== normalized)].slice(0, 5));
    } catch (caught) {
      const message = caught instanceof RaceVaultApiError
        ? `${caught.message} (${caught.code})`
        : caught instanceof Error ? caught.message : "Search failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void runSearch(query);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView("search")} type="button">
          <span>RV</span><strong>RaceVault</strong>
        </button>
        <button className="new-search" onClick={() => { setView("search"); setResponse(null); setSelected(null); setQuery(""); }} type="button">
          <SearchIcon aria-hidden="true" /> New search
        </button>
        <nav aria-label="Primary navigation">
          <button className={view === "search" ? "active" : ""} onClick={() => setView("search")} type="button">
            <SearchIcon aria-hidden="true" /> Search
          </button>
          <button className={view === "sources" ? "active" : ""} onClick={() => setView("sources")} type="button">
            <LibraryIcon aria-hidden="true" /> Sources
          </button>
          <button className={view === "compare" ? "active" : ""} onClick={() => setView("compare")} type="button">
            <CompareIcon aria-hidden="true" /> Compare
          </button>
        </nav>
        {recent.length > 0 && (
          <div className="recent-list">
            <span>Recent</span>
            {recent.map((item) => (
              <button key={item} onClick={() => void runSearch(item)} title={item} type="button">{item}</button>
            ))}
          </div>
        )}
        <div className="sidebar-status">
          <i className={corpus?.consistent ? "ok" : ""} />
          <div><strong>{statusText}</strong><span>{corpus ? `${corpus.documents} sources · ${corpus.chunks.toLocaleString()} chunks` : "Checking local services"}</span></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><span>RV</span><strong>RaceVault</strong></div>
          <div className="scope-label"><i /> Local engineering corpus</div>
          <button className="filter-button" onClick={() => setShowFilters(true)} type="button">
            <SlidersIcon aria-hidden="true" /> Filters {filterCount > 0 && <b>{filterCount}</b>}
          </button>
        </header>

        {view === "sources" && <SourcesView sources={sources} />}
        {view === "compare" && <CompareView sources={sources} />}
        {view === "search" && (
          <div className="content-shell">
            <main className={`conversation ${response ? "has-results" : ""}`}>
              {!response && !loading && (
                <div className="welcome">
                  <div className="welcome-mark">RV</div>
                  <h1>What do you need to verify?</h1>
                  <p>Search manuals, regulations, tyre data, catalogues, and engineering references. Every result links back to exact source evidence.</p>
                  <div className="suggestions">
                    {SUGGESTIONS.map((suggestion) => (
                      <button key={suggestion} onClick={() => void runSearch(suggestion)} type="button">
                        <span>{suggestion}</span><ChevronIcon aria-hidden="true" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {response && (
                <div className="results-thread">
                  <div className="user-query"><p>{response.query}</p><span>You</span></div>
                  <div className="result-intro">
                    <div className="assistant-mark">RV</div>
                    <div>
                      <h1>Found {response.results.length} evidence passages</h1>
                      <p>Ranked from {response.counts.fused} fused candidates. Open a result to inspect its citation and retrieval trace.</p>
                    </div>
                  </div>
                  {activeFilterLabels.length > 0 && (
                    <div className="active-filters">
                      <FilterIcon aria-hidden="true" />
                      {activeFilterLabels.map((item) => <span key={item}>{item}</span>)}
                    </div>
                  )}
                  <div className="evidence-list">
                    {response.results.map((result) => (
                      <EvidenceCard
                        key={result.citation.chunk_id}
                        onSelect={() => setSelected(result)}
                        result={result}
                        selected={selected?.citation.chunk_id === result.citation.chunk_id}
                      />
                    ))}
                  </div>
                </div>
              )}

              {loading && (
                <div className="loading-state">
                  <div className="spinner" />
                  <div><strong>Searching the corpus</strong><span>BM25 · BGE-M3 · RRF · reranker</span></div>
                </div>
              )}
              {error && <div className="error-banner">{error}</div>}

              <div className="composer-wrap">
                <form className="composer" onSubmit={submit}>
                  <textarea
                    aria-label="Engineering question"
                    onChange={(event) => setQuery(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void runSearch(query);
                      }
                    }}
                    placeholder="Ask about a procedure, rule, component, or setup…"
                    rows={2}
                    value={query}
                  />
                  <div className="composer-actions">
                    <button className="composer-filter" onClick={() => setShowFilters(true)} type="button">
                      <FilterIcon aria-hidden="true" />
                      {filterCount ? `${filterCount} filters` : "Add filters"}
                    </button>
                    <button aria-label="Search" className="send-button" disabled={!query.trim() || loading} type="submit">
                      <SendIcon aria-hidden="true" />
                    </button>
                  </div>
                </form>
                <p>RaceVault retrieves source evidence. Verify technical decisions in the original document.</p>
              </div>
            </main>
            <CitationInspector result={selected} />
          </div>
        )}
      </section>

      {showFilters && (
        <div className="panel-overlay" onMouseDown={(event) => { if (event.currentTarget === event.target) setShowFilters(false); }}>
          <FilterPanel filters={filters} onChange={setFilters} onClose={() => setShowFilters(false)} sources={sources} />
        </div>
      )}
    </div>
  );
}
