// AutoGrid - AI 얼굴 격자 오버레이 (autogrid.html에서 포팅)
// 얼굴 자동 감지(face-api.js) / 전체 격자 / 수동 추가·제거 / PNG 저장.
// 모든 처리는 브라우저 안에서만 이뤄지며, 얼굴 감지 모델 로딩에만 인터넷이 필요하다.

(() => {
    const FACEAPI_SRC = "https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js";
    const MODEL_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/model/";

    const panel = document.getElementById("autogrid");
    const toolsSection = document.querySelector(".tools");

    const canvas = document.getElementById("agCanvas");
    const ctx = canvas.getContext("2d");
    const frame = document.getElementById("agFrame");
    const dropzone = document.getElementById("agDropzone");
    const fileInput = document.getElementById("agFile");
    const statusEl = document.getElementById("agStatus");

    const gridSizeInput = document.getElementById("agGridSize");
    const lineWidthInput = document.getElementById("agLineWidth");
    const opacityInput = document.getElementById("agOpacity");
    const paddingInput = document.getElementById("agPadding");
    const lineColorInput = document.getElementById("agLineColor");

    const btnBack = document.getElementById("agBack");
    const btnUpload = document.getElementById("agUpload");
    const btnFace = document.getElementById("agFace");
    const btnFull = document.getElementById("agFull");
    const btnAdd = document.getElementById("agAdd");
    const btnRemove = document.getElementById("agRemove");
    const btnApply = document.getElementById("agApply");
    const btnSave = document.getElementById("agSave");
    const btnFolder = document.getElementById("agFolder");
    const btnReset = document.getElementById("agReset");
    const countEl = document.getElementById("agCount");
    const folderInfo = document.getElementById("agFolderInfo");
    const folderNameEl = document.getElementById("agFolderName");

    let originalImage = null;
    let modelsLoaded = false;
    let faceBoxes = [];
    let manualMode = null; // 'add' | 'remove' | null
    let isDragging = false;
    let dragStart = null;
    let dragCurrent = null;
    let saveDirHandle = null;
    let statusTimer = null;

    // ---------- 패널 열기/닫기 ----------
    document.querySelector('.card[data-tool="ai-autogrid"]').addEventListener("click", () => {
        toolsSection.hidden = true;
        panel.hidden = false;
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    btnBack.addEventListener("click", () => {
        panel.hidden = true;
        toolsSection.hidden = false;
        window.scrollTo({ top: 0, behavior: "smooth" });
    });

    // ---------- 상태 표시 ----------
    function showStatus(msg, type, duration = 3000) {
        clearTimeout(statusTimer);
        statusEl.textContent = msg;
        statusEl.className = "ag-status " + type;
        statusEl.hidden = false;
        if (type !== "loading") {
            statusTimer = setTimeout(() => { statusEl.hidden = true; }, duration);
        }
    }
    function hideStatus() {
        clearTimeout(statusTimer);
        statusEl.hidden = true;
    }

    // ---------- 슬라이더 값 표시 ----------
    function updateRangeDisplays() {
        document.getElementById("agGridSizeVal").textContent = gridSizeInput.value + "px";
        document.getElementById("agLineWidthVal").textContent = parseFloat(lineWidthInput.value).toFixed(1);
        document.getElementById("agOpacityVal").textContent = Math.round(opacityInput.value * 100) + "%";
        document.getElementById("agPaddingVal").textContent = paddingInput.value + "%";
    }
    [gridSizeInput, lineWidthInput, opacityInput, paddingInput].forEach((i) =>
        i.addEventListener("input", updateRangeDisplays)
    );

    function updateFaceCount() {
        if (faceBoxes.length > 0) {
            countEl.textContent = `${faceBoxes.length}개 영역 선택됨`;
            countEl.hidden = false;
        } else {
            countEl.hidden = true;
        }
        btnApply.disabled = faceBoxes.length === 0;
    }

    // ---------- face-api 로딩 (필요할 때만) ----------
    function loadFaceApiScript() {
        if (window.faceapi) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = FACEAPI_SRC;
            s.onload = resolve;
            s.onerror = () => reject(new Error("얼굴 감지 라이브러리 로딩 실패 — 인터넷 연결을 확인하세요."));
            document.head.appendChild(s);
        });
    }

    async function loadModels() {
        if (modelsLoaded) return;
        showStatus("얼굴 감지 모델 로딩 중...", "loading");
        await loadFaceApiScript();
        await faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL);
        modelsLoaded = true;
        hideStatus();
    }

    // ---------- 이미지 로드 ----------
    function showCanvas() {
        dropzone.hidden = true;
        frame.hidden = false;
        [btnFace, btnFull, btnReset, btnSave, btnAdd, btnRemove].forEach((b) => (b.disabled = false));
    }

    function loadImageFromSrc(src) {
        const img = new Image();
        img.onload = () => {
            originalImage = img;
            faceBoxes = [];
            setManualMode(null);
            drawScene();
            showCanvas();
            updateFaceCount();
            hideStatus();
        };
        img.src = src;
    }

    function loadImage(file) {
        const r = new FileReader();
        r.onload = (e) => loadImageFromSrc(e.target.result);
        r.readAsDataURL(file);
    }

    // 클립보드 붙여넣기 (패널이 열려 있을 때만)
    document.addEventListener("paste", (e) => {
        if (panel.hidden) return;
        const items = e.clipboardData?.items;
        if (!items) return;
        for (const item of items) {
            if (item.type.startsWith("image/")) {
                e.preventDefault();
                const f = item.getAsFile();
                if (f) { loadImage(f); showStatus("클립보드에서 불러옴", "success"); }
                return;
            }
        }
    });

    // ---------- 그리기 ----------
    function drawOriginal() {
        if (!originalImage) return;
        canvas.width = originalImage.naturalWidth;
        canvas.height = originalImage.naturalHeight;
        ctx.drawImage(originalImage, 0, 0);
    }

    function drawScene() { drawOriginal(); drawFaceBoxPreviews(); }

    function paddedBox(box) {
        const pp = parseInt(paddingInput.value) / 100;
        const pw = box.width * pp, ph = box.height * pp;
        return { x: box.x - pw, y: box.y - ph, w: box.width + pw * 2, h: box.height + ph * 2 };
    }

    function drawFaceBoxPreviews() {
        faceBoxes.forEach((box, i) => {
            const { x, y, w, h } = paddedBox(box);
            const cx = x + w / 2, cy = y + h / 2;

            ctx.save();
            ctx.strokeStyle = "rgba(23,178,106,0.7)";
            ctx.lineWidth = 2;
            ctx.setLineDash([8, 5]);
            ctx.beginPath();
            ctx.ellipse(cx, cy, w / 2, h / 2, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);

            const fs = Math.max(14, Math.min(22, box.width * 0.12));
            ctx.fillStyle = "rgba(23,178,106,0.9)";
            ctx.font = `700 ${fs}px sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.fillText(`${i + 1}`, cx, y - 6);
            ctx.restore();
        });
    }

    function drawDragPreview() {
        if (!isDragging || !dragStart || !dragCurrent) return;
        const x = Math.min(dragStart.x, dragCurrent.x), y = Math.min(dragStart.y, dragCurrent.y);
        const w = Math.abs(dragCurrent.x - dragStart.x), h = Math.abs(dragCurrent.y - dragStart.y);
        ctx.save();
        ctx.strokeStyle = "rgba(23,178,106,0.8)";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(x, y, w, h);
        ctx.fillStyle = "rgba(23,178,106,0.06)";
        ctx.fillRect(x, y, w, h);
        ctx.setLineDash([]);
        ctx.restore();
    }

    function gridColor() {
        const c = lineColorInput.value;
        const r = parseInt(c.slice(1, 3), 16), g = parseInt(c.slice(3, 5), 16), b = parseInt(c.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${parseFloat(opacityInput.value)})`;
    }

    function drawGrid(x, y, w, h) {
        const gs = parseInt(gridSizeInput.value);
        ctx.save();
        ctx.strokeStyle = gridColor();
        ctx.lineWidth = parseFloat(lineWidthInput.value);
        for (let lx = x; lx <= x + w; lx += gs) { ctx.beginPath(); ctx.moveTo(lx, y); ctx.lineTo(lx, y + h); ctx.stroke(); }
        for (let ly = y; ly <= y + h; ly += gs) { ctx.beginPath(); ctx.moveTo(x, ly); ctx.lineTo(x + w, ly); ctx.stroke(); }
        ctx.restore();
    }

    function drawFaceGrid(box) {
        const { x, y, w, h } = paddedBox(box);
        const cx = x + w / 2, cy = y + h / 2;
        const gs = parseInt(gridSizeInput.value);
        ctx.save();
        ctx.beginPath(); ctx.ellipse(cx, cy, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.clip();
        ctx.strokeStyle = gridColor();
        ctx.lineWidth = parseFloat(lineWidthInput.value);
        for (let lx = x; lx <= x + w; lx += gs) { ctx.beginPath(); ctx.moveTo(lx, y); ctx.lineTo(lx, y + h); ctx.stroke(); }
        for (let ly = y; ly <= y + h; ly += gs) { ctx.beginPath(); ctx.moveTo(x, ly); ctx.lineTo(x + w, ly); ctx.stroke(); }
        ctx.restore();
    }

    // ---------- 수동 편집 ----------
    function getCanvasCoords(e) {
        const r = canvas.getBoundingClientRect();
        return { x: (e.clientX - r.left) * (canvas.width / r.width), y: (e.clientY - r.top) * (canvas.height / r.height) };
    }

    function setManualMode(mode) {
        manualMode = mode;
        btnAdd.classList.toggle("active", mode === "add");
        btnRemove.classList.toggle("active", mode === "remove");
        frame.classList.remove("mode-add", "mode-remove");
        if (mode === "add") { frame.classList.add("mode-add"); showStatus("드래그하여 얼굴 영역 추가", "info", 6000); }
        else if (mode === "remove") { frame.classList.add("mode-remove"); showStatus("영역을 클릭하여 제거", "info", 6000); }
        else hideStatus();
    }

    btnAdd.addEventListener("click", () => { if (originalImage) setManualMode(manualMode === "add" ? null : "add"); });
    btnRemove.addEventListener("click", () => { if (originalImage) setManualMode(manualMode === "remove" ? null : "remove"); });

    canvas.addEventListener("mousedown", (e) => {
        if (!originalImage) return;
        if (manualMode === "add") {
            isDragging = true; dragStart = getCanvasCoords(e); dragCurrent = { ...dragStart }; e.preventDefault();
        } else if (manualMode === "remove") {
            const pos = getCanvasCoords(e);
            let idx = -1;
            for (let i = faceBoxes.length - 1; i >= 0; i--) {
                const { x, y, w, h } = paddedBox(faceBoxes[i]);
                const cx = x + w / 2, cy = y + h / 2;
                const dx = (pos.x - cx) / (w / 2), dy = (pos.y - cy) / (h / 2);
                if (dx * dx + dy * dy <= 1) { idx = i; break; }
            }
            if (idx >= 0) {
                faceBoxes.splice(idx, 1); drawScene(); updateFaceCount();
                showStatus(`영역 제거됨 (${faceBoxes.length}개 남음)`, "info");
            } else { showStatus("해당 위치에 영역 없음", "error"); }
            e.preventDefault();
        }
    });

    canvas.addEventListener("mousemove", (e) => {
        if (!isDragging || manualMode !== "add") return;
        dragCurrent = getCanvasCoords(e); drawScene(); drawDragPreview(); e.preventDefault();
    });

    canvas.addEventListener("mouseup", (e) => {
        if (!isDragging || manualMode !== "add") return;
        isDragging = false;
        const end = getCanvasCoords(e);
        const x = Math.min(dragStart.x, end.x), y = Math.min(dragStart.y, end.y);
        const w = Math.abs(end.x - dragStart.x), h = Math.abs(end.y - dragStart.y);
        if (w > 10 && h > 10) {
            faceBoxes.push({ x, y, width: w, height: h }); updateFaceCount();
            showStatus(`영역 추가 (총 ${faceBoxes.length}개)`, "success");
        }
        drawScene(); dragStart = null; dragCurrent = null; e.preventDefault();
    });

    canvas.addEventListener("mouseleave", () => {
        if (isDragging) { isDragging = false; dragStart = null; dragCurrent = null; drawScene(); }
    });

    // ---------- 버튼 ----------
    btnApply.addEventListener("click", () => {
        if (!originalImage || !faceBoxes.length) return;
        drawOriginal(); faceBoxes.forEach((b) => drawFaceGrid(b)); setManualMode(null);
        showStatus(`${faceBoxes.length}개 영역에 격자 적용`, "success");
    });

    btnFace.addEventListener("click", async () => {
        if (!originalImage) return;
        btnFace.disabled = true; btnFull.disabled = true;
        try {
            await loadModels();
            showStatus("얼굴 감지 중...", "loading");
            drawOriginal();
            const det = await faceapi.detectAllFaces(canvas);
            if (!det.length) {
                faceBoxes = []; updateFaceCount();
                showStatus("얼굴 미감지 — 수동 추가하세요", "error");
            } else {
                faceBoxes = det.map((d) => ({ x: d.box.x, y: d.box.y, width: d.box.width, height: d.box.height }));
                updateFaceCount(); drawOriginal(); faceBoxes.forEach((b) => drawFaceGrid(b));
                showStatus(`${det.length}개 감지 완료`, "success");
            }
        } catch (err) { showStatus(err.message, "error", 6000); }
        btnFace.disabled = false; btnFull.disabled = false;
    });

    btnFull.addEventListener("click", () => {
        if (!originalImage) return;
        setManualMode(null); drawOriginal(); drawGrid(0, 0, canvas.width, canvas.height);
        showStatus("전체 격자 적용", "success");
    });

    btnReset.addEventListener("click", () => {
        faceBoxes = []; setManualMode(null); drawOriginal(); updateFaceCount(); hideStatus();
    });

    btnUpload.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files[0]) loadImage(e.target.files[0]);
        fileInput.value = "";
    });

    // ---------- 저장 ----------
    btnFolder.addEventListener("click", async () => {
        if (!window.showDirectoryPicker) {
            showStatus("이 브라우저는 폴더 지정을 지원하지 않습니다 (Chrome/Edge 권장)", "error", 5000);
            return;
        }
        try {
            saveDirHandle = await window.showDirectoryPicker({ mode: "readwrite" });
            folderNameEl.textContent = saveDirHandle.name;
            folderInfo.hidden = false;
            showStatus(`저장 폴더: ${saveDirHandle.name}`, "success");
        } catch (e) {
            if (e.name !== "AbortError") showStatus("폴더 지정 실패", "error");
        }
    });

    function generateFileName() {
        const d = new Date();
        const p = (n) => String(n).padStart(2, "0");
        return `autogrid_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.png`;
    }

    btnSave.addEventListener("click", async () => {
        if (!originalImage) return;
        const hadMode = manualMode;
        // 편집 모드 중이면 미리보기(점선)를 지우고 실제 격자만 그려서 저장
        if (hadMode) { drawOriginal(); faceBoxes.forEach((b) => drawFaceGrid(b)); }
        const fileName = generateFileName();
        if (saveDirHandle) {
            try {
                const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
                const fh = await saveDirHandle.getFileHandle(fileName, { create: true });
                const w = await fh.createWritable();
                await w.write(blob);
                await w.close();
                showStatus(`저장됨: ${saveDirHandle.name}/${fileName}`, "success");
            } catch {
                const a = document.createElement("a");
                a.download = fileName; a.href = canvas.toDataURL("image/png"); a.click();
            }
        } else {
            const a = document.createElement("a");
            a.download = fileName; a.href = canvas.toDataURL("image/png"); a.click();
            showStatus(`다운로드: ${fileName}`, "success");
        }
        if (hadMode) drawScene();
    });

    // ---------- 드롭존 ----------
    dropzone.addEventListener("click", () => fileInput.click());
    ["dragenter", "dragover"].forEach((ev) =>
        dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("hover"); })
    );
    ["dragleave", "drop"].forEach((ev) =>
        dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("hover"); })
    );
    dropzone.addEventListener("drop", (e) => {
        const f = e.dataTransfer.files[0];
        if (f?.type.startsWith("image/")) loadImage(f);
    });
})();
