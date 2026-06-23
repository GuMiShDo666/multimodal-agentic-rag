const form = document.querySelector("#detect-form");
const textInput = document.querySelector("#claim-text");
const imageInput = document.querySelector("#claim-image");
const imagePreview = document.querySelector("#image-preview");
const fileName = document.querySelector("#file-name");
const submitButton = document.querySelector("#submit-button");
const clearInputButton = document.querySelector("#clear-input");
const resetSessionButton = document.querySelector("#reset-session");
const refreshDbButton = document.querySelector("#refresh-db");
const runState = document.querySelector("#run-state");
const answerContent = document.querySelector("#answer-content");
const messageList = document.querySelector("#message-list");
const databaseSummary = document.querySelector("#database-summary");

function setState(label, mode) {
  runState.textContent = label;
  runState.className = `run-state ${mode || ""}`.trim();
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitButton.textContent = isLoading ? "检测中" : "开始检测";
}

function escapeText(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderAnswer(text) {
  answerContent.classList.remove("empty");
  answerContent.textContent = text || "没有生成可展示的检测结果。";
}

function renderMessages(messages) {
  const details = (messages || []).filter((message) => message.title);
  if (!details.length) {
    messageList.innerHTML = '<div class="empty-state">暂无检索过程。</div>';
    return;
  }

  messageList.innerHTML = details
    .map((message, index) => {
      const title = escapeText(message.title || `过程 ${index + 1}`);
      const content = escapeText(message.content || "");
      const open = index < 2 ? "open" : "";
      return `
        <details class="message-card" ${open}>
          <summary>${title}</summary>
          <pre>${content}</pre>
        </details>
      `;
    })
    .join("");
}

async function refreshDatabase() {
  try {
    const response = await fetch("/api/database/summary");
    const data = await response.json();
    databaseSummary.textContent = data.summary || "未读取到知识库状态。";
  } catch (error) {
    databaseSummary.textContent = `知识库状态读取失败：${error.message}`;
  }
}

function clearInputs() {
  textInput.value = "";
  imageInput.value = "";
  fileName.textContent = "支持 png、jpg、jpeg、webp、bmp、tif";
  imagePreview.removeAttribute("src");
  imagePreview.style.display = "none";
}

imageInput.addEventListener("change", () => {
  const file = imageInput.files && imageInput.files[0];
  if (!file) {
    fileName.textContent = "支持 png、jpg、jpeg、webp、bmp、tif";
    imagePreview.style.display = "none";
    return;
  }

  fileName.textContent = file.name;
  const previewUrl = URL.createObjectURL(file);
  imagePreview.src = previewUrl;
  imagePreview.style.display = "block";
});

clearInputButton.addEventListener("click", clearInputs);
refreshDbButton.addEventListener("click", refreshDatabase);

resetSessionButton.addEventListener("click", async () => {
  await fetch("/api/session/reset", { method: "POST" });
  answerContent.textContent = "提交文本或图片后，这里会显示模型给出的判断。";
  answerContent.classList.add("empty");
  messageList.innerHTML = '<div class="empty-state">暂无检索过程。</div>';
  setState("待检测", "");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const text = textInput.value.trim();
  const image = imageInput.files && imageInput.files[0];
  if (!text && !image) {
    setState("缺少输入", "error");
    renderAnswer("请输入文本，或上传一张图片。");
    return;
  }

  const payload = new FormData();
  payload.append("text", text);
  if (image) {
    payload.append("image", image);
  }

  setState("检测中", "running");
  setLoading(true);
  answerContent.classList.remove("empty");
  answerContent.textContent = "正在解析输入、检索知识库并生成判断。";
  messageList.innerHTML = '<div class="empty-state">正在等待 Agent 返回过程记录。</div>';

  try {
    const response = await fetch("/api/detect", {
      method: "POST",
      body: payload,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "检测请求失败。");
    }

    renderAnswer(data.answer);
    renderMessages(data.messages);
    databaseSummary.textContent = data.database || databaseSummary.textContent;
    setState("检测完成", "done");
  } catch (error) {
    renderAnswer(`检测失败：${error.message}`);
    messageList.innerHTML = '<div class="empty-state">本次请求没有生成检索过程。</div>';
    setState("检测失败", "error");
  } finally {
    setLoading(false);
  }
});

refreshDatabase();
