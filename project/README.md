# RumerDetection-rag Project Notes

This folder contains the runnable Agentic RAG application for Chinese text and image rumor detection.

The application builds a local retrieval index from the reference article CSV files under `data/reference_data/`. During the build step, `project/rumor_database.py` filters empty rows, removes duplicate articles, generates `data/rumor_database.csv`, and creates `markdown_docs/rumor_database.md` for indexing.

```csv
id,source,title,url,date,text
REF-00001,中华医学健康科普知识库,老年人总穿拖鞋易疲劳，拖鞋挑选有讲究,https://...,2022-05-18,...
```

`DocumentManager.build_rumor_database()` clears the local Qdrant collection, chunks the generated Markdown, stores parent chunks, and indexes child chunks.

Image inputs are handled by `core/image_claim_extractor.py`. The extractor uses PaddleOCR for text in the image and BLIP for image captioning, then passes the extracted claim content into the same RAG chat flow used for text input.

Run:

```bash
python project/app.py
```

Then click **Build / Rebuild Reference RAG Database** in the Gradio UI before asking text or image questions.
