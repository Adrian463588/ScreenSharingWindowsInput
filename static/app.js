// TabSign - Tablet Client Application (Upgraded with Smart Click & Deadzone Filter)
(function () {
    const screenCanvas = document.getElementById('screen-canvas');
    const screenCtx = screenCanvas.getContext('2d');
    const inkCanvas = document.getElementById('ink-canvas');
    const inkCtx = inkCanvas.getContext('2d');
    const selectionBox = document.getElementById('selection-box');
    const viewport = document.getElementById('viewport');
    
    // UI Elements
    const connBadge = document.getElementById('conn-badge');
    const fpsBadge = document.getElementById('fps-badge');
    const btnModePen = document.getElementById('btn-mode-pen');
    const btnModeClick = document.getElementById('btn-mode-click');
    const btnModeNav = document.getElementById('btn-mode-nav');
    const btnZoomBox = document.getElementById('btn-zoom-box');
    const btnZoomReset = document.getElementById('btn-zoom-reset');
    const btnClearSig = document.getElementById('btn-clear-sig');
    const btnUndo = document.getElementById('btn-undo');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    const toolbar = document.getElementById('toolbar');
    const dragHandle = document.getElementById('drag-handle');
    const toast = document.getElementById('toast');

    // State Variables
    let ws = null;
    let mode = 'pen'; // 'pen', 'click', 'nav', 'zoom_select'
    
    // ROI: normalized bounds [u0, v0, u1, v1]
    let roi = { u0: 0, v0: 0, u1: 1, v1: 1 };
    
    // Frame storage & display rect
    let imgBitmap = null;
    let displayRect = { x: 0, y: 0, width: 0, height: 0 };
    
    // FPS counter
    let frameCount = 0;
    let lastFpsUpdate = performance.now();

    // Multi-touch & gesture tracking
    const activePointers = new Map();
    let isDrawing = false;
    let hasSentDown = false;
    let pointerStart = { x: 0, y: 0, time: 0, u: 0, v: 0 };
    let longPressTimer = null;
    let lastScrollY = 0;
    let inkPoints = [];

    // Notification toast
    function showToast(msg, duration = 2000) {
        toast.textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), duration);
    }

    // Resize canvases to match viewport
    function resizeCanvases() {
        const dpr = window.devicePixelRatio || 1;
        const w = viewport.clientWidth;
        const h = viewport.clientHeight;

        screenCanvas.width = w * dpr;
        screenCanvas.height = h * dpr;
        inkCanvas.width = w * dpr;
        inkCanvas.height = h * dpr;

        screenCtx.scale(dpr, dpr);
        inkCtx.scale(dpr, dpr);

        renderCurrentFrame();
    }
    window.addEventListener('resize', resizeCanvases);

    // WebSocket Setup
    function connectWebSocket() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/ws/client`;
        
        ws = new WebSocket(url);
        ws.binaryType = 'blob';

        ws.onopen = () => {
            connBadge.textContent = '● Terhubung';
            connBadge.className = 'badge badge-connected';
            showToast('Terhubung ke PC Windows');
        };

        ws.onclose = () => {
            connBadge.textContent = '● Terputus';
            connBadge.className = 'badge badge-disconnected';
            setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = () => {
            connBadge.textContent = '● Galat Koneksi';
            connBadge.className = 'badge badge-disconnected';
        };

        ws.onmessage = async (e) => {
            if (e.data instanceof Blob) {
                try {
                    const bmp = await createImageBitmap(e.data);
                    if (imgBitmap) imgBitmap.close();
                    imgBitmap = bmp;
                    renderCurrentFrame();
                    
                    frameCount++;
                    const now = performance.now();
                    if (now - lastFpsUpdate >= 1000) {
                        const fps = Math.round((frameCount * 1000) / (now - lastFpsUpdate));
                        fpsBadge.textContent = `${fps} FPS`;
                        frameCount = 0;
                        lastFpsUpdate = now;
                    }
                } catch (err) {
                    console.error('Frame decode error:', err);
                }
            } else {
                try {
                    const data = JSON.parse(e.data);
                    if (data.type === 'toast') showToast(data.message);
                } catch (err) {}
            }
        };
    }

    // Render incoming video frame with ROI
    function renderCurrentFrame() {
        if (!imgBitmap) return;

        const cw = viewport.clientWidth;
        const ch = viewport.clientHeight;

        screenCtx.fillStyle = '#000000';
        screenCtx.fillRect(0, 0, cw, ch);

        const sw = imgBitmap.width;
        const sh = imgBitmap.height;
        const sx = roi.u0 * sw;
        const sy = roi.v0 * sh;
        const sCropW = (roi.u1 - roi.u0) * sw;
        const sCropH = (roi.v1 - roi.v0) * sh;

        const sAspect = sCropW / sCropH;
        const cAspect = cw / ch;

        let dw, dh, dx, dy;
        if (cAspect > sAspect) {
            dh = ch;
            dw = ch * sAspect;
            dx = (cw - dw) / 2;
            dy = 0;
        } else {
            dw = cw;
            dh = cw / sAspect;
            dx = 0;
            dy = (ch - dh) / 2;
        }

        displayRect = { x: dx, y: dy, width: dw, height: dh };
        screenCtx.drawImage(imgBitmap, sx, sy, sCropW, sCropH, dx, dy, dw, dh);
    }

    // Coordinate Mapping: Viewport -> Original Normalized [0.0, 1.0] Desktop Screen
    function clientToNormalizedCoords(clientX, clientY) {
        if (displayRect.width === 0 || displayRect.height === 0) return null;

        const rx = (clientX - displayRect.x) / displayRect.width;
        const ry = (clientY - displayRect.y) / displayRect.height;

        if (rx < 0 || rx > 1 || ry < 0 || ry > 1) return null;

        const u = roi.u0 + rx * (roi.u1 - roi.u0);
        const v = roi.v0 + ry * (roi.v1 - roi.v0);

        return {
            u: Math.max(0.0, Math.min(1.0, u)),
            v: Math.max(0.0, Math.min(1.0, v))
        };
    }

    function sendInput(payload) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(payload));
        }
    }

    // Instant Local Ink
    function startLocalInk(x, y, pressure) {
        inkCtx.beginPath();
        inkCtx.lineCap = 'round';
        inkCtx.lineJoin = 'round';
        inkCtx.strokeStyle = '#1d4ed8';
        const width = 2.5 * (0.4 + (pressure || 0.5) * 1.2);
        inkCtx.lineWidth = width;
        inkCtx.moveTo(x, y);
        inkPoints = [{ x, y, pressure }];
    }

    function addLocalInk(x, y, pressure) {
        if (inkPoints.length === 0) return;
        const p1 = inkPoints[inkPoints.length - 1];
        const midX = (p1.x + x) / 2;
        const midY = (p1.y + y) / 2;
        const width = 2.5 * (0.4 + (pressure || 0.5) * 1.2);
        inkCtx.lineWidth = width;
        inkCtx.quadraticCurveTo(p1.x, p1.y, midX, midY);
        inkCtx.stroke();
        inkPoints.push({ x, y, pressure });
    }

    function clearLocalInk() {
        inkPoints = [];
        inkCtx.clearRect(0, 0, viewport.clientWidth, viewport.clientHeight);
    }

    // Visual Ripple on Tap/Click
    function showClickFeedback(x, y) {
        inkCtx.save();
        inkCtx.beginPath();
        inkCtx.arc(x, y, 16, 0, Math.PI * 2);
        inkCtx.fillStyle = 'rgba(56, 189, 248, 0.4)';
        inkCtx.fill();
        inkCtx.strokeStyle = 'rgba(56, 189, 248, 0.8)';
        inkCtx.lineWidth = 2;
        inkCtx.stroke();
        inkCtx.restore();
        setTimeout(clearLocalInk, 120);
    }

    // Pointer Event Handlers
    inkCanvas.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        inkCanvas.setPointerCapture(e.pointerId);
        activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY, type: e.pointerType });

        // Two-Finger Gesture: Auto-detect Scroll without switching mode
        if (activePointers.size === 2) {
            cancelLongPress();
            isDrawing = false;
            hasSentDown = false;
            clearLocalInk();
            const pts = Array.from(activePointers.values());
            lastScrollY = (pts[0].y + pts[1].y) / 2;
            return;
        }

        const coords = clientToNormalizedCoords(e.clientX, e.clientY);
        if (!coords) return;

        pointerStart = {
            x: e.clientX,
            y: e.clientY,
            time: performance.now(),
            u: coords.u,
            v: coords.v,
            pointerType: e.pointerType,
            pressure: e.pressure > 0 ? e.pressure : 0.5
        };
        hasSentDown = false;
        isDrawing = false;

        // Long Press -> Right Click
        cancelLongPress();
        longPressTimer = setTimeout(() => {
            if (activePointers.size === 1 && !isDrawing) {
                sendInput({
                    type: 'click',
                    x: pointerStart.u,
                    y: pointerStart.v,
                    button: 'right'
                });
                showToast('Klik Kanan');
                showClickFeedback(pointerStart.x, pointerStart.y);
                hasSentDown = false;
            }
        }, 550);
    });

    inkCanvas.addEventListener('pointermove', (e) => {
        e.preventDefault();
        if (!activePointers.has(e.pointerId)) return;
        activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY, type: e.pointerType });

        // Two-Finger Scroll
        if (activePointers.size >= 2) {
            const pts = Array.from(activePointers.values());
            const currentY = (pts[0].y + pts[1].y) / 2;
            const deltaY = currentY - lastScrollY;
            if (Math.abs(deltaY) > 6) {
                const coords = clientToNormalizedCoords(e.clientX, e.clientY) || { u: 0.5, v: 0.5 };
                sendInput({
                    type: 'scroll',
                    x: coords.u,
                    y: coords.v,
                    delta: deltaY > 0 ? 1 : -1
                });
                lastScrollY = currentY;
            }
            return;
        }

        const dist = Math.hypot(e.clientX - pointerStart.x, e.clientY - pointerStart.y);

        // Cancel long-press once moved
        if (dist > 8) cancelLongPress();

        if (mode === 'zoom_select') {
            const x0 = Math.min(pointerStart.x, e.clientX);
            const y0 = Math.min(pointerStart.y, e.clientY);
            const w = Math.abs(e.clientX - pointerStart.x);
            const h = Math.abs(e.clientY - pointerStart.y);
            selectionBox.style.left = `${x0}px`;
            selectionBox.style.top = `${y0}px`;
            selectionBox.style.width = `${w}px`;
            selectionBox.style.height = `${h}px`;
            selectionBox.classList.remove('hidden');
            return;
        }

        if (mode === 'nav') {
            const deltaY = e.clientY - pointerStart.y;
            if (Math.abs(deltaY) > 8) {
                const coords = clientToNormalizedCoords(e.clientX, e.clientY) || { u: 0.5, v: 0.5 };
                sendInput({
                    type: 'scroll',
                    x: coords.u,
                    y: coords.v,
                    delta: deltaY > 0 ? 1 : -1
                });
                pointerStart.y = e.clientY;
            }
            return;
        }

        if (mode === 'click') {
            // Click mode only clicks on pointerup, no drag
            return;
        }

        // Mode Pen (Tanda Tangan)
        if (mode === 'pen') {
            // DEADZONE FILTER: Don't start drawing or sending drag until moved >= 6px
            if (dist < 6) return;

            const coords = clientToNormalizedCoords(e.clientX, e.clientY);
            if (!coords) return;

            const pressure = e.pressure > 0 ? e.pressure : 0.5;

            if (!hasSentDown) {
                // First movement beyond deadzone: send genuine down event
                hasSentDown = true;
                isDrawing = true;
                startLocalInk(pointerStart.x, pointerStart.y, pointerStart.pressure);
                sendInput({
                    type: 'down',
                    x: pointerStart.u,
                    y: pointerStart.v,
                    pressure: pointerStart.pressure,
                    button: 'left'
                });
            }

            addLocalInk(e.clientX, e.clientY, pressure);
            sendInput({
                type: 'drag',
                x: coords.u,
                y: coords.v,
                pressure: pressure
            });
        }
    });

    const endPointerHandler = (e) => {
        e.preventDefault();
        cancelLongPress();
        activePointers.delete(e.pointerId);

        try {
            inkCanvas.releasePointerCapture(e.pointerId);
        } catch (err) {}

        if (mode === 'zoom_select') {
            selectionBox.classList.add('hidden');
            const x0 = Math.min(pointerStart.x, e.clientX);
            const y0 = Math.min(pointerStart.y, e.clientY);
            const x1 = Math.max(pointerStart.x, e.clientX);
            const y1 = Math.max(pointerStart.y, e.clientY);

            if (x1 - x0 > 40 && y1 - y0 > 40) {
                const c0 = clientToNormalizedCoords(x0, y0);
                const c1 = clientToNormalizedCoords(x1, y1);
                if (c0 && c1) {
                    roi = {
                        u0: Math.min(c0.u, c1.u),
                        v0: Math.min(c0.v, c1.v),
                        u1: Math.max(c0.u, c1.u),
                        v1: Math.max(c0.v, c1.v)
                    };
                    renderCurrentFrame();
                    showToast('Kotak tanda tangan diperbesar!');
                }
            }
            setMode('pen');
            return;
        }

        if (mode === 'nav') return;

        const dist = Math.hypot(e.clientX - pointerStart.x, e.clientY - pointerStart.y);
        const duration = performance.now() - pointerStart.time;

        // TRUE TAP / CLICK DETECTED (Movement < 7px and duration < 400ms)
        if (mode === 'click' || (!hasSentDown && dist < 7 && duration < 400)) {
            const coords = clientToNormalizedCoords(e.clientX, e.clientY) || { u: pointerStart.u, v: pointerStart.v };
            sendInput({
                type: 'click',
                x: coords.u,
                y: coords.v,
                button: 'left'
            });
            showClickFeedback(e.clientX, e.clientY);
            clearLocalInk();
            return;
        }

        // End of regular drag/drawing stroke
        if (hasSentDown) {
            hasSentDown = false;
            isDrawing = false;
            const coords = clientToNormalizedCoords(e.clientX, e.clientY) || { u: pointerStart.u, v: pointerStart.v };
            sendInput({
                type: 'up',
                x: coords.u,
                y: coords.v,
                button: 'left'
            });
            setTimeout(clearLocalInk, 250);
        }
    };

    inkCanvas.addEventListener('pointerup', endPointerHandler);
    inkCanvas.addEventListener('pointercancel', endPointerHandler);

    function cancelLongPress() {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }

    // Mode Switcher
    function setMode(newMode) {
        mode = newMode;
        btnModePen.classList.toggle('btn-active', mode === 'pen');
        btnModeClick.classList.toggle('btn-active', mode === 'click');
        btnModeNav.classList.toggle('btn-active', mode === 'nav');
        btnZoomBox.classList.toggle('btn-active', mode === 'zoom_select');

        if (mode === 'pen') showToast('Mode Tanda Tangan (Sentuh/S-Pen)');
        else if (mode === 'click') showToast('Mode Klik / Buka Menu & Taskbar');
        else if (mode === 'nav') showToast('Mode Scroll Halaman Web');
        else if (mode === 'zoom_select') showToast('Tarik kotak untuk memperbesar');
    }

    btnModePen.addEventListener('click', () => setMode('pen'));
    btnModeClick.addEventListener('click', () => setMode('click'));
    btnModeNav.addEventListener('click', () => setMode('nav'));
    btnZoomBox.addEventListener('click', () => setMode('zoom_select'));

    btnZoomReset.addEventListener('click', () => {
        roi = { u0: 0, v0: 0, u1: 1, v1: 1 };
        renderCurrentFrame();
        clearLocalInk();
        showToast('Tampilan dikembalikan penuh');
    });

    // Clear Signature Button (Hapus)
    btnClearSig.addEventListener('click', () => {
        clearLocalInk();
        // Send Undo and Escape to clear the signature in web modal
        sendInput({ type: 'undo' });
        sendInput({ type: 'esc' });
        showToast('Tanda tangan dihapus/direset');
    });

    // Undo action (Ctrl+Z)
    btnUndo.addEventListener('click', () => {
        sendInput({ type: 'undo' });
        clearLocalInk();
        showToast('Undo dikirim ke PC');
    });

    // Fullscreen toggle
    btnFullscreen.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    });

    // Draggable Toolbar Logic
    let isDraggingToolbar = false;
    let dragOffset = { x: 0, y: 0 };

    dragHandle.addEventListener('pointerdown', (e) => {
        isDraggingToolbar = true;
        dragOffset = {
            x: e.clientX - toolbar.offsetLeft,
            y: e.clientY - toolbar.offsetTop
        };
        toolbar.classList.remove('toolbar-top');
        dragHandle.style.cursor = 'grabbing';
        e.stopPropagation();
    });

    window.addEventListener('pointermove', (e) => {
        if (!isDraggingToolbar) return;
        const x = Math.max(10, Math.min(window.innerWidth - toolbar.offsetWidth - 10, e.clientX - dragOffset.x));
        const y = Math.max(10, Math.min(window.innerHeight - toolbar.offsetHeight - 10, e.clientY - dragOffset.y));
        toolbar.style.left = `${x}px`;
        toolbar.style.top = `${y}px`;
        toolbar.style.transform = 'none';
    });

    window.addEventListener('pointerup', () => {
        if (isDraggingToolbar) {
            isDraggingToolbar = false;
            dragHandle.style.cursor = 'grab';
        }
    });

    // Initialize
    resizeCanvases();
    connectWebSocket();
})();
