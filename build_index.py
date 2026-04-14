"""build_index.py — Build ChromaDB index for Day 09 KB.

This script combines:
- Windows-safe text decoding
- Metadata parsing from document headers
- Section-aware chunking with overlap
- Environment-configurable Chroma collection setup

Usage:
    python build_index.py

Environment variables (optional, loaded from .env):
    CHROMA_DB_PATH=./chroma_db
    CHROMA_COLLECTION=day09_docs
    DATA_DOCS_DIR=./data/docs
    CHUNK_MAX_CHARS=1600
    CHUNK_OVERLAP_CHARS=320
    CHUNK_SIZE_TOKENS=400
    CHUNK_OVERLAP_TOKENS=80
    CHROMA_RESET_COLLECTION=1
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _read_text_robust(path: str) -> str:
    """Read text file robustly across Windows encodings.

    Tries utf-8/utf-8-sig first, then utf-16, then falls back to utf-8 with replacement.
    """
    with open(path, "rb") as f:
        raw = f.read()

    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _is_section_heading(line: str) -> bool:
    return bool(re.match(r"^===\s*.*?\s*===\s*$", line.strip()))


def _extract_metadata_and_body(raw_text: str, source_file: str) -> Tuple[Dict[str, Any], str]:
    """Extract structured metadata from header and return body text.

    Expected header keys (case-insensitive):
    - Source
    - Department
    - Effective Date
    - Access
    """
    text = _normalize_newlines(raw_text)
    lines = text.split("\n")

    metadata: Dict[str, Any] = {
        # Keep "source" as filename for compatibility with current retrieval/traces.
        "source": source_file,
        "source_file": source_file,
        # Preserve canonical/source-ref from file header if available.
        "source_ref": source_file,
        "department": "unknown",
        "effective_date": "unknown",
        "access": "internal",
    }

    body_lines: List[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()

        if not in_body:
            if _is_section_heading(stripped):
                in_body = True
                body_lines.append(stripped)
                continue

            match = re.match(r"^(Source|Department|Effective Date|Access)\s*:\s*(.*)$", line, flags=re.IGNORECASE)
            if match:
                key = match.group(1).strip().lower()
                value = match.group(2).strip()
                if key == "source":
                    metadata["source_ref"] = value or metadata["source_ref"]
                elif key == "department":
                    metadata["department"] = value or metadata["department"]
                elif key == "effective date":
                    metadata["effective_date"] = value or metadata["effective_date"]
                elif key == "access":
                    metadata["access"] = value or metadata["access"]
                continue

            # Ignore title/blank lines before first section heading.
            continue

        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not body:
        body = text.strip()

    body = re.sub(r"\n{3,}", "\n\n", body)
    return metadata, body


def _split_into_sections(text: str) -> List[Tuple[str, str]]:
    """Split document body into (section_name, section_text)."""
    text = _normalize_newlines(text).strip()
    if not text:
        return []

    parts = re.split(r"(?m)^(===\s*.*?\s*===)\s*$", text)

    sections: List[Tuple[str, str]] = []
    preamble = parts[0].strip() if parts else ""
    if preamble:
        sections.append(("General", preamble))

    for i in range(1, len(parts), 2):
        raw_heading = parts[i].strip()
        section_name = raw_heading.strip("=").strip() or "General"
        section_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if section_text:
            sections.append((section_name, section_text))

    if not sections:
        sections.append(("General", text))

    return sections


def _split_text_with_overlap(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    """Split long text by paragraphs, with trailing overlap from previous chunk."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        return []

    if len(text) <= max_chars:
        return [text.strip()]

    chunks: List[str] = []
    current_parts: List[str] = []
    current_len = 0
    overlap_prefix = ""

    for para in paragraphs:
        para_len = len(para) + (2 if current_parts else 0)

        # Hard-split very long paragraph.
        if len(para) > max_chars:
            if current_parts:
                current_body = "\n\n".join(current_parts)
                chunk_text = (overlap_prefix + "\n\n" if overlap_prefix else "") + current_body
                chunks.append(chunk_text.strip())
                overlap_prefix = current_body[-overlap_chars:] if overlap_chars > 0 else ""
                current_parts = []
                current_len = 0

            for i in range(0, len(para), max_chars):
                sub = para[i : i + max_chars].strip()
                if sub:
                    chunk_text = (overlap_prefix + "\n\n" if overlap_prefix else "") + sub
                    chunks.append(chunk_text.strip())
                    overlap_prefix = sub[-overlap_chars:] if overlap_chars > 0 else ""
            continue

        if current_len + para_len <= max_chars:
            current_parts.append(para)
            current_len += para_len
        else:
            current_body = "\n\n".join(current_parts)
            chunk_text = (overlap_prefix + "\n\n" if overlap_prefix else "") + current_body
            chunks.append(chunk_text.strip())
            overlap_prefix = current_body[-overlap_chars:] if overlap_chars > 0 else ""

            current_parts = [para]
            current_len = len(para)

    if current_parts:
        current_body = "\n\n".join(current_parts)
        chunk_text = (overlap_prefix + "\n\n" if overlap_prefix else "") + current_body
        chunks.append(chunk_text.strip())

    return chunks


def _chunk_document(raw_text: str, source_file: str, max_chars: int, overlap_chars: int) -> List[Tuple[str, Dict[str, Any]]]:
    """Convert one raw file into chunk tuples: (text, metadata)."""
    base_meta, body = _extract_metadata_and_body(raw_text, source_file=source_file)
    sections = _split_into_sections(body)

    all_chunks: List[Tuple[str, Dict[str, Any]]] = []
    for section_name, section_text in sections:
        section_chunks = _split_text_with_overlap(section_text, max_chars=max_chars, overlap_chars=overlap_chars)
        for chunk_text in section_chunks:
            chunk_meta = dict(base_meta)
            chunk_meta["section"] = section_name
            all_chunks.append((chunk_text, chunk_meta))

    return all_chunks


@dataclass
class DocChunk:
    doc_id: str
    text: str
    metadata: Dict[str, Any]


def _iter_doc_chunks(docs_dir: str, chunk_max_chars: int, chunk_overlap_chars: int) -> Iterable[DocChunk]:
    for fname in sorted(os.listdir(docs_dir)):
        fpath = os.path.join(docs_dir, fname)
        if not os.path.isfile(fpath):
            continue

        raw_text = _read_text_robust(fpath)
        chunk_tuples = _chunk_document(
            raw_text,
            source_file=fname,
            max_chars=chunk_max_chars,
            overlap_chars=chunk_overlap_chars,
        )

        stem = Path(fname).stem
        for idx, (chunk_text, chunk_meta) in enumerate(chunk_tuples):
            yield DocChunk(
                doc_id=f"{stem}:{idx:04d}",
                text=chunk_text,
                metadata=chunk_meta,
            )


def _env_int(name: str, default_value: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default_value
    try:
        return int(raw)
    except ValueError:
        return default_value


def _resolve_chunk_params() -> Tuple[int, int]:
    """Resolve chunk size and overlap with token-compatible fallbacks."""
    token_size = _env_int("CHUNK_SIZE_TOKENS", 400)
    token_overlap = _env_int("CHUNK_OVERLAP_TOKENS", 80)

    max_chars = _env_int("CHUNK_MAX_CHARS", token_size * 4)
    overlap_chars = _env_int("CHUNK_OVERLAP_CHARS", token_overlap * 4)

    # Safety guards
    max_chars = max(300, max_chars)
    overlap_chars = max(0, min(overlap_chars, max_chars // 2))
    return max_chars, overlap_chars


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()

    chroma_db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    collection_name = os.getenv("CHROMA_COLLECTION", "day09_docs")
    docs_dir = os.getenv("DATA_DOCS_DIR", "./data/docs")
    chunk_max_chars, chunk_overlap_chars = _resolve_chunk_params()
    reset_collection = _truthy_env("CHROMA_RESET_COLLECTION", True)

    if not os.path.isdir(docs_dir):
        raise SystemExit(f"Docs dir not found: {docs_dir}")

    # Embeddings (offline by default)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    import chromadb

    client = chromadb.PersistentClient(path=chroma_db_path)
    if reset_collection:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    col = client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"})

    doc_chunks = list(
        _iter_doc_chunks(
            docs_dir,
            chunk_max_chars=chunk_max_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        )
    )
    if not doc_chunks:
        raise SystemExit(f"No documents found under: {docs_dir}")

    texts = [c.text for c in doc_chunks]
    metadatas = [c.metadata for c in doc_chunks]
    ids = [c.doc_id for c in doc_chunks]

    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True).tolist()

    # Upsert so re-running is safe.
    col.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)

    # Quick summary
    sources = sorted({c.metadata.get("source", "unknown") for c in doc_chunks})
    departments = sorted({c.metadata.get("department", "unknown") for c in doc_chunks})
    sample_sections = sorted({c.metadata.get("section", "General") for c in doc_chunks})[:6]
    print("=" * 60)
    print("ChromaDB index built")
    print(f"DB path     : {chroma_db_path}")
    print(f"Collection  : {collection_name}")
    print(f"Docs dir    : {docs_dir}")
    print(f"Chunk chars : {chunk_max_chars} (overlap {chunk_overlap_chars})")
    print(f"Reset coll  : {reset_collection}")
    print(f"Sources     : {sources}")
    print(f"Departments : {departments}")
    print(f"Sections(s) : {sample_sections}")
    print(f"Total chunks: {len(doc_chunks)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
