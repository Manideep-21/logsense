"""Build the document list and load it into Qdrant (replaces the old collection).

Run:  .venv/bin/python -m app.index_docs

Sources:
  data/docs_download/post-mortems-README.md   one document per post-mortem entry
  docs/runbooks/*.md                          one document per runbook section
The parsed documents are also saved to data/documents.jsonl so you can read them.
"""
import json
import re
from pathlib import Path

from qdrant_client import models

from app.vector_search import COLLECTION, embed, get_client, get_model

README = Path("data/docs_download/post-mortems-README.md")
RUNBOOKS = Path("docs/runbooks")
OUT = Path("data/documents.jsonl")

# Only these README sections hold incident stories; the rest are lists of links.
SECTIONS = {"Config Errors", "Hardware/Power Failures", "Conflicts", "Time", "Database", "Uncategorized"}
ENTRY_RE = re.compile(r"^\[([^\]]+)\]\(([^)\s]+)\)\.?\s*(.*)", re.S)
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")   # [text](url) -> text


def post_mortems():
    docs, category = [], None
    for para in README.read_text(encoding="utf-8").split("\n\n"):
        para = para.strip()
        if para.startswith("## "):
            category = para[3:].strip()
            continue
        m = ENTRY_RE.match(para)
        if category in SECTIONS and m:
            company, url, text = m.groups()
            text = " ".join(LINK_RE.sub(r"\1", text).split())
            if text:
                docs.append({"source": "post-mortem", "title": company, "category": category,
                             "url": url, "text": text})
    return docs


def runbooks():
    """Split each runbook at '## ' headings; every piece starts with the runbook title.

    The embedding model only reads ~256 word-pieces, so short pieces embed better than whole files.
    """
    docs = []
    for path in sorted(RUNBOOKS.glob("*.md")):
        title, *rest = path.read_text(encoding="utf-8").split("\n", 1)
        title = title.lstrip("# ").strip()
        for i, part in enumerate(re.split(r"\n(?=## )", rest[0] if rest else "")):
            part = part.strip()
            if not part:
                continue
            heading = part.split("\n", 1)[0].lstrip("# ").strip() if part.startswith("## ") else "Overview"
            docs.append({"source": "runbook", "title": f"{title} - {heading}", "category": "HDFS runbook",
                         "url": str(path), "text": part})
    return docs


def main():
    docs = post_mortems() + runbooks()
    with OUT.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")
    n_pm = sum(d["source"] == "post-mortem" for d in docs)
    print(f"{n_pm} post-mortems + {len(docs) - n_pm} runbook sections -> {OUT}")

    # Embed "title + text" so the company / runbook name helps matching too.
    vectors = embed([f"{d['title']}. {d['text']}" for d in docs])

    client = get_client()
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(COLLECTION, vectors_config=models.VectorParams(
        size=get_model().get_sentence_embedding_dimension(), distance=models.Distance.COSINE))
    client.create_payload_index(COLLECTION, "source", models.PayloadSchemaType.KEYWORD)
    client.upsert(COLLECTION, points=[models.PointStruct(id=i, vector=v.tolist(), payload=d)
                                      for i, (d, v) in enumerate(zip(docs, vectors))])
    print(f"stored {client.count(COLLECTION).count} documents in Qdrant collection '{COLLECTION}'")


if __name__ == "__main__":
    main()
