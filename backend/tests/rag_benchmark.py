"""
RAG Benchmark System
====================
自建RAG Benchmark - 用于评估RAG系统的检索质量和回答准确性。

评估指标:
  1. Hit Rate (命中率): 回答中是否包含预期关键信息
  2. Citation Accuracy (引用准确率): 引用的教材来源是否正确
  3. Average Response Time (平均响应时间)

运行方式:
  python -m backend.tests.rag_benchmark
  python -m backend.tests.rag_benchmark --base-url http://localhost:8000
  python -m backend.tests.rag_benchmark --top-k 10
"""

import argparse
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Benchmark Questions
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkQuestion:
    """A single benchmark test case."""
    id: int
    question: str
    question_type: str  # factual | comparative | cross_textbook | reasoning
    expected_answer_keywords: list[str]  # keywords that should appear in a correct answer
    expected_sources: list[str]  # textbook names expected in citations
    description: str = ""


BENCHMARK_QUESTIONS: list[BenchmarkQuestion] = [
    # ── Factual Questions (事实型) ──────────────────────────────────────────
    BenchmarkQuestion(
        id=1,
        question="什么是炎症反应？",
        question_type="factual",
        expected_answer_keywords=["炎症", "血管", "组织损伤", "防御", "白细胞"],
        expected_sources=["病理学"],
        description="basic inflammation definition",
    ),
    BenchmarkQuestion(
        id=2,
        question="静息电位是如何产生的？",
        question_type="factual",
        expected_answer_keywords=["静息电位", "钾离子", "细胞膜", "浓度梯度"],
        expected_sources=["生理学"],
        description="resting potential mechanism",
    ),
    BenchmarkQuestion(
        id=3,
        question="什么是结核分枝杆菌？其致病机制是什么？",
        question_type="factual",
        expected_answer_keywords=["结核", "分枝杆菌", "抗酸", "肺"],
        expected_sources=["医学微生物学"],
        description="Mycobacterium tuberculosis pathogenesis",
    ),
    BenchmarkQuestion(
        id=4,
        question="简述心脏的泵血过程。",
        question_type="factual",
        expected_answer_keywords=["心室", "收缩", "舒张", "瓣膜", "射血"],
        expected_sources=["生理学"],
        description="cardiac pumping cycle",
    ),
    BenchmarkQuestion(
        id=5,
        question="什么是肉芽组织？",
        question_type="factual",
        expected_answer_keywords=["肉芽", "新生", "毛细血管", "成纤维细胞", "修复"],
        expected_sources=["病理学"],
        description="granulation tissue definition",
    ),

    # ── Comparative Questions (对比型) ──────────────────────────────────────
    BenchmarkQuestion(
        id=6,
        question="静息电位和动作电位有什么区别？",
        question_type="comparative",
        expected_answer_keywords=["静息电位", "动作电位", "钾离子", "钠离子", "去极化"],
        expected_sources=["生理学"],
        description="resting vs action potential",
    ),
    BenchmarkQuestion(
        id=7,
        question="细胞坏死和细胞凋亡的区别是什么？",
        question_type="comparative",
        expected_answer_keywords=["坏死", "凋亡", "程序性", "被动", "炎症"],
        expected_sources=["病理学"],
        description="necrosis vs apoptosis",
    ),
    BenchmarkQuestion(
        id=8,
        question="良性肿瘤和恶性肿瘤有什么区别？",
        question_type="comparative",
        expected_answer_keywords=["良性", "恶性", "转移", "分化", "浸润"],
        expected_sources=["病理学"],
        description="benign vs malignant tumors",
    ),
    BenchmarkQuestion(
        id=9,
        question="体液免疫和细胞免疫的区别是什么？",
        question_type="comparative",
        expected_answer_keywords=["体液免疫", "细胞免疫", "B细胞", "T细胞", "抗体"],
        expected_sources=["生理学"],
        description="humoral vs cellular immunity",
    ),
    BenchmarkQuestion(
        id=10,
        question="动脉和静脉在结构和功能上有什么不同？",
        question_type="comparative",
        expected_answer_keywords=["动脉", "静脉", "管壁", "弹性", "瓣膜"],
        expected_sources=["生理学"],
        description="arteries vs veins",
    ),

    # ── Cross-Textbook Questions (跨教材型) ─────────────────────────────────
    BenchmarkQuestion(
        id=11,
        question="免疫系统如何对抗病毒感染？",
        question_type="cross_textbook",
        expected_answer_keywords=["免疫", "病毒", "干扰素", "T细胞", "抗体"],
        expected_sources=["生理学", "医学微生物学"],
        description="immune response to viruses (physiology + microbiology)",
    ),
    BenchmarkQuestion(
        id=12,
        question="细菌感染引起的炎症反应涉及哪些病理变化？",
        question_type="cross_textbook",
        expected_answer_keywords=["细菌", "炎症", "渗出", "白细胞", "组织损伤"],
        expected_sources=["病理学", "医学微生物学"],
        description="bacterial infection and inflammation (pathology + microbiology)",
    ),
    BenchmarkQuestion(
        id=13,
        question="免疫缺陷病的病理生理机制是什么？常见病原体有哪些？",
        question_type="cross_textbook",
        expected_answer_keywords=["免疫缺陷", "HIV", "机会性感染", "T细胞", "病原体"],
        expected_sources=["病理生理学", "医学微生物学"],
        description="immunodeficiency pathophysiology and pathogens",
    ),
    BenchmarkQuestion(
        id=14,
        question="感染性休克的发病机制是什么？涉及哪些病理生理过程？",
        question_type="cross_textbook",
        expected_answer_keywords=["休克", "感染", "内毒素", "微循环", "器官衰竭"],
        expected_sources=["病理生理学", "医学微生物学"],
        description="septic shock mechanisms (pathophysiology + microbiology)",
    ),
    BenchmarkQuestion(
        id=15,
        question="肿瘤免疫逃逸的机制是什么？从免疫学和病理学角度分析。",
        question_type="cross_textbook",
        expected_answer_keywords=["肿瘤", "免疫逃逸", "MHC", "免疫编辑", "T细胞"],
        expected_sources=["生理学", "病理学"],
        description="tumor immune evasion (physiology + pathology)",
    ),

    # ── Reasoning Questions (推理型) ────────────────────────────────────────
    BenchmarkQuestion(
        id=16,
        question="为什么高血压会导致左心室肥厚？请从病理生理学角度解释。",
        question_type="reasoning",
        expected_answer_keywords=["高血压", "左心室", "肥厚", "后负荷", "心肌"],
        expected_sources=["病理生理学", "生理学"],
        description="why hypertension causes LVH",
    ),
    BenchmarkQuestion(
        id=17,
        question="肝硬化患者为什么会出现腹水？请解释其病理生理机制。",
        question_type="reasoning",
        expected_answer_keywords=["肝硬化", "腹水", "门静脉", "白蛋白", "钠水潴留"],
        expected_sources=["病理生理学", "病理学"],
        description="why cirrhosis causes ascites",
    ),
    BenchmarkQuestion(
        id=18,
        question="为什么糖尿病患者容易发生感染？从免疫和代谢角度分析。",
        question_type="reasoning",
        expected_answer_keywords=["糖尿病", "感染", "免疫", "高血糖", "白细胞"],
        expected_sources=["病理生理学", "医学微生物学"],
        description="why diabetics are prone to infection",
    ),
    BenchmarkQuestion(
        id=19,
        question="为什么大面积烧伤会导致休克？请解释其病理生理过程。",
        question_type="reasoning",
        expected_answer_keywords=["烧伤", "休克", "血浆", "低血容量", "渗出"],
        expected_sources=["病理生理学", "病理学"],
        description="why burns cause shock",
    ),
    BenchmarkQuestion(
        id=20,
        question="为什么缺氧会导致细胞水肿？请从细胞代谢角度分析。",
        question_type="reasoning",
        expected_answer_keywords=["缺氧", "细胞水肿", "ATP", "钠泵", "细胞膜"],
        expected_sources=["病理生理学"],
        description="why hypoxia causes cellular edema",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation Helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase and strip whitespace."""
    return text.lower().strip()


def compute_hit_rate(answer: str, expected_keywords: list[str]) -> tuple[float, list[str]]:
    """
    Check whether the answer contains the expected keywords.
    Returns (hit_ratio, matched_keywords).
    """
    answer_lower = normalize_text(answer)
    matched = [kw for kw in expected_keywords if normalize_text(kw) in answer_lower]
    ratio = len(matched) / len(expected_keywords) if expected_keywords else 0.0
    return ratio, matched


def compute_citation_accuracy(
    citations: list[dict],
    expected_sources: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Check whether the retrieved citations come from the expected textbooks.
    Returns (accuracy_ratio, matched_sources, all_citation_sources).
    """
    if not citations:
        return 0.0, [], []

    cited_sources: list[str] = []
    for c in citations:
        tb_name = c.get("textbook", "")
        if tb_name and tb_name not in cited_sources:
            cited_sources.append(tb_name)

    matched = [s for s in expected_sources if any(s in cs for cs in cited_sources)]
    ratio = len(matched) / len(expected_sources) if expected_sources else 0.0
    return ratio, matched, cited_sources


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Result for a single benchmark question."""
    question_id: int
    question: str
    question_type: str
    answer: str
    hit_rate: float
    matched_keywords: list[str]
    citation_accuracy: float
    matched_sources: list[str]
    cited_sources: list[str]
    response_time: float
    citations: list[dict] = field(default_factory=list)


async def run_single_question(
    client: httpx.AsyncClient,
    base_url: str,
    bq: BenchmarkQuestion,
) -> BenchmarkResult:
    """Send a single question to the RAG endpoint and evaluate the response."""
    start = time.perf_counter()

    try:
        resp = await client.post(
            f"{base_url}/api/rag/query",
            params={"question": bq.question},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            question_id=bq.id,
            question=bq.question,
            question_type=bq.question_type,
            answer=f"[ERROR] {e}",
            hit_rate=0.0,
            matched_keywords=[],
            citation_accuracy=0.0,
            matched_sources=[],
            cited_sources=[],
            response_time=elapsed,
            citations=[],
        )

    elapsed = time.perf_counter() - start

    answer = data.get("answer", "")
    citations = data.get("citations", [])

    hit_rate, matched_kw = compute_hit_rate(answer, bq.expected_answer_keywords)
    cit_acc, matched_src, cited_src = compute_citation_accuracy(citations, bq.expected_sources)

    return BenchmarkResult(
        question_id=bq.id,
        question=bq.question,
        question_type=bq.question_type,
        answer=answer,
        hit_rate=hit_rate,
        matched_keywords=matched_kw,
        citation_accuracy=cit_acc,
        matched_sources=matched_src,
        cited_sources=cited_src,
        response_time=elapsed,
        citations=citations,
    )


async def run_benchmark(
    base_url: str = "http://localhost:8000",
    questions: Optional[list[BenchmarkQuestion]] = None,
) -> list[BenchmarkResult]:
    """Run the full benchmark suite and return results."""
    if questions is None:
        questions = BENCHMARK_QUESTIONS

    results: list[BenchmarkResult] = []

    async with httpx.AsyncClient() as client:
        for i, bq in enumerate(questions, 1):
            print(f"  [{i:02d}/{len(questions)}] Running: {bq.question[:40]}...")
            result = await run_single_question(client, base_url, bq)
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 90
THIN_SEP = "-" * 90


def print_detailed_results(results: list[BenchmarkResult]) -> None:
    """Print per-question detailed results."""
    print(f"\n{SEPARATOR}")
    print("DETAILED RESULTS")
    print(SEPARATOR)

    for r in results:
        print(f"\nQ{r.question_id:02d} [{r.question_type}] {r.question}")
        print(f"  Hit Rate:         {r.hit_rate:.0%}  (matched: {', '.join(r.matched_keywords) or 'none'})")
        print(f"  Citation Accuracy: {r.citation_accuracy:.0%}  (expected: {', '.join(r.matched_sources) or '-'}, got: {', '.join(r.cited_sources) or 'none'})")
        print(f"  Response Time:    {r.response_time:.2f}s")
        # Show first 120 chars of answer as preview
        preview = r.answer[:120].replace("\n", " ")
        if len(r.answer) > 120:
            preview += "..."
        print(f"  Answer Preview:   {preview}")


def compute_type_stats(results: list[BenchmarkResult]) -> dict[str, dict]:
    """Compute aggregate stats grouped by question type."""
    from collections import defaultdict

    buckets: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for r in results:
        buckets[r.question_type].append(r)

    stats = {}
    for qtype, bucket in buckets.items():
        avg_hit = sum(r.hit_rate for r in bucket) / len(bucket)
        avg_cit = sum(r.citation_accuracy for r in bucket) / len(bucket)
        avg_time = sum(r.response_time for r in bucket) / len(bucket)
        stats[qtype] = {
            "count": len(bucket),
            "avg_hit_rate": avg_hit,
            "avg_citation_accuracy": avg_cit,
            "avg_response_time": avg_time,
        }
    return stats


def print_summary_table(results: list[BenchmarkResult]) -> None:
    """Print the final summary table."""
    total = len(results)
    overall_hit = sum(r.hit_rate for r in results) / total if total else 0
    overall_cit = sum(r.citation_accuracy for r in results) / total if total else 0
    overall_time = sum(r.response_time for r in results) / total if total else 0

    type_stats = compute_type_stats(results)

    # Full pass: hit_rate == 1.0 AND citation_accuracy == 1.0
    full_pass = sum(1 for r in results if r.hit_rate == 1.0 and r.citation_accuracy == 1.0)

    print(f"\n{SEPARATOR}")
    print("RAG BENCHMARK SUMMARY")
    print(SEPARATOR)

    # Per-type breakdown
    print(f"\n{'Type':<18} {'Count':>5} {'Hit Rate':>10} {'Citation Acc':>14} {'Avg Time':>10}")
    print(THIN_SEP)
    for qtype in ["factual", "comparative", "cross_textbook", "reasoning"]:
        if qtype in type_stats:
            s = type_stats[qtype]
            print(f"{qtype:<18} {s['count']:>5} {s['avg_hit_rate']:>9.0%} {s['avg_citation_accuracy']:>13.0%} {s['avg_response_time']:>9.2f}s")
    print(THIN_SEP)

    # Overall
    print(f"{'OVERALL':<18} {total:>5} {overall_hit:>9.0%} {overall_cit:>13.0%} {overall_time:>9.2f}s")
    print(THIN_SEP)
    print(f"Full Pass (hit=100% & citation=100%): {full_pass}/{total}  ({full_pass/total:.0%})")
    print(SEPARATOR)

    # Per-question summary
    print(f"\n{'ID':<4} {'Type':<18} {'Hit':>5} {'Cite':>5} {'Time':>7}  Question")
    print(THIN_SEP)
    for r in results:
        q_short = r.question[:36] + ("..." if len(r.question) > 36 else "")
        print(f"{r.question_id:<4} {r.question_type:<18} {r.hit_rate:>4.0%} {r.citation_accuracy:>4.0%} {r.response_time:>6.2f}s  {q_short}")
    print(SEPARATOR)


def export_results_json(results: list[BenchmarkResult], path: str) -> None:
    """Export benchmark results to a JSON file."""
    total = len(results)
    overall_hit = sum(r.hit_rate for r in results) / total if total else 0
    overall_cit = sum(r.citation_accuracy for r in results) / total if total else 0
    overall_time = sum(r.response_time for r in results) / total if total else 0
    full_pass = sum(1 for r in results if r.hit_rate == 1.0 and r.citation_accuracy == 1.0)

    output = {
        "summary": {
            "total_questions": total,
            "overall_hit_rate": round(overall_hit, 4),
            "overall_citation_accuracy": round(overall_cit, 4),
            "avg_response_time_sec": round(overall_time, 4),
            "full_pass_count": full_pass,
            "full_pass_rate": round(full_pass / total, 4) if total else 0,
        },
        "by_type": compute_type_stats(results),
        "results": [
            {
                "id": r.question_id,
                "question": r.question,
                "type": r.question_type,
                "hit_rate": round(r.hit_rate, 4),
                "matched_keywords": r.matched_keywords,
                "citation_accuracy": round(r.citation_accuracy, 4),
                "matched_sources": r.matched_sources,
                "cited_sources": r.cited_sources,
                "response_time_sec": round(r.response_time, 4),
                "answer_preview": r.answer[:300],
                "citations_count": len(r.citations),
            }
            for r in results
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults exported to: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(base_url: str = "http://localhost:8000", top_k: int = 5) -> None:
    """Entry point for the benchmark."""
    print(SEPARATOR)
    print("RAG Benchmark - 自建RAG Benchmark")
    print(SEPARATOR)
    print(f"Base URL:      {base_url}")
    print(f"Questions:     {len(BENCHMARK_QUESTIONS)}")
    print(f"Question types: factual, comparative, cross_textbook, reasoning")
    print(SEPARATOR)

    # Health check
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_url}/api/health", timeout=10.0)
            resp.raise_for_status()
            print("Health check:  OK")
        except Exception as e:
            print(f"Health check:  FAILED ({e})")
            print("Make sure the backend server is running.")
            return

    # Check RAG index status
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_url}/api/rag/status", timeout=10.0)
            resp.raise_for_status()
            status = resp.json()
            print(f"RAG Index:     {status.get('total_chunks', 0)} chunks, "
                  f"{status.get('indexed_textbooks', 0)} textbooks indexed")
        except Exception:
            print("RAG Index:     Could not retrieve status")

    print(f"\nRunning {len(BENCHMARK_QUESTIONS)} benchmark questions...\n")

    results = await run_benchmark(base_url)

    print_detailed_results(results)
    print_summary_table(results)

    # Export to JSON
    output_path = "rag_benchmark_results.json"
    export_results_json(results, output_path)


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="RAG Benchmark - 自建RAG Benchmark")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the backend API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k retrieval parameter (default: 5, informational only)",
    )
    args = parser.parse_args()

    asyncio.run(main(base_url=args.base_url, top_k=args.top_k))
