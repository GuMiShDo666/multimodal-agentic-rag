import gradio as gr
from core.chat_interface import ChatInterface
from core.document_manager import DocumentManager
from core.rag_system import RAGSystem
import os

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

def create_gradio_ui():
    rag_system = RAGSystem()
    rag_system.initialize()
    
    doc_manager = DocumentManager(rag_system)
    chat_interface = ChatInterface(rag_system)
    
    def format_database_summary():
        return doc_manager.get_database_summary()

    def build_database_handler(progress=gr.Progress()):
        result, parent_count, child_count = doc_manager.build_rumor_database(
            progress_callback=lambda p, desc: progress(p, desc=desc)
        )
        gr.Info(f"已索引 {result['rows']} 篇文章，生成 {parent_count} 个父文本块和 {child_count} 个子文本块")
        return format_database_summary()
    
    def clear_handler():
        try:
            doc_manager.clear_all()
            gr.Info("已清空知识库")
        except Exception as exc:
            gr.Error(f"清空知识库失败：{exc}")
        return format_database_summary()
    
    def chat_handler(msg, hist):
        for chunk in chat_interface.chat(msg, hist):
            yield chunk
    
    def clear_chat_handler():
        chat_interface.clear_session()
    
    with gr.Blocks(title="谣言检测 RAG") as demo:
        
        with gr.Tab("知识库", elem_id="doc-management-tab"):
            gr.Markdown("## 谣言检测参考知识库")
            gr.Markdown("从 `data/reference_data` 构建检索知识库，Agent 会把这些文章作为谣言检测证据。")

            build_btn = gr.Button("构建 / 重建 RAG 知识库", variant="primary", size="md")

            gr.Markdown("## 知识库状态")
            database_summary = gr.Textbox(
                value=format_database_summary(),
                interactive=False,
                lines=8,
                max_lines=12,
                elem_id="file-list-box",
                show_label=False
            )
            
            with gr.Row():
                refresh_btn = gr.Button("刷新", size="md")
                clear_btn = gr.Button("清空", variant="stop", size="md")
            
            build_btn.click(build_database_handler, None, database_summary, show_progress="corner")
            refresh_btn.click(format_database_summary, None, database_summary)
            clear_btn.click(clear_handler, None, database_summary)
        
        with gr.Tab("检测"):
            chatbot = gr.Chatbot(
                height=720, 
                placeholder="<strong>输入文本或上传图片进行谣言检测。</strong><br><em>图片会先经过 OCR 和 BLIP 解析，再进入检索判断。</em>",
                show_label=False,
                avatar_images=(None, os.path.join(ASSETS_DIR, "chatbot_avatar.png")),
                layout="bubble"
            )
            chatbot.clear(clear_chat_handler)

            chat_input = gr.MultimodalTextbox(
                file_types=["image"],
                file_count="single",
                placeholder="输入需要核验的内容，或上传一张图片...",
                show_label=False,
                sources=["upload"],
            )
            
            gr.ChatInterface(
                fn=chat_handler,
                chatbot=chatbot,
                textbox=chat_input,
                multimodal=True,
            )
    
    return demo
