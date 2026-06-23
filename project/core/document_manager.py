from pathlib import Path
import config
from utils import clear_directory_contents
from rumor_database import build_rumor_database, database_summary

class DocumentManager:

    def __init__(self, rag_system):
        self.rag_system = rag_system
        self.markdown_dir = Path(config.MARKDOWN_DIR)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

    def build_rumor_database(self, progress_callback=None):
        if progress_callback:
            progress_callback(0.1, desc="正在重置向量库")
        self.clear_all()

        if progress_callback:
            progress_callback(0.35, desc="正在准备参考知识库")
        result = build_rumor_database()

        md_path = Path(result["markdown_path"])
        if progress_callback:
            progress_callback(0.55, desc="正在切分参考文章")
        parent_chunks, child_chunks = self.rag_system.chunker.create_chunks_single(
            md_path,
            source_name=Path(result["csv_path"]).name,
        )

        if not child_chunks:
            raise ValueError("参考知识库没有生成可索引的子文本块。")

        if progress_callback:
            progress_callback(0.8, desc="正在写入 Qdrant 向量库")
        self.rag_system.parent_store.save_many(parent_chunks)
        collection = self.rag_system.vector_db.get_collection(self.rag_system.collection_name)
        batch_size = max(1, config.INDEX_BATCH_SIZE)
        for start in range(0, len(child_chunks), batch_size):
            end = min(start + batch_size, len(child_chunks))
            print(f"Indexing child chunks {start + 1}-{end} of {len(child_chunks)}")
            collection.add_documents(child_chunks[start:end])

        if progress_callback:
            progress_callback(1.0, desc="参考知识库已就绪")
        return result, len(parent_chunks), len(child_chunks)
    
    def get_markdown_files(self):
        sources = self.rag_system.parent_store.list_sources()
        if sources:
            return sources
        return sorted(p.name for p in self.markdown_dir.glob("*.md"))

    def get_database_summary(self):
        indexed_sources = self.get_markdown_files()
        indexed_text = "\n".join(f"- {source}" for source in indexed_sources) if indexed_sources else "- 尚未索引"
        return f"{database_summary()}\n已索引来源：\n{indexed_text}"
    
    def clear_all(self):
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.rag_system.vector_db.delete_collection(self.rag_system.collection_name)

        clear_directory_contents(self.markdown_dir)
        self.rag_system.parent_store.clear_store()

        self.rag_system.vector_db.create_collection(self.rag_system.collection_name)
