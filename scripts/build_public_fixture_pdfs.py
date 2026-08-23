"""Build deterministic CC0 PDF fixtures without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPOSITORY_ROOT / "evaluation" / "public" / "fixture_sources.json"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream(title: str, lines: list[str]) -> bytes:
    commands = ["BT", "/F1 15 Tf", "72 740 Td", f"({_pdf_escape(title)}) Tj"]
    commands.extend(("/F1 11 Tf", "0 -28 Td"))
    for line in lines:
        commands.extend((f"({_pdf_escape(line)}) Tj", "0 -18 Td"))
    commands.append("ET")
    return ("\n".join(commands) + "\n").encode("ascii")


def build_pdf(title: str, pages: list[list[str]]) -> bytes:
    page_count = len(pages)
    page_object_ids = [3 + index * 2 for index in range(page_count)]
    font_object_id = 3 + page_count * 2
    kids = " ".join(f"{value} 0 R" for value in page_object_ids)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode(),
    ]
    for index, lines in enumerate(pages):
        page_id = page_object_ids[index]
        content_id = page_id + 1
        content = _stream(title, lines)
        objects.extend(
            (
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode(),
                b"<< /Length "
                + str(len(content)).encode()
                + b" >>\nstream\n"
                + content
                + b"endstream",
            )
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    payload = bytearray(b"%PDF-1.4\n%RaceVault\n")
    offsets = [0]
    for object_id, value in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{object_id} 0 obj\n".encode())
        payload.extend(value)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(payload)


def build_fixtures(source: Path, output: Path) -> dict[str, object]:
    definition = json.loads(source.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "license": definition["license"],
        "documents": [],
    }
    for document in definition["documents"]:
        payload = build_pdf(document["title"], document["pages"])
        target = output / document["filename"]
        target.write_bytes(payload)
        manifest["documents"].append(
            {
                "path": document["filename"],
                "title": document["title"],
                "sha256": hashlib.sha256(payload).hexdigest(),
                "license": definition["license"],
                "generated": True,
            }
        )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / ".artifacts" / "public-benchmark" / "corpus",
    )
    args = parser.parse_args(argv)
    manifest = build_fixtures(args.source, args.output)
    print(f"Built {len(manifest['documents'])} deterministic PDFs in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
