# IBM Storage Ceph RAG Pipeline

GPU-accelerated Retrieval-Augmented Generation pipeline for IBM Storage Ceph 9.9.1 documentation.

## Features

- **Ceph-aware hierarchical chunking** — Preserves document structure (chapters, sections, headings)
- **GPU-optimized embeddings** — BGE-large on RTX 5070 Ti (FP16, torch.compile, batch=128)
- **Rich metadata** — Topic tags, content types, chapter/section tracking
- **Swappable LLM backends** — Ollama (free/local), OpenAI (GPT-4o/mini), Anthropic (Claude)
- **Evaluation harness** — Automated quality testing with ground truth

## Quick Start

### 1. Prerequisites

```bash
# Python 3.10+
# NVIDIA GPU with CUDA (RTX 5070 Ti recommended)
# Or CPU fallback works too
```

### 2. Install Dependencies

```bash
cd rag-pipeline
pip install -r requirements.txt
```

### 3. Install Ollama (for free local LLM)

```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download

# Pull model (5.5 GB VRAM)
ollama pull llama3.1:8b-instruct-q4_K_M

# Start Ollama server
ollama serve
```

### 4. Run Ingestion (One-time, ~30 seconds)

```bash
# Ensure scraper has completed first!
# MD files should be at: ceph-scraper/output/md/20260922_234455-IBM-Ceph-TOC-20260922_231027/

python ingest_gpu.py
```

Output:
```
🚀 GPU: NVIDIA GeForce RTX 5070 Ti
💾 VRAM: 16.0 GB
📦 Loading embedding model: BAAI/bge-large-en-v1.5...
✅ FP16 enabled
✅ torch.compile enabled
✂️  Chunking documents...
✅ Created 4,847 chunks in 3.2s
💾 Ingesting 4,847 chunks into ChromaDB...
✅ Ingestion complete in 8.5s

📊 INGESTION STATISTICS
Total chunks:     4,847
Total tokens:     1,234,567
Avg tokens/chunk: 254
Total time:       11.7s
```

### 5. Test Retrieval (No LLM)

```bash
# Single query
python query_gpu.py "how to set device class for ssd osd"

# Interactive mode with filters
python query_gpu.py
# Commands: :k 10 | :c 11-planning | :t procedure | :tags crush,osd
```

### 6. Full RAG with LLM

```bash
# Using Ollama (free, local)
python query_rag.py "how to create erasure coded pool"

# Using GPT-4o-mini (cheap, fast) - edit config.yaml first
python query_rag.py "why are my PGs degraded?"

# Interactive RAG
python query_rag.py
# Commands: :k 5 | :c 13-upgrading | :src (toggle sources)
```

## Configuration

Edit `config.yaml` to customize:

```yaml
paths:
  md_root: "ceph-scraper/output/md/20260922_234455-IBM-Ceph-TOC-20260922_231027"
  chroma_db: "./chroma_db"
  collection_name: "ibm_ceph_docs"

llm:
  # Option 1: Ollama (FREE, local)
  provider: "ollama"
  model: "llama3.1:8b-instruct-q4_K_M"
  base_url: "http://localhost:11434"

  # Option 2: GPT-4o-mini (CHEAP) - uncomment
  # provider: "openai"
  # model: "gpt-4o-mini"
  # api_key: "${OPENAI_API_KEY}"

  # Option 3: GPT-4o (BEST) - uncomment
  # provider: "openai"
  # model: "gpt-4o"
  # api_key: "${OPENAI_API_KEY}"
```

For OpenAI: `export OPENAI_API_KEY="sk-..."`

## Model Options (RTX 5070 Ti 16 GB)

| Model | VRAM | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `llama3.1:8b-instruct-q4_K_M` | 5.5 GB | ~80 tok/s | ⭐⭐⭐⭐ | Default, balanced |
| `qwen2.5:7b-instruct-q4_K_M` | 4.8 GB | ~90 tok/s | ⭐⭐⭐⭐ | Code/config tasks |
| `nemotron-3-ultra` | 10 GB | ~40 tok/s | ⭐⭐⭐⭐⭐ | Complex reasoning |
| `phi3.5:mini` | 2.5 GB | ~120 tok/s | ⭐⭐⭐ | Speed/edge |

Pull with: `ollama pull <model-name>`

## Project Structure

```
rag-pipeline/
├── config.yaml           # All configuration
├── requirements.txt      # Python dependencies
├── chunker.py           # Ceph-aware hierarchical chunking
├── llm_client.py        # Unified LLM client (Ollama/OpenAI/Anthropic)
├── ingest_gpu.py        # One-time ingestion (run once)
├── query_gpu.py         # Semantic search only (test retrieval)
├── query_rag.py         # Full RAG: search + LLM answer
├── eval.py              # Quality evaluation harness
└── README.md            # This file
```

## Usage Examples

### Search with Filters

```bash
# Only procedures from planning chapter
python query_gpu.py -c 11-planning -t procedure "crush rule"

# Only troubleshooting from administering
python query_gpu.py -c 16-administering -t troubleshooting "osd down"

# Filter by topic tags
python query_gpu.py --tags crush,device-class,ssd "device class"
```

### RAG with Custom Parameters

```bash
# More context chunks
python query_rag.py -k 8 "design crush hierarchy"

# Chapter-specific
python query_rag.py -c 12-installing "bootstrap cluster"

# Type-specific
python query_rag.py -t procedure "add osd to cluster"
```

### Evaluation

```bash
# Run full evaluation suite
python eval.py

# Only procedures
python eval.py --category procedure

# Only hard questions
python eval.py --difficulty hard

# Custom thresholds
python eval.py --keyword-threshold 0.6 --chapter-threshold 0.5
```

## Interactive Commands

Both `query_gpu.py` and `query_rag.py` support interactive commands:

| Command | Description |
|---------|-------------|
| `:q` | Quit |
| `:k N` | Set top-k results |
| `:c chapter` | Filter by chapter (e.g., `:c 11-planning`) |
| `:t type` | Filter by content type (procedure/concept/reference/troubleshooting) |
| `:tags tag1,tag2` | Filter by topic tags |
| `:clear` | Clear all filters |
| `:src` | Toggle source display (query_rag only) |
| `:help` | Show commands |

## GPU Optimizations (RTX 5070 Ti)

The pipeline uses:
- **FP16 (half precision)** — 2x embedding throughput
- **torch.compile** — 10-20% additional speedup
- **Batch size 128** — Optimal for 16 GB VRAM
- **TF32 enabled** — Free on Ampere/Blackwell
- **Inference mode** — No gradient overhead

Expected performance:
- Ingestion: ~30 seconds (591 files → 4,800 chunks)
- Search latency: ~20 ms
- RAG latency (Ollama): ~300 ms
- RAG latency (GPT-4o-mini): ~800 ms

## Troubleshooting

### CUDA Out of Memory
```yaml
# In config.yaml, reduce batch size:
embeddings:
  batch_size: 64  # Default 128
```

### ChromaDB Not Found
```bash
# Run ingestion first
python ingest_gpu.py
```

### Ollama Connection Failed
```bash
# Start Ollama server
ollama serve

# Check it's running
curl http://localhost:11434/api/tags
```

### OpenAI API Key Error
```bash
export OPENAI_API_KEY="sk-your-key"
# Or add to config.yaml as plain text (not recommended for shared repos)
```

### Scraper Path Changed
Update `config.yaml`:
```yaml
paths:
  md_root: "ceph-scraper/output/md/YOUR_NEW_TIMESTAMP_FOLDER"
```

## Adding New Documents

1. Add markdown files to the scraper output directory
2. Re-run ingestion: `python ingest_gpu.py`
3. ChromaDB will append new chunks (upserts by ID)

## Evaluation Test Cases

The `eval.py` includes 14 test cases covering:
- **Procedures** (4): device class, bootstrap, erasure pool, upgrade
- **Concepts** (3): CRUSH failure domain, PGs, BlueStore compression
- **Troubleshooting** (2): degraded PGs, OSD down
- **Configuration** (2): network config, 3-AZ erasure profile
- **Commands** (2): list device classes, cluster health

Add custom test cases by editing the `TEST_CASES` list in `eval.py`.

## License

Internal use — IBM Storage Ceph documentation.