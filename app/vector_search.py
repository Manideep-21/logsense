"""Semantic search over the documents stored in Qdrant.

Try it:  .venv/bin/python -m app.vector_search "disk failure took the site down"
         .venv/bin/python -m app.vector_search --source runbook "what does Could not read from stream mean"
"""
import argparse
from functools import lru_cache

from qdrant_client import QdrantClient, models

QDRANT_URL = "http://localhost:6333"
COLLECTION = "docs"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"   # small (90 MB), runs fine on CPU, 384 numbers per text


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer   # slow import, so only when needed
    return SentenceTransformer(MODEL_NAME, device="cpu")


@lru_cache(maxsize=1)
def get_client():
    return QdrantClient(url=QDRANT_URL)


def embed(texts):
    """Turn texts into vectors. normalize -> cosine similarity works as expected."""
    return get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)


def search(query, k=5, source=None):
    """Return the k documents closest in meaning to the query.

    source: None for everything, or "post-mortem" / "runbook" to search only one kind.
    Each result is a dict: score (0..1, higher = closer), title, source, category, url, text.
    """
    flt = None
    if source:
        flt = models.Filter(must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))])
    hits = get_client().query_points(COLLECTION, query=embed([query])[0].tolist(),
                                     query_filter=flt, limit=k, with_payload=True).points
    return [{"score": round(h.score, 3), **h.payload} for h in hits]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--source", choices=["post-mortem", "runbook"])
    args = ap.parse_args()
    for r in search(args.query, args.k, args.source):
        print(f"[{r['score']}] ({r['source']}) {r['title']}")
        print(f"    {r['text'][:200]}{'...' if len(r['text']) > 200 else ''}")
        if r.get("url"):
            print(f"    {r['url']}")


if __name__ == "__main__":
    main()
