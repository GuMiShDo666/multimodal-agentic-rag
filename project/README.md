# RumerDetection-rag Project Notes

This folder contains the runnable Agentic RAG application for Chinese rumor detection.

The app uses the original RumorDetection CSV files as the retrieval database:

- `data/train.csv`
- `data/valid.csv`
- `data/test.csv`
- `data/rumor_database.csv`

`project/rumor_database.py` merges the split CSV files and creates `markdown_docs/rumor_database.md` for indexing. `DocumentManager.build_rumor_database()` clears the old local Qdrant collection, chunks the generated Markdown, stores parent chunks, and indexes child chunks.

Run:

```bash
python project/app.py
```

Then click **Build / Rebuild Rumor RAG Database** in the Gradio UI before asking questions.
