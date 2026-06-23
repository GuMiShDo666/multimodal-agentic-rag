import csv
import re
from collections import Counter
from pathlib import Path

import config


CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")
OUTPUT_FIELDS = ["id", "source", "title", "url", "date", "text"]


def clean_text(value):
    text = str(value or "").replace("\u00a0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def clean_for_csv(value):
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def open_csv_dict_reader(path):
    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            file = path.open("r", encoding=encoding, newline="")
            reader = csv.DictReader(file)
            if reader.fieldnames:
                return file, reader
            file.close()
        except UnicodeDecodeError as exc:
            last_error = exc
        except csv.Error as exc:
            last_error = exc
    raise RuntimeError(f"Unable to read CSV file {path}: {last_error}")


def iter_reference_csv_files(source_dir=config.REFERENCE_DATA_DIR):
    source_dir = Path(source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"Missing reference data directory: {source_dir}")
    return sorted(
        path
        for path in source_dir.glob("*.csv")
        if path.is_file() and not path.name.startswith(".")
    )


def read_reference_rows(source_dir=config.REFERENCE_DATA_DIR):
    rows = []
    skipped_empty_text = 0
    skipped_duplicates = 0
    source_counts = Counter()
    seen = set()

    for csv_path in iter_reference_csv_files(source_dir):
        file, reader = open_csv_dict_reader(csv_path)
        with file:
            fields = set(reader.fieldnames or [])
            required = {"title", "url", "date", "text"}
            if not required.issubset(fields):
                missing = ", ".join(sorted(required - fields))
                raise ValueError(f"{csv_path} is missing required columns: {missing}")

            for raw in reader:
                title = clean_for_csv(raw.get("title"))
                url = clean_for_csv(raw.get("url"))
                date = clean_for_csv(raw.get("date"))
                text = clean_text(raw.get("text"))
                if not text:
                    skipped_empty_text += 1
                    continue

                dedupe_key = url or f"{title}\n{text[:500]}"
                if dedupe_key in seen:
                    skipped_duplicates += 1
                    continue
                seen.add(dedupe_key)

                source = csv_path.stem
                source_counts[source] += 1
                rows.append(
                    {
                        "id": f"REF-{len(rows) + 1:05d}",
                        "source": source,
                        "title": title or "(untitled)",
                        "url": url,
                        "date": date,
                        "text": text,
                    }
                )

    return rows, {
        "source_counts": dict(source_counts),
        "skipped_empty_text": skipped_empty_text,
        "skipped_duplicates": skipped_duplicates,
    }


def write_merged_csv(rows, output_path=config.RUMOR_DATABASE_CSV):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "url": row["url"],
                "date": row["date"],
                "text": clean_for_csv(row["text"]),
            }
            for row in rows
        )
    return output_path


def row_to_markdown(row):
    return "\n".join(
        [
            f"## Article {row['id']}: {row['title']}",
            f"Record ID: {row['id']}",
            f"Source: {row['source']}",
            f"Title: {row['title']}",
            f"URL: {row['url'] or 'N/A'}",
            f"Date: {row['date'] or 'N/A'}",
            "",
            "### Content",
            row["text"],
        ]
    )


def write_rag_markdown(rows, metadata, output_path=config.RUMOR_DATABASE_MARKDOWN):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_lines = [
        f"- {source}: {count}"
        for source, count in sorted(metadata["source_counts"].items())
    ]

    sections = [
        "# Rumor Detection Reference Knowledge Base",
        "This knowledge base contains fact-checking and health-science reference articles for retrieval-augmented rumor detection.",
        f"Total indexed articles: {len(rows)}",
        f"Skipped empty-text rows: {metadata['skipped_empty_text']}",
        f"Skipped duplicate rows: {metadata['skipped_duplicates']}",
        "## Source Counts",
        "\n".join(source_lines),
        "# Articles",
    ]
    sections.extend(row_to_markdown(row) for row in rows)
    output_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def build_rumor_database():
    rows, metadata = read_reference_rows()
    csv_path = write_merged_csv(rows)
    markdown_path = write_rag_markdown(rows, metadata)
    return {
        "rows": len(rows),
        "csv_path": str(csv_path),
        "markdown_path": str(markdown_path),
        **metadata,
    }


def database_summary():
    csv_path = Path(config.RUMOR_DATABASE_CSV)
    if not csv_path.exists():
        return "参考知识库尚未构建。"

    total = 0
    source_counts = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            total += 1
            source_counts[row.get("source", "")] += 1

    top_sources = "\n".join(
        f"- {source}: {count}"
        for source, count in source_counts.most_common(10)
    )
    return (
        f"文章数量：{total}\n"
        f"来源数量：{len(source_counts)}\n"
        f"主要来源：\n{top_sources}\n"
        f"CSV 路径：{csv_path}"
    )
