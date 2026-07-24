// 툴 카드 → 변환 패널 전환 + 업로드 + 파일별 진행 상황(배지 / 진행률 바 / 다운로드)
// 도구 종류: 이미지 변환 / PDF 도구(→JPG, 압축, 분할)는 "파일별" 처리,
//            PDF 병합은 "여러 개 → 하나" 처리라 별도 UI를 쓴다.

// 도구 정의: mode "each"(파일마다 개별 처리) / "merge"(모아서 하나로)
const TOOLS = {
    "img-jpg":      { mode: "each", endpoint: "/convert", format: "jpg",  accept: "image/*", label: "이미지 → JPG", pickFormat: true },
    "img-png":      { mode: "each", endpoint: "/convert", format: "png",  accept: "image/*", label: "이미지 → PNG", pickFormat: true },
    "img-webp":     { mode: "each", endpoint: "/convert", format: "webp", accept: "image/*", label: "이미지 → WEBP", pickFormat: true },
    "pdf-jpg":      { mode: "each", endpoint: "/pdf/to-jpg",   accept: ".pdf", label: "PDF → JPG" },
    "pdf-compress": { mode: "each", endpoint: "/pdf/compress", accept: ".pdf", label: "PDF 압축" },
    "pdf-split":    { mode: "each", endpoint: "/pdf/split",    accept: ".pdf", label: "PDF 분할" },
    "pdf-text":     { mode: "each", endpoint: "/pdf/extract-text",   accept: ".pdf", label: "PDF 텍스트 추출" },
    "pdf-images":   { mode: "each", endpoint: "/pdf/extract-images", accept: ".pdf", label: "PDF 이미지 추출" },
    "pdf-merge":    { mode: "merge", endpoint: "/pdf/merge",   accept: ".pdf", label: "PDF 병합" },
    "vid-mp4":      { mode: "each", endpoint: "/video/convert", format: "mp4",  accept: "video/*", label: "영상 → MP4" },
    "vid-gif":      { mode: "each", endpoint: "/video/convert", format: "gif",  accept: "video/*", label: "영상 → GIF" },
    "vid-webm":     { mode: "each", endpoint: "/video/convert", format: "webm", accept: "video/*", label: "영상 → WEBM" },
    "aud-mp3":      { mode: "each", endpoint: "/audio/convert", format: "mp3", accept: "audio/*,video/*", label: "오디오 → MP3" },
    "aud-wav":      { mode: "each", endpoint: "/audio/convert", format: "wav", accept: "audio/*,video/*", label: "오디오 → WAV" },
    "aud-m4a":      { mode: "each", endpoint: "/audio/convert", format: "m4a", accept: "audio/*,video/*", label: "오디오 → M4A" },
};

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const formatSel = document.getElementById("format");
const results = document.getElementById("results");
const dzText = document.getElementById("dzText");

const converter = document.getElementById("converter");
const convLabel = document.getElementById("convLabel");
const backBtn = document.getElementById("backBtn");
const toolsSection = document.querySelector(".tools");

const mergeArea = document.getElementById("mergeArea");
const mergeList = document.getElementById("mergeList");
const mergeBtn = document.getElementById("mergeBtn");

let currentTool = null;   // 현재 선택된 도구 객체
let mergeFiles = [];      // 병합 대기 파일 목록 (순서 유지)

// 카드를 누르면 해당 도구로 변환 패널 열기
document.querySelectorAll(".card[data-tool]").forEach((card) => {
    card.addEventListener("click", () => openTool(card.dataset.tool));
});

// 이미지 도구에서 포맷 셀렉트를 바꾸면 라벨·엔드포인트 정보 갱신
formatSel.addEventListener("change", () => {
    if (currentTool && currentTool.pickFormat) {
        currentTool.format = formatSel.value;
        convLabel.textContent = `이미지 → ${formatSel.value.toUpperCase()}`;
    }
});

backBtn.addEventListener("click", closeTool);

function openTool(toolId) {
    if (!TOOLS[toolId]) return; // 별도 패널을 쓰는 도구(예: AutoGrid)는 여기서 처리하지 않음
    currentTool = { ...TOOLS[toolId] };
    convLabel.textContent = currentTool.label;
    results.innerHTML = "";
    mergeFiles = [];
    renderMergeList();

    // 파일 선택 필터
    fileInput.setAttribute("accept", currentTool.accept);

    // 이미지 도구만 포맷 셀렉트 노출
    if (currentTool.pickFormat) {
        formatSel.hidden = false;
        formatSel.value = currentTool.format;
    } else {
        formatSel.hidden = true;
    }

    // 병합 모드 UI 토글
    const isMerge = currentTool.mode === "merge";
    mergeArea.hidden = !isMerge;
    dzText.textContent = isMerge
        ? "합칠 PDF들을 끌어다 놓기 (여러 개)"
        : "여기로 파일을 끌어다 놓기";

    toolsSection.hidden = true;
    converter.hidden = false;
    converter.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeTool() {
    converter.hidden = true;
    toolsSection.hidden = false;
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- 드롭존 공통 ----------
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
    handleFiles(fileInput.files);
    fileInput.value = "";
});
["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.add("hover");
    })
);
["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.remove("hover");
    })
);
dropzone.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files));

function handleFiles(fileList) {
    if (!currentTool) return;
    if (currentTool.mode === "merge") {
        [...fileList].forEach((f) => mergeFiles.push(f));
        renderMergeList();
    } else {
        [...fileList].forEach((file) => processEach(file));
    }
}

// ---------- 파일별 처리 (이미지 / PDF→JPG / 압축 / 분할) ----------
function processEach(file) {
    const row = createRow(file.name);
    results.prepend(row.el);

    const form = new FormData();
    form.append("file", file);
    if (currentTool.format) form.append("format", currentTool.format);

    sendXhr(currentTool.endpoint, form, row);
}

// ---------- 병합 처리 ----------
function renderMergeList() {
    mergeList.innerHTML = "";
    mergeFiles.forEach((f, i) => {
        const li = document.createElement("li");
        li.className = "merge-item";
        li.innerHTML = `
            <span class="mi-order">${i + 1}</span>
            <span class="mi-name">${escapeHtml(f.name)}</span>
            <span class="mi-actions">
                <button class="mi-up" title="위로" ${i === 0 ? "disabled" : ""}>▲</button>
                <button class="mi-down" title="아래로" ${i === mergeFiles.length - 1 ? "disabled" : ""}>▼</button>
                <button class="mi-del" title="빼기">✕</button>
            </span>`;
        li.querySelector(".mi-up").addEventListener("click", () => moveMerge(i, -1));
        li.querySelector(".mi-down").addEventListener("click", () => moveMerge(i, 1));
        li.querySelector(".mi-del").addEventListener("click", () => {
            mergeFiles.splice(i, 1);
            renderMergeList();
        });
        mergeList.appendChild(li);
    });
    mergeBtn.disabled = mergeFiles.length < 2;
    mergeBtn.textContent =
        mergeFiles.length >= 2 ? `병합하기 (${mergeFiles.length}개)` : "병합하려면 2개 이상 필요";
}

function moveMerge(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= mergeFiles.length) return;
    [mergeFiles[i], mergeFiles[j]] = [mergeFiles[j], mergeFiles[i]];
    renderMergeList();
}

mergeBtn.addEventListener("click", () => {
    if (mergeFiles.length < 2) return;
    const names = mergeFiles.map((f) => f.name).join(", ");
    const row = createRow(`병합: ${names}`);
    results.prepend(row.el);

    const form = new FormData();
    mergeFiles.forEach((f) => form.append("file", f)); // 순서대로 추가

    sendXhr(currentTool.endpoint, form, row);

    // 목록 비우기 (결과는 위에 남음)
    mergeFiles = [];
    renderMergeList();
});

// ---------- XHR 공통 (업로드 진행률 + 결과 처리) ----------
function sendXhr(endpoint, form, row) {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) row.setProgress((e.loaded / e.total) * 100);
    });
    xhr.upload.addEventListener("load", () => row.setConverting());
    xhr.addEventListener("load", () => {
        let data = {};
        try {
            data = JSON.parse(xhr.responseText);
        } catch (_) {
            /* 아래에서 실패 처리 */
        }
        if (xhr.status >= 200 && xhr.status < 300 && data.ok) {
            row.setDone(data.download_name, data.download_url, data.note);
        } else {
            row.setError(data.error || `오류 (HTTP ${xhr.status})`);
        }
    });
    xhr.addEventListener("error", () =>
        row.setError("서버에 연결할 수 없습니다. run.bat 창이 켜져 있는지 확인하세요.")
    );

    xhr.open("POST", endpoint);
    xhr.send(form);
}

// ---------- 결과 줄 ----------
function createRow(title) {
    const el = document.createElement("li");
    el.className = "result processing";
    el.innerHTML = `
        <div class="row-head">
            <span class="name">${escapeHtml(title)}</span>
            <span class="right"><span class="badge processing">처리중</span></span>
        </div>
        <div class="bar"><div class="bar-fill"></div></div>`;

    const right = el.querySelector(".right");
    const fill = el.querySelector(".bar-fill");
    const bar = el.querySelector(".bar");

    return {
        el,
        setProgress(pct) {
            bar.classList.remove("indeterminate");
            fill.style.width = `${Math.max(2, Math.min(100, pct))}%`;
        },
        setConverting() {
            fill.style.width = "100%";
            bar.classList.add("indeterminate");
        },
        setDone(downloadName, url, note) {
            el.classList.remove("processing");
            el.classList.add("ok");
            bar.classList.remove("indeterminate");
            fill.style.width = "100%";
            el.querySelector(".name").innerHTML =
                `${escapeHtml(downloadName)}` +
                (note ? ` <span class="note">${escapeHtml(note)}</span>` : "");
            right.innerHTML = `
                <span class="badge done">완료</span>
                <a class="download" href="${url}">다운로드</a>`;
            setTimeout(() => bar.classList.add("hide"), 600);
        },
        setError(message) {
            el.classList.remove("processing");
            el.classList.add("err");
            bar.classList.remove("indeterminate");
            bar.classList.add("hide");
            right.innerHTML = `<span class="badge error" title="${escapeHtml(message)}">실패</span>`;
            const msg = document.createElement("div");
            msg.className = "err-msg";
            msg.textContent = message;
            el.appendChild(msg);
        },
    };
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[c]));
}
