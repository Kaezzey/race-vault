# PDF extraction

RaceVault uses Docling and PyMuPDF to create versioned extraction artifacts from
source PDFs.

## Output files

Each extraction writes two JSON files:

```text
.artifacts/extracted/<source-sha256>/pages-<start>-<end>-<config-id>/
  extraction.json
  docling.json
```

`extraction.json` contains normalized RaceVault records. `docling.json` contains
the lossless Docling document export.

The artifact path includes:

- the SHA-256 hash of the source PDF;
- the extracted page range;
- a hash of the extraction settings.

This allows artifacts from different source revisions, page ranges, or extractor
settings to exist at the same time.

## Artifact contents

The normalized artifact contains:

- source path, filename, size, SHA-256, and total page count;
- Docling, Docling Core, PyMuPDF, and RaceVault pipeline versions;
- the raw Docling JSON SHA-256;
- extraction settings;
- page dimensions, rotation, text, text hashes, and text blocks;
- document elements in reading order;
- headings and section paths;
- tables, cells, row and column spans, and header flags;
- page-numbered bounding-box provenance;
- validated summary counts.

Artifacts do not contain extraction timestamps. A repeated extraction with the
same source, software versions, page range, and settings can produce identical
JSON.

## Install extraction dependencies

```powershell
python -m pip install -e ".\backend[dev,extraction]"
```

Docling downloads its local layout and table models the first time it runs.

## Extract a manifest document

```powershell
python -m racevault.extraction.cli extract --role tyre_data
```

Extract part of a document:

```powershell
python -m racevault.extraction.cli extract `
  --role regulation_current `
  --page-start 1 `
  --page-end 10
```

Extract a corpus-relative path:

```powershell
python -m racevault.extraction.cli extract `
  --source "ECU/engine_control_unit_ms_6-x_manual.pdf"
```

Use `--force` to rerun an existing artifact. Otherwise, the command validates
and reuses the existing artifact.

## Validate an artifact

```powershell
python -m racevault.extraction.cli validate `
  ".artifacts/extracted/<source-sha256>/<configuration>/extraction.json" `
  --verify-source
```

Source verification recalculates the PDF SHA-256 and compares it with the
artifact.

## Extraction settings

| Option | Default | Description |
| --- | --- | --- |
| `--device` | `cpu` on Windows, `auto` elsewhere | Docling accelerator device |
| `--threads` | `8` | Docling worker threads |
| `--ocr` | Disabled | Enable OCR for scanned pages |
| `--no-tables` | Not set | Disable table structure extraction |
| `--compile-models` | Disabled | Enable PyTorch model compilation |

Native Windows uses CPU by default and disables model compilation. CUDA model
execution and model compilation require a compatible Linux or WSL2 environment.

## Validation rules

Artifact validation fails when:

- pages are missing, duplicated, or outside the configured page range;
- an element or table references a page outside the artifact;
- a table reference does not resolve;
- stable IDs are duplicated;
- summary statistics do not match the artifact;
- the raw Docling file is missing;
- source verification finds a different PDF hash.
