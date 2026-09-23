#!/usr/bin/env python3
"""
Semantic search CLI for IBM Ceph RAG — no LLM, just vector search.

Use this to test retrieval quality before adding LLM generation.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import torch

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from chunker import Chunk


# ─── GPU Embedding Function (Same as ingestion) ──────────────────────────

class GPUEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, model: SentenceTransformer, batch_size: int = 128, normalize: bool = True):
        self.model = model
        self.batch_size = batch_size
        self.normalize = normalize

    def __call__(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            with torch.inference_mode(), torch.cuda.amp.autocast(dtype=torch.float16):
                embeddings = self.model.encode(
                    batch,
                    batch_size=len(batch),
                    convert_to_tensor=True,
                    normalize_embeddings=self.normalize,
                    show_progress_bar=False
                )
            all_embeddings.extend(embeddings.cpu().numpy().tolist())
        return all_embeddings


# ─── Load Config & Setup ─────────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def setup_embedding_model(config: dict) -> SentenceTransformer:
    """Load embedding model with same settings as ingestion."""
    emb_config = config["embeddings"]
    device = "cuda" if torch.cuda.is_available() and emb_config.get("device") == "cuda" else "cpu"

    model = SentenceTransformer(emb_config["model"], device=device)

    if emb_config.get("fp16", True) and device == "cuda":
        model.half()

    if emb_config.get("compile", True) and hasattr(torch, "compile"):
        try:
            model = torch.compile(model)
        except Exception:
            pass

    return model


def connect_chromadb(config: dict, embedding_fn) -> chromadb.Collection:
    paths_config = config["paths"]
    client = chromadb.PersistentClient(path=paths_config["chroma_db"])
    return client.get_collection(
        name=paths_config["collection_name"],
        embedding_function=embedding_fn
    )


# ─── Search Functions ────────────────────────────────────────────────────

def search(
    collection,
    query: str,
    top_k: int = 5,
    chapter_filter: Optional[str] = None,
    content_type_filter: Optional[str] = None,
    topic_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute vector search with optional metadata filters."""
    where = {}

    if chapter_filter:
        where["chapter"] = chapter_filter
    if content_type_filter:
        where["content_type"] = content_type_filter
    if topic_tags:
        # ChromaDB $contains for array fields
        where["topic_tags"] = {"$in": topic_tags}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where if where else None,
        include=["documents", "metadatas", "distances"]
    )

    return results


def format_results(results: Dict[str, Any], show_text: bool = True, max_text_len: int = 400) -> str:
    """Format search results for display."""
    if not results["documents"][0]:
        return "No results found."

    output = []
    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    )):
        score = 1 - dist  # Convert distance to similarity
        output.append(f"\n{'='*60}")
        output.append(f"Result {i+1} | Score: {score:.4f}")
        output.append(f"{'='*60}")
        output.append(f"📄 File:      {meta.get('source_file', 'N/A')}")
        output.append(f"📚 Chapter:   {meta.get('chapter', 'N/A')}")
        output.append(f"🔖 Section:   {meta.get('section_number', 'N/A')}")
        output.append(f"📍 Path:      {meta.get('heading_path', 'N/A')}")
        output.append(f"🏷️  Type:      {meta.get('content_type', 'N/A')}")
        output.append(f"🏷️  Tags:      {', '.join(meta.get('topic_tags', [])) or 'none'}")

        if show_text:
            text = doc[:max_text_len] + ("..." if len(doc) > max_text_len else "")
            output.append(f"\n📝 Content:\n{text}")

    return "\n".join(output)


def interactive_search(collection, config: dict):
    """Interactive search loop."""
    retrieval_config = config["retrieval"]
    top_k = retrieval_config.get("top_k", 5)

    print("\n🔍 Interactive Semantic Search")
    print("Commands: :q quit | :k N top-k | :c chapter | :t type | :tags tag1,tag2")
    print("-" * 60)

    current_filters = {
        "chapter": None,
        "content_type": None,
        "tags": None
    }

    while True:
        try:
            query = input("\n🔍 Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not query:
            continue

        # Handle commands
        if query == ":q":
            print("👋 Goodbye!")
            break
        elif query.startswith(":k "):
            try:
                top_k = int(query[3:].strip())
                print(f"✅ top_k = {top_k}")
            except ValueError:
                print("❌ Usage: :k N")
            continue
        elif query.startswith(":c "):
            current_filters["chapter"] = query[3:].strip() or None
            print(f"✅ Chapter filter: {current_filters['chapter'] or 'off'}")
            continue
        elif query.startswith(":t "):
            current_filters["content_type"] = query[3:].strip() or None
            print(f"✅ Type filter: {current_filters['content_type'] or 'off'}")
            continue
        elif query.startswith(":tags "):
            tags = [t.strip() for t in query[6:].split(",")]
            current_filters["tags"] = tags if tags != [""] else None
            print(f"✅ Tag filter: {current_filters['tags'] or 'off'}")
            continue
        elif query == ":clear":
            current_filters = {"chapter": None, "content_type": None, "tags": None}
            print("✅ All filters cleared")
            continue
        elif query == ":help":
            print("Commands: :q quit | :k N top-k | :c chapter | :t type | :tags tag1,tag2 | :clear")
            continue

        # Execute search
        results = search(
            collection,
            query,
            top_k=top_k,
            chapter_filter=current_filters["chapter"],
            content_type_filter=current_filters["content_type"],
            topic_tags=current_filters["tags"]
        )

        print(format_results(results))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Semantic search for IBM Ceph docs")
    parser.add_argument("query", nargs="*", help="Search query (optional, starts interactive mode)")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("-c", "--chapter", help="Filter by chapter (e.g., 11-planning)")
    parser.add_argument("-t", "--type", help="Filter by content type (procedure/concept/reference/troubleshooting)")
    parser.add_argument("--tags", help="Filter by topic tags (comma-separated)")
    parser.add_argument("--no-text", action="store_true", help="Don't show document text")
    parser.add_argument("--config", default="config.yaml", help="Config file path")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup
    print("🔧 Loading embedding model...")
    model = setup_embedding_model(config)

    embedding_fn = GPUEmbeddingFunction(
        model=model,
        batch_size=config["embeddings"].get("batch_size", 128),
        normalize=config["embeddings"].get("normalize", True)
    )

    print("🗄️  Connecting to ChromaDB...")
    collection = connect_chromadb(config, embedding_fn)

    # Execute query or start interactive
    if args.query:
        query = " ".join(args.query)
        results = search(
            collection,
            query,
            top_k=args.top_k,
            chapter_filter=args.chapter,
            content_type_filter=args.type,
            topic_tags=args.tags.split(",") if args.tags else None
        )
        print(format_results(results, show_text=not args.no_text))
    else:
        interactive_search(collection, config)


if __name__ == "__main__":
    main()