#!/usr/bin/env python3
"""
Evaluation harness for RAG pipeline quality testing.

Tests retrieval relevance and answer accuracy against ground truth.
"""

import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

import yaml

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from query_rag import (
    load_config, setup_embedding_model, connect_chromadb,
    search, answer_question, GPUEmbeddingFunction
)
from llm_client import get_llm_client


@dataclass
class TestCase:
    """Single test case for evaluation."""
    question: str
    expected_keywords: List[str]          # Keywords that MUST appear in answer
    expected_source_chapters: List[str]   # Chapters that should be retrieved
    expected_content_type: Optional[str]  # Expected content type (procedure/concept/etc.)
    category: str                         # Category for reporting
    difficulty: str                       # easy/medium/hard


@dataclass
class EvalResult:
    """Evaluation result for a single test case."""
    question: str
    category: str
    difficulty: str
    answer: str
    sources: List[Dict]
    chunks_retrieved: int
    keyword_recall: float           # Fraction of expected keywords found
    source_chapter_recall: float    # Fraction of expected chapters retrieved
    content_type_match: bool        # Whether expected content type was retrieved
    latency_ms: float               # Total latency
    passed: bool                    # Overall pass/fail


# ─── Test Cases ────────────────────────────────────────────────────────────

TEST_CASES = [
    # Procedures
    TestCase(
        question="How to set device class for SSD OSD?",
        expected_keywords=["ceph osd crush set-device-class", "ssd", "osd"],
        expected_source_chapters=["11-planning"],
        expected_content_type="procedure",
        category="procedure",
        difficulty="easy"
    ),
    TestCase(
        question="Bootstrap a new storage cluster with cephadm",
        expected_keywords=["cephadm bootstrap", "cluster", "storage"],
        expected_source_chapters=["12-installing"],
        expected_content_type="procedure",
        category="procedure",
        difficulty="easy"
    ),
    TestCase(
        question="Create an erasure coded pool with k=4 m=2",
        expected_keywords=["ceph osd pool create", "erasure", "k=4", "m=2"],
        expected_source_chapters=["11-planning"],
        expected_content_type="procedure",
        category="procedure",
        difficulty="medium"
    ),
    TestCase(
        question="Upgrade IBM Storage Ceph cluster using cephadm",
        expected_keywords=["cephadm upgrade", "upgrade"],
        expected_source_chapters=["13-upgrading"],
        expected_content_type="procedure",
        category="procedure",
        difficulty="medium"
    ),

    # Concepts
    TestCase(
        question="What is a CRUSH failure domain?",
        expected_keywords=["failure domain", "crush", "osd", "host"],
        expected_source_chapters=["11-planning"],
        expected_content_type="concept",
        category="concept",
        difficulty="easy"
    ),
    TestCase(
        question="Explain placement groups in Ceph",
        expected_keywords=["placement group", "pg", "data distribution"],
        expected_source_chapters=["11-planning"],
        expected_content_type="concept",
        category="concept",
        difficulty="easy"
    ),
    TestCase(
        question="How does BlueStore compression work?",
        expected_keywords=["bluestore", "compression", "inline"],
        expected_source_chapters=["15-edge-clusters"],
        expected_content_type="concept",
        category="concept",
        difficulty="medium"
    ),

    # Troubleshooting
    TestCase(
        question="PGs stuck in degraded state - how to fix?",
        expected_keywords=["degraded", "pg", "osd", "ceph pg ls"],
        expected_source_chapters=["16-administering"],
        expected_content_type="troubleshooting",
        category="troubleshooting",
        difficulty="medium"
    ),
    TestCase(
        question="OSD is down - troubleshooting steps",
        expected_keywords=["osd", "down", "ceph osd tree", "recovery"],
        expected_source_chapters=["16-administering"],
        expected_content_type="troubleshooting",
        category="troubleshooting",
        difficulty="medium"
    ),

    # Configuration
    TestCase(
        question="Configure network for Ceph public and cluster networks",
        expected_keywords=["public network", "cluster network", "ceph config"],
        expected_source_chapters=["14-configuring"],
        expected_content_type="reference",
        category="configuration",
        difficulty="medium"
    ),
    TestCase(
        question="Erasure code profile for 3 availability zones",
        expected_keywords=["erasure", "availability zone", "k=", "m="],
        expected_source_chapters=["11-planning"],
        expected_content_type="procedure",
        category="configuration",
        difficulty="hard"
    ),

    # Commands
    TestCase(
        question="List all device classes in cluster",
        expected_keywords=["ceph osd crush class ls", "device class"],
        expected_source_chapters=["11-planning"],
        expected_content_type="procedure",
        category="command",
        difficulty="easy"
    ),
    TestCase(
        question="Check Ceph cluster health status",
        expected_keywords=["ceph status", "ceph -s", "health"],
        expected_source_chapters=["16-administering"],
        expected_content_type="procedure",
        category="command",
        difficulty="easy"
    ),
]


# ─── Evaluation Functions ──────────────────────────────────────────────────

def evaluate_keyword_recall(answer: str, expected_keywords: List[str]) -> float:
    """Calculate fraction of expected keywords found in answer."""
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return found / len(expected_keywords)


def evaluate_source_chapter_recall(sources: List[Dict], expected_chapters: List[str]) -> float:
    """Calculate fraction of expected chapters found in sources."""
    if not expected_chapters:
        return 1.0
    retrieved_chapters = set(s.get("chapter", "") for s in sources)
    found = sum(1 for ch in expected_chapters if ch in retrieved_chapters)
    return found / len(expected_chapters)


def evaluate_content_type_match(sources: List[Dict], expected_type: Optional[str]) -> bool:
    """Check if expected content type appears in retrieved sources."""
    if not expected_type:
        return True
    retrieved_types = set(s.get("content_type", "") for s in sources)
    return expected_type in retrieved_types


def run_evaluation(
    config_path: str = "config.yaml",
    test_cases: Optional[List[TestCase]] = None,
    top_k: int = 5,
    keyword_threshold: float = 0.5,
    chapter_threshold: float = 0.5
) -> List[EvalResult]:
    """Run full evaluation suite."""
    cases = test_cases or TEST_CASES

    # Load config and setup
    config = load_config(config_path)
    model = setup_embedding_model(config)

    embedding_fn = GPUEmbeddingFunction(
        model=model,
        batch_size=config["embeddings"].get("batch_size", 128),
        normalize=config["embeddings"].get("normalize", True)
    )

    collection = connect_chromadb(config, embedding_fn)
    llm_client = get_llm_client(config)

    results = []

    print(f"\n🧪 Running evaluation on {len(cases)} test cases...")
    print("=" * 70)

    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case.category.upper()} | {case.difficulty}")
        print(f"Q: {case.question}")

        start_time = time.time()

        # Run RAG
        result = answer_question(
            case.question,
            llm_client,
            collection,
            config,
            top_k=top_k,
            show_sources=False
        )

        latency_ms = (time.time() - start_time) * 1000

        # Evaluate
        keyword_recall = evaluate_keyword_recall(result["answer"], case.expected_keywords)
        chapter_recall = evaluate_source_chapter_recall(result["sources"], case.expected_source_chapters)
        type_match = evaluate_content_type_match(result["sources"], case.expected_content_type)

        # Overall pass: keyword recall + chapter recall thresholds
        passed = (keyword_recall >= keyword_threshold and
                  chapter_recall >= chapter_threshold)

        eval_result = EvalResult(
            question=case.question,
            category=case.category,
            difficulty=case.difficulty,
            answer=result["answer"],
            sources=result["sources"],
            chunks_retrieved=result["chunks_retrieved"],
            keyword_recall=keyword_recall,
            source_chapter_recall=chapter_recall,
            content_type_match=type_match,
            latency_ms=latency_ms,
            passed=passed
        )

        results.append(eval_result)

        # Print summary
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} | Keywords: {keyword_recall:.0%} | Chapters: {chapter_recall:.0%} | Type: {'✓' if type_match else '✗'} | {latency_ms:.0f}ms")

    return results


def print_summary(results: List[EvalResult]):
    """Print evaluation summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    print("\n" + "=" * 70)
    print("📊 EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total tests:     {total}")
    print(f"Passed:          {passed} ({passed/total:.0%})")
    print(f"Failed:          {total - passed} ({(total-passed)/total:.0%})")

    # By category
    print("\nBy Category:")
    categories = {}
    for r in results:
        cat = categories.setdefault(r.category, {"total": 0, "passed": 0})
        cat["total"] += 1
        if r.passed:
            cat["passed"] += 1

    for cat, stats in sorted(categories.items()):
        print(f"  {cat:20s} {stats['passed']}/{stats['total']} ({stats['passed']/stats['total']:.0%})")

    # By difficulty
    print("\nBy Difficulty:")
    difficulties = {}
    for r in results:
        diff = difficulties.setdefault(r.difficulty, {"total": 0, "passed": 0})
        diff["total"] += 1
        if r.passed:
            diff["passed"] += 1

    for diff, stats in sorted(difficulties.items()):
        print(f"  {diff:10s} {stats['passed']}/{stats['total']} ({stats['passed']/stats['total']:.0%})")

    # Average metrics
    avg_keyword = sum(r.keyword_recall for r in results) / total
    avg_chapter = sum(r.source_chapter_recall for r in results) / total
    avg_latency = sum(r.latency_ms for r in results) / total

    print(f"\nAvg Keyword Recall:    {avg_keyword:.1%}")
    print(f"Avg Chapter Recall:    {avg_chapter:.1%}")
    print(f"Avg Latency:           {avg_latency:.0f}ms")


def save_results(results: List[EvalResult], output_path: str = "eval_results.json"):
    """Save detailed results to JSON."""
    data = [asdict(r) for r in results]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Detailed results saved to {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline quality")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--top-k", type=int, default=5, help="Chunks to retrieve")
    parser.add_argument("--keyword-threshold", type=float, default=0.5, help="Keyword recall threshold")
    parser.add_argument("--chapter-threshold", type=float, default=0.5, help="Chapter recall threshold")
    parser.add_argument("--output", default="eval_results.json", help="Output JSON path")
    parser.add_argument("--category", help="Run only specific category")
    parser.add_argument("--difficulty", help="Run only specific difficulty")

    args = parser.parse_args()

    # Filter test cases
    cases = TEST_CASES
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    if args.difficulty:
        cases = [c for c in cases if c.difficulty == args.difficulty]

    if not cases:
        print("❌ No test cases match filters")
        return

    # Run evaluation
    results = run_evaluation(
        config_path=args.config,
        test_cases=cases,
        top_k=args.top_k,
        keyword_threshold=args.keyword_threshold,
        chapter_threshold=args.chapter_threshold
    )

    # Print summary
    print_summary(results)

    # Save results
    save_results(results, args.output)


if __name__ == "__main__":
    main()