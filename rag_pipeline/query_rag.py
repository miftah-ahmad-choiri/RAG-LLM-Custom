#!/usr/bin/env python3
"""
Full RAG pipeline: Semantic search + LLM generation.

Supports: Ollama (local), OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude)
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
from llm_client import get_llm_client, load_config as load_llm_config


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


# ─── Search Function ─────────────────────────────────────────────────────

def search(
    collection,
    query: str,
    top_k: int = 5,
    chapter_filter: Optional[str] = None,
    content_type_filter: Optional[str] = None,
    topic_tags: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Execute vector search and return formatted results."""
    where = {}

    if chapter_filter:
        where["chapter"] = chapter_filter
    if content_type_filter:
        where["content_type"] = content_type_filter
    if topic_tags:
        where["topic_tags"] = {"$in": topic_tags}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where if where else None,
        include=["documents", "metadatas", "distances"]
    )

    # Format as list of dicts
    formatted = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        formatted.append({
            "text": doc,
            "metadata": meta,
            "score": 1 - dist,
            "distance": dist
        })

    return formatted


# ─── RAG Answer Generation ───────────────────────────────────────────────

def build_context(chunks: List[Dict[str, Any]]) -> str:
    """Build context string from retrieved chunks."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        source = meta.get("source_file", "unknown")
        section = meta.get("heading_path", "unknown")
        text = chunk["text"]
        context_parts.append(
            f"[Source {i}: {source} | {section}]\n{text}"
        )
    return "\n\n---\n\n".join(context_parts)


def build_prompt(question: str, context: str, config: dict) -> tuple[str, str]:
    """Build system prompt and user prompt from config template."""
    prompt_config = config.get("prompt", {})

    system = prompt_config.get("system", "You are an expert. Answer using the provided context.")
    template = prompt_config.get("template", "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")

    prompt = template.format(context=context, question=question)

    return system, prompt


def answer_question(
    question: str,
    llm_client,
    collection,
    config: dict,
    top_k: Optional[int] = None,
    chapter_filter: Optional[str] = None,
    content_type_filter: Optional[str] = None,
    topic_tags: Optional[List[str]] = None,
    show_sources: bool = True
) -> Dict[str, Any]:
    """
    Full RAG pipeline: retrieve + generate.

    Returns dict with answer, sources, and metadata.
    """
    retrieval_config = config["retrieval"]
    k = top_k or retrieval_config.get("top_k", 5)

    # 1. Retrieve relevant chunks
    chunks = search(
        collection,
        question,
        top_k=k,
        chapter_filter=chapter_filter,
        content_type_filter=content_type_filter,
        topic_tags=topic_tags
    )

    if not chunks:
        return {
            "answer": "No relevant documentation found for this query.",
            "sources": [],
            "chunks_retrieved": 0
        }

    # 2. Build context
    context = build_context(chunks)

    # 3. Build prompt
    system, prompt = build_prompt(question, context, config)

    # 4. Generate answer
    answer = llm_client.generate(prompt, system)

    return {
        "answer": answer,
        "sources": [
            {
                "file": c["metadata"].get("source_file"),
                "section": c["metadata"].get("heading_path"),
                "chapter": c["metadata"].get("chapter"),
                "content_type": c["metadata"].get("content_type"),
                "score": c["score"]
            }
            for c in chunks
        ],
        "chunks_retrieved": len(chunks),
        "context_used": context if show_sources else None
    }


def format_answer(result: Dict[str, Any], show_sources: bool = True) -> str:
    """Format RAG result for display."""
    output = []
    output.append("\n" + "=" * 60)
    output.append("🤖 ANSWER")
    output.append("=" * 60)
    output.append(result["answer"])

    if show_sources and result["sources"]:
        output.append("\n" + "-" * 60)
        output.append(f"📚 SOURCES ({result['chunks_retrieved']} chunks)")
        output.append("-" * 60)
        for i, src in enumerate(result["sources"], 1):
            output.append(f"\n{i}. {src['file']}")
            output.append(f"   Section: {src['section']}")
            output.append(f"   Chapter: {src['chapter']} | Type: {src['content_type']} | Score: {src['score']:.3f}")

    return "\n".join(output)


# ─── Interactive Mode ────────────────────────────────────────────────────

def interactive_rag(llm_client, collection, config: dict):
    """Interactive RAG loop."""
    retrieval_config = config["retrieval"]
    top_k = retrieval_config.get("top_k", 5)

    print("\n🤖 Interactive RAG — IBM Ceph Expert")
    print("Commands: :q quit | :k N top-k | :c chapter | :t type | :tags tag1,tag2 | :src on/off")
    print("-" * 60)

    current_filters = {
        "chapter": None,
        "content_type": None,
        "tags": None
    }
    show_sources = True

    while True:
        try:
            query = input("\n❓ Question> ").strip()
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
        elif query == ":src":
            show_sources = not show_sources
            print(f"✅ Show sources: {show_sources}")
            continue
        elif query == ":clear":
            current_filters = {"chapter": None, "content_type": None, "tags": None}
            print("✅ All filters cleared")
            continue
        elif query == ":help":
            print("Commands: :q quit | :k N top-k | :c chapter | :t type | :tags tag1,tag2 | :src | :clear")
            continue

        # Execute RAG
        print("🔍 Searching...")
        result = answer_question(
            query,
            llm_client,
            collection,
            config,
            top_k=top_k,
            chapter_filter=current_filters["chapter"],
            content_type_filter=current_filters["content_type"],
            topic_tags=current_filters["tags"],
            show_sources=show_sources
        )

        print(format_answer(result, show_sources))


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG Q&A for IBM Ceph docs")
    parser.add_argument("question", nargs="*", help="Question (optional, starts interactive mode)")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of chunks to retrieve")
    parser.add_argument("-c", "--chapter", help="Filter by chapter (e.g., 11-planning)")
    parser.add_argument("-t", "--type", help="Filter by content type (procedure/concept/reference/troubleshooting)")
    parser.add_argument("--tags", help="Filter by topic tags (comma-separated)")
    parser.add_argument("--no-sources", action="store_true", help="Don't show sources")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--stream", action="store_true", help="Stream answer tokens")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Create LLM client
    print(f"🤖 Loading LLM ({config['llm']['provider']}: {config['llm']['model']})...")
    llm_client = get_llm_client(config)

    # Setup embedding model
    print("🔧 Loading embedding model...")
    model = setup_embedding_model(config)

    embedding_fn = GPUEmbeddingFunction(
        model=model,
        batch_size=config["embeddings"].get("batch_size", 128),
        normalize=config["embeddings"].get("normalize", True)
    )

    # Connect to ChromaDB
    print("🗄️  Connecting to ChromaDB...")
    collection = connect_chromadb(config, embedding_fn)

    # Execute question or start interactive
    if args.question:
        question = " ".join(args.question)
        result = answer_question(
            question,
            llm_client,
            collection,
            config,
            top_k=args.top_k,
            chapter_filter=args.chapter,
            content_type_filter=args.type,
            topic_tags=args.tags.split(",") if args.tags else None,
            show_sources=not args.no_sources
        )
        print(format_answer(result, not args.no_sources))
    else:
        interactive_rag(llm_client, collection, config)


if __name__ == "__main__":
    main()