"""Ingest an ICAR PDF into the AgriMind local corpus or ChromaDB."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from rag.metadata import clean_text, extract_metadata


def extract_pdf_pages(pdf_path):
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
        if text.strip():
            yield page_no, text


def chunks(text, size=1800, overlap=250):
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind("\n", start + 1200, end)
            if cut > start:
                end = cut
        piece = clean_text(text[start:end])
        if piece:
            yield piece
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)


def ingest(pdf_path, persist_directory="rag/chroma", corpus_path="knowledge/icar_chunks.json"):
    from rag.retriever import KnowledgeRetriever

    docs, ids, metas = [], [], []
    stem = Path(pdf_path).stem
    for page_no, text in extract_pdf_pages(pdf_path):
        for cno, piece in enumerate(chunks(text), 1):
            docs.append(piece)
            ids.append(f"{stem}-p{page_no}-c{cno}")
            meta = extract_metadata(piece, page_no, cno)
            meta["source_document"] = Path(pdf_path).name
            metas.append(meta)

    retriever = KnowledgeRetriever(persist_directory, corpus_path)
    if retriever.collection is None and Path(corpus_path).exists():
        Path(corpus_path).unlink()
    retriever.add_documents(docs, ids, metas)
    return {
        "pages_with_text": len({m["source_page"] for m in metas}),
        "chunks": len(docs),
        "corpus_path": str(corpus_path),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--persist", default="rag/chroma")
    ap.add_argument("--corpus", default="knowledge/icar_chunks.json")
    a = ap.parse_args()
    print(json.dumps(ingest(a.pdf, a.persist, a.corpus), indent=2))
