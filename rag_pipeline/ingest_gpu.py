#!/usr/bin/env python3
"""
GPU-accelerated ingestion pipeline for IBM Ceph documentation.

Runs once to create ChromaDB vector database from markdown files.
Optimized for RTX 5070 Ti (16 GB VRAM).
"""

import os
import sys
import time
import torch
from pathlib import Path
from typing import List, Dict, Any

import yaml
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from chunker import process_markdown_files, Chunk


# ─── GPU Setup ────────────────────────────────────────────────────────────

def setup_gpu() -> torch.device:
    """Configure GPU optimizations for RTX 5070 Ti."""
    if not torch.cuda.is_available():
        print("⚠️  CUDA not available, falling back to CPU")
        return torch.device("cpu")

    device = torch.device("cuda")
    gpu_name = torch.cuda.get_device_name(0)
    vram_total = torch.cuda.get_device_properties(0).total_memory / 1e9

    print(f"🚀 GPU: {gpu_name}")
    print(f"💾 VRAM: {vram_total:.1f} GB")

    # Enable optimizations for Ampere/Blackwell
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.cuda.empty_cache()

    return device


# ─── Custom GPU Embedding Function ────────────────────────────────────────

class GPUEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """ChromaDB embedding function using GPU-accelerated SentenceTransformer."""

    def __init__(
        self,
        model: SentenceTransformer,
        batch_size: int = 128,
        normalize: bool = True
    ):
        self.model = model
        self.batch_size = batch_size
        self.normalize = normalize

    def __call__(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []

        # Process in batches on GPU
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


# ─── Main Ingestion ───────────────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_embedding_model(config: dict, device: torch.device) -> SentenceTransformer:
    """Create and optimize embedding model for GPU."""
    emb_config = config["embeddings"]

    print(f"📦 Loading embedding model: {emb_config['model']}...")
    model = SentenceTransformer(emb_config["model"], device=str(device))

    if emb_config.get("fp16", True) and device.type == "cuda":
        model.half()  # FP16 for 2x speed
        print("✅ FP16 enabled")

    if emb_config.get("compile", True) and hasattr(torch, "compile"):
        try:
            model = torch.compile(model)
            print("✅ torch.compile enabled")
        except Exception as e:
            print(f"⚠️  torch.compile failed: {e}")

    return model


def create_chromadb_client(config: dict, embedding_fn) -> chromadb.Collection:
    """Create or get ChromaDB collection."""
    db_config = config["vectordb"]
    paths_config = config["paths"]

    client = chromadb.PersistentClient(path=paths_config["chroma_db"])

    collection = client.get_or_create_collection(
        name=paths_config["collection_name"],
        embedding_function=embedding_fn,
        metadata={
            "hnsw:space": db_config.get("hnsw_space", "cosine"),
            "hnsw:construction_ef": db_config.get("hnsw_construction_ef", 200),
            "hnsw:M": db_config.get("hnsw_M", 16)
        }
    )

    return collection


def ingest_documents(config: dict, collection, chunks: List[Chunk]) -> None:
    """Ingest chunks into ChromaDB in batches."""
    paths_config = config["paths"]
    batch_size = 100  # DB write batch size (different from embedding batch)

    print(f"\n💾 Ingesting {len(chunks)} chunks into ChromaDB...")

    start_time = time.time()
    for i in tqdm(range(0, len(chunks), batch_size), desc="Storing"):
        batch = chunks[i:i + batch_size]

        ids = [f"chunk_{i + j}" for j in range(len(batch))]
        documents = [c.text for c in batch]
        metadatas = [c.metadata for c in batch]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    elapsed = time.time() - start_time
    print(f"✅ Ingestion complete in {elapsed:.1f}s")


def print_stats(config: dict, chunks: List[Chunk], start_time: float) -> None:
    """Print ingestion statistics."""
    total_time = time.time() - start_time
    total_tokens = sum(c.token_count for c in chunks)

    # Chapter distribution
    chapters = {}
    content_types = {}
    for chunk in chunks:
        ch = chunk.metadata.get("chapter", "unknown")
        ct = chunk.metadata.get("content_type", "unknown")
        chapters[ch] = chapters.get(ch, 0) + 1
        content_types[ct] = content_types.get(ct, 0) + 1

    print("\n" + "=" * 60)
    print("📊 INGESTION STATISTICS")
    print("=" * 60)
    print(f"Total chunks:     {len(chunks):,}")
    print(f"Total tokens:     {total_tokens:,}")
    print(f"Avg tokens/chunk: {total_tokens // len(chunks):,}")
    print(f"Total time:       {total_time:.1f}s")
    print(f"Chunks/second:    {len(chunks) / total_time:.1f}")

    print(f"\n📚 By Chapter:")
    for ch, count in sorted(chapters.items()):
        print(f"  {ch}: {count:,}")

    print(f"\n📝 By Content Type:")
    for ct, count in sorted(content_types.items()):
        print(f"  {ct}: {count:,}")

    if torch.cuda.is_available():
        print(f"\n💾 Peak VRAM:     {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

    print(f"\n📁 Database:      {config['paths']['chroma_db']}")
    print(f"📦 Collection:    {config['paths']['collection_name']}")


def main():
    """Main ingestion pipeline."""
    print("=" * 60)
    print("🔧 IBM CEPH RAG — GPU INGESTION PIPELINE")
    print("=" * 60)

    overall_start = time.time()

    # 1. Load config
    config = load_config("config.yaml")
    print(f"📄 Config loaded")

    # 2. Setup GPU
    device = setup_gpu()

    # 3. Load embedding model
    model = create_embedding_model(config, device)

    # 4. Create embedding function
    emb_config = config["embeddings"]
    embedding_fn = GPUEmbeddingFunction(
        model=model,
        batch_size=emb_config.get("batch_size", 128),
        normalize=emb_config.get("normalize", True)
    )

    # 5. Create ChromaDB collection
    collection = create_chromadb_client(config, embedding_fn)
    print(f"🗄️  ChromaDB ready: {config['paths']['chroma_db']}")

    # 6. Process markdown files (chunking)
    print(f"\n✂️  Chunking documents...")
    chunk_start = time.time()

    md_root = Path(config["paths"]["md_root"])
    if not md_root.exists():
        print(f"❌ Markdown root not found: {md_root}")
        print(f"   Run the scraper first, or update config.yaml paths.md_root")
        sys.exit(1)

    chunk_config = config["chunking"]
    chunks = process_markdown_files(
        md_root,
        max_tokens=chunk_config["max_tokens"],
        overlap_tokens=chunk_config["overlap_tokens"],
        min_chunk_tokens=chunk_config["min_chunk_tokens"]
    )

    chunk_time = time.time() - chunk_start
    print(f"✅ Created {len(chunks)} chunks in {chunk_time:.1f}s")

    # 7. Ingest into ChromaDB
    ingest_documents(config, collection, chunks)

    # 8. Print statistics
    print_stats(config, chunks, overall_start)

    print("\n" + "=" * 60)
    print("🎉 INGESTION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  python query_gpu.py          # Test semantic search")
    print("  python query_rag.py          # Full RAG with LLM")
    print("  ollama pull llama3.1:8b-instruct-q4_K_M  # If using Ollama")


if __name__ == "__main__":
    main()