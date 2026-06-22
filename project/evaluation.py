import argparse
import csv
import json
import re
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_sources(answer):
    match = re.search(r"\bSources:\s*\n(?P<sources>(?:- .*(?:\n|$))*)", answer)
    if not match:
        return []
    sources = []
    for line in match.group("sources").splitlines():
        line = line.strip()
        if line.startswith("- "):
            sources.append(line[2:].split(" — ", 1)[0].strip())
    return sources


def normalize_terms(text):
    return set(re.findall(r"[a-zA-Z0-9_\-\u4e00-\u9fff]+", str(text).lower()))


def overlap_score(answer, reference):
    reference_terms = normalize_terms(reference)
    if not reference_terms:
        return ""
    answer_terms = normalize_terms(answer)
    return round(len(answer_terms & reference_terms) / len(reference_terms), 4)


def source_hit_rate(actual_sources, expected_sources):
    if not expected_sources:
        return ""
    actual_text = "\n".join(actual_sources).lower()
    hits = sum(1 for source in expected_sources if str(source).lower() in actual_text)
    return round(hits / len(expected_sources), 4)


def latest_ai_message(messages):
    for message in reversed(messages):
        if message.__class__.__name__ == "AIMessage" and not getattr(message, "name", None):
            return message.content
    return ""


def verdict_from_answer(answer):
    match = re.search(r"判定[:：]\s*(谣言|非谣言|证据不足)", answer)
    return match.group(1) if match else ""


def evaluate(qa_items, output_path, rebuild_database=True):
    from langchain_core.messages import HumanMessage

    from core.document_manager import DocumentManager
    from core.rag_system import RAGSystem

    rag_system = RAGSystem()
    rag_system.initialize()

    document_manager = DocumentManager(rag_system)
    if rebuild_database:
        result, parent_count, child_count = document_manager.build_rumor_database()
        print(
            f"Rumor database indexed: {result['rows']} rows, "
            f"{parent_count} parent chunks, {child_count} child chunks"
        )

    rows = []
    for index, item in enumerate(qa_items, start=1):
        question = item["question"]
        rag_system.reset_thread()
        result = rag_system.agent_graph.invoke(
            {"messages": [HumanMessage(content=question)]},
            config=rag_system.get_config(),
        )
        answer = latest_ai_message(result.get("messages", []))
        sources = extract_sources(answer)
        contexts = [
            context
            for agent_answer in result.get("agent_answers", [])
            for context in agent_answer.get("contexts", [])
        ]

        row = {
            "index": index,
            "question": question,
            "answer": answer,
            "reference": item.get("reference", ""),
            "expected_verdict": item.get("expected_verdict", ""),
            "predicted_verdict": verdict_from_answer(answer),
            "sources": "\n".join(sources),
            "expected_sources": "\n".join(item.get("expected_sources", [])),
            "context_count": len(contexts),
            "reference_overlap": overlap_score(answer, item.get("reference", "")),
            "expected_source_hit_rate": source_hit_rate(sources, item.get("expected_sources", [])),
        }
        rows.append(row)
        print(f"[{index}/{len(qa_items)}] {question}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "index",
        "question",
        "answer",
        "reference",
        "expected_verdict",
        "predicted_verdict",
        "sources",
        "expected_sources",
        "context_count",
        "reference_overlap",
        "expected_source_hit_rate",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Evaluation written to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run a lightweight QA evaluation over RumorDetection-RAG.")
    parser.add_argument("--qa", required=True, help="Path to a JSON file containing QA items.")
    parser.add_argument("--output", default="rag_evaluation_results.csv", help="CSV output path.")
    parser.add_argument("--no-rebuild", action="store_true", help="Use the existing Qdrant index instead of rebuilding it.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate(load_json(args.qa), args.output, rebuild_database=not args.no_rebuild)
