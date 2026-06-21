"""
scripts/seed_week.py
--------------------
Inserts a realistic W24 dataset directly into ChromaDB for delta testing.

This is only needed once — to give the delta logic a "previous week" to compare
against W25. In production the scheduler handles this naturally week by week.

Run from project root:
    python scripts/seed_week.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from processing.chunker_embedder import process_documents
from storage.vector_store import save_chunks, get_stats

# ── Realistic W24 paper dataset ───────────────────────────────────────────────
# These reflect real LLM research themes from the weeks before W25.
# Topic overlap with W25 is intentional — the delta will detect what shifted.

W24_PAPERS = [
    {
        "paper_id": "seed_w24_001",
        "title": "Scaling Laws Revisited: Diminishing Returns in Large Language Model Training",
        "abstract": (
            "Recent work has questioned whether the scaling laws governing large language model "
            "performance continue to hold at extreme parameter counts. We present empirical evidence "
            "that returns on additional compute diminish significantly beyond 100B parameters when "
            "training data quality is held constant. Our analysis of 47 models across three model "
            "families suggests that data curation and diversity matter more than raw scale beyond "
            "a certain threshold. We propose a revised scaling framework that accounts for data "
            "saturation effects and provides more accurate predictions of downstream task performance."
        ),
        "url": "https://arxiv.org/abs/seed_w24_001",
        "published": "2026-06-09",
        "authors": ["J. Martinez", "S. Kim", "R. Patel"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_002",
        "title": "Chain-of-Thought Prompting Does Not Reliably Improve Reasoning in Sub-7B Models",
        "abstract": (
            "Chain-of-thought (CoT) prompting has been widely adopted as a technique to improve "
            "reasoning in large language models. However, our systematic evaluation across 12 "
            "reasoning benchmarks reveals that CoT prompting consistently fails to improve — and "
            "often degrades — performance in models with fewer than 7 billion parameters. We "
            "hypothesize that CoT requires a minimum capacity threshold to be beneficial, below "
            "which the intermediate reasoning steps introduce more noise than signal. These findings "
            "challenge the universal applicability of CoT and suggest that smaller models require "
            "fundamentally different approaches to reasoning improvement."
        ),
        "url": "https://arxiv.org/abs/seed_w24_002",
        "published": "2026-06-10",
        "authors": ["A. Chen", "B. Williams", "C. Lopez"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_003",
        "title": "RLHF at Scale: Challenges in Human Preference Data Collection for LLMs",
        "abstract": (
            "Reinforcement learning from human feedback (RLHF) has become the dominant approach "
            "for aligning large language models with human preferences. However, scaling RLHF "
            "introduces significant challenges that have received limited attention: annotator "
            "disagreement increases substantially for complex tasks, preference data exhibits "
            "strong recency and demographic biases, and reward model generalization remains "
            "unreliable outside the training distribution. We document these failure modes across "
            "three production-scale RLHF deployments and propose evaluation protocols to detect "
            "alignment degradation before deployment."
        ),
        "url": "https://arxiv.org/abs/seed_w24_003",
        "published": "2026-06-10",
        "authors": ["D. Thompson", "E. Garcia", "F. Brown"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_004",
        "title": "Retrieval-Augmented Generation: A Systematic Comparison of Chunking Strategies",
        "abstract": (
            "Retrieval-augmented generation (RAG) systems are highly sensitive to document chunking "
            "strategy, yet this choice is rarely studied systematically. We evaluate fixed-size, "
            "sentence-boundary, semantic, and recursive chunking across six RAG benchmarks and "
            "find that recursive chunking outperforms alternatives on long-form documents while "
            "semantic chunking excels on structured data. Surprisingly, chunk size has a greater "
            "impact on retrieval precision than the choice of embedding model across all benchmarks. "
            "We release a benchmark suite for standardized RAG chunking evaluation."
        ),
        "url": "https://arxiv.org/abs/seed_w24_004",
        "published": "2026-06-11",
        "authors": ["G. Wilson", "H. Lee", "I. Anderson"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_005",
        "title": "Hallucination in LLMs: A Taxonomy and Mitigation Survey",
        "abstract": (
            "Hallucination — the generation of factually incorrect but fluent text — remains one "
            "of the most critical unsolved problems in large language models. We present a unified "
            "taxonomy distinguishing intrinsic hallucination (contradicting provided context) from "
            "extrinsic hallucination (generating unverifiable claims). Our survey of 89 mitigation "
            "techniques finds that retrieval augmentation reduces extrinsic hallucination by 34-67% "
            "but has minimal effect on intrinsic hallucination. We identify calibration of model "
            "confidence as the most promising under-explored direction for comprehensive hallucination "
            "reduction."
        ),
        "url": "https://arxiv.org/abs/seed_w24_005",
        "published": "2026-06-11",
        "authors": ["J. Taylor", "K. Moore", "L. Jackson"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_006",
        "title": "Efficient Fine-Tuning of LLMs via Sparse Parameter Updates",
        "abstract": (
            "Full fine-tuning of large language models is computationally prohibitive for most "
            "practitioners. While LoRA has emerged as the dominant parameter-efficient fine-tuning "
            "method, it introduces rank constraints that limit expressivity. We propose SparseAdapt, "
            "which selects and updates only the top-k most gradient-sensitive parameters during "
            "fine-tuning. SparseAdapt achieves comparable performance to full fine-tuning on seven "
            "benchmarks while updating only 2.1% of parameters, outperforming LoRA on tasks "
            "requiring significant knowledge modification. Memory requirements are reduced by 71% "
            "compared to full fine-tuning."
        ),
        "url": "https://arxiv.org/abs/seed_w24_006",
        "published": "2026-06-12",
        "authors": ["M. Harris", "N. Clark", "O. Lewis"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
    {
        "paper_id": "seed_w24_007",
        "title": "Context Window Utilization in Long-Document LLM Tasks",
        "abstract": (
            "Modern large language models support context windows of 128k tokens or more, yet "
            "empirical studies consistently show that models fail to effectively utilize information "
            "from the middle of long contexts — the so-called lost-in-the-middle phenomenon. We "
            "conduct a controlled study of context utilization across five LLMs on long-document QA "
            "tasks and confirm that performance degrades significantly for relevant information "
            "positioned beyond the first and last 20% of the context window. Positional encoding "
            "modifications and explicit attention supervision partially mitigate this issue but do "
            "not eliminate it."
        ),
        "url": "https://arxiv.org/abs/seed_w24_007",
        "published": "2026-06-12",
        "authors": ["P. Robinson", "Q. Walker", "R. Young"],
        "topic": 'cat:cs.LG AND abs:"large language models"',
        "source": "arxiv",
        "week": "2026-W24"
    },
]


def seed_w24():
    print("Seeding W24 papers into ChromaDB...")
    print(f"Papers to seed: {len(W24_PAPERS)}\n")

    print("Chunking and embedding W24 papers...")
    chunks = process_documents(W24_PAPERS)
    print(f"Created {len(chunks)} chunks\n")

    print("Saving to ChromaDB...")
    saved = save_chunks(chunks)
    stats = get_stats()

    print(f"Saved {saved} chunks")
    print(f"Total chunks in DB: {stats['total_chunks']}")
    print(f"\nW24 seeded successfully.")
    print("You can now run the delta pipeline comparing W24 vs W25.")


if __name__ == "__main__":
    seed_w24()