"""RAGAS-style evaluation over eval/queries.jsonl.

Metrics: context_precision, context_recall (source-ref based), faithfulness and
answer_relevancy (LLM-judged when a key is present, lexical overlap otherwise)."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from app.core import db
from app.core.config import get_settings
from app.rag.retrieval import retrieve

EVAL_FILE = Path(__file__).resolve().parents[3] / "eval" / "queries.jsonl"
FAITHFULNESS_GATE = 0.85


def _lexical_overlap(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    return len(ta & tb) / max(len(tb), 1)


async def run_eval(tenant_id: UUID, *, generate: bool = True) -> dict:
    cases = [json.loads(line) for line in EVAL_FILE.read_text().splitlines() if line.strip()]
    s = get_settings()
    precisions, recalls, faith, relev, details = [], [], [], [], []
    from app.agent.llm import get_llm

    llm = get_llm() if generate else None
    for case in cases:
        res = await retrieve(tenant_id=tenant_id, query=case["question"], diet=case.get("diet"), guest_count=case.get("guest_count"), use_llm_rewrite=False)
        refs = set(case.get("expected_source_refs", []))
        got_refs = []
        for h in res.hits:
            row = await db.fetchrow("SELECT source_ref FROM rag_sources WHERE id = $1", h.source_id)
            got_refs.append(row["source_ref"] if row else "")
        relevant = [r for r in got_refs if any(r.startswith(e) for e in refs)]
        precision = len(relevant) / max(len(got_refs), 1)
        recall = len({e for e in refs if any(g.startswith(e) for g in got_refs)}) / max(len(refs), 1)
        answer, f, rel = None, None, None
        if llm and res.context_blocks:
            answer = await llm.complete_short(
                "Answer the customer's question using only the context. If not answerable, say so.\n\nContext:\n"
                + "\n\n".join(res.context_blocks) + f"\n\nQuestion: {case['question']}"
            )
            judge = await llm.complete_short(
                "You are grading a RAG answer. Reply with JSON {\"faithfulness\":0-1,\"relevancy\":0-1}. "
                "faithfulness = fraction of claims supported by the context; relevancy = how well it answers the question.\n\n"
                f"Context:\n{chr(10).join(res.context_blocks)}\n\nQuestion: {case['question']}\nAnswer: {answer}"
            )
            try:
                j = json.loads(judge[judge.find("{"): judge.rfind("}") + 1])
                f, rel = float(j["faithfulness"]), float(j["relevancy"])
            except Exception:  # noqa: BLE001
                pass
        if f is None and case.get("reference_answer"):
            ctx = "\n".join(res.context_blocks)
            f = _lexical_overlap(ctx, case["reference_answer"])
            rel = _lexical_overlap(case["question"], case["reference_answer"])
        precisions.append(precision)
        recalls.append(recall)
        if f is not None:
            faith.append(f)
        if rel is not None:
            relev.append(rel)
        details.append({"q": case["question"], "precision": precision, "recall": recall, "faithfulness": f, "relevancy": rel, "answer": answer, "latency_ms": res.latency_ms})

    def avg(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    summary = {"cases": len(cases), "context_precision": avg(precisions), "context_recall": avg(recalls), "faithfulness": avg(faith), "answer_relevancy": avg(relev)}
    await db.execute(
        """INSERT INTO rag_eval_runs (tenant_id, embedding_model, llm_model, cases, context_precision, context_recall, faithfulness, answer_relevancy, details)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
        tenant_id, s.resolved_embedding_model, s.resolved_llm_model, len(cases), summary["context_precision"], summary["context_recall"],
        summary["faithfulness"], summary["answer_relevancy"], {"details": details},
    )
    summary["gate_passed"] = summary["faithfulness"] is None or summary["faithfulness"] >= FAITHFULNESS_GATE
    return summary
