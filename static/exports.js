// exports.js

document.addEventListener('DOMContentLoaded', () => {
    const exportsList = document.getElementById('exports-list');
    const btnRefresh = document.getElementById('btn-refresh');
    const toastEl = document.getElementById('toast');
    const checkAll = document.getElementById('check-all');
    const btnBulkDelete = document.getElementById('btn-bulk-delete');
    const btnBulkDownload = document.getElementById('btn-bulk-download');

    // State
    const wavesurfers = [];
    const selectedExports = new Set();
    
    // Insert JSON Support for Exports page
    const btnImportPasted = document.getElementById('btn-import-pasted');
    const jsonPasteArea = document.getElementById('json-paste-area');
    const insertModal = document.getElementById('insert-modal');
    
    if (btnImportPasted) {
        btnImportPasted.addEventListener('click', async () => {
            const text = jsonPasteArea.value.trim();
            if (!text) return;
            try {
                const data = JSON.parse(text);
                if (!Array.isArray(data)) {
                    showToast("Error: JSON must be an array [...]");
                    return;
                }
                
                let successCount = 0;
                for (const loop of data) {
                    const res = await fetch('/api/loops', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(loop)
                    });
                    if (res.ok) successCount++;
                }
                
                showToast(`Imported ${successCount} loops!`);
                if (insertModal) insertModal.classList.add('hidden');
                jsonPasteArea.value = '';
            } catch (err) {
                showToast("Invalid JSON text");
                console.error(err);
            }
        });
    }
    
    function updateBulkActionUI() {
        const total = document.querySelectorAll('.card-checkbox').length;
        const selected = selectedExports.size;

        if (total === 0) {
            checkAll.checked = false;
            checkAll.indeterminate = false;
        } else if (selected === 0) {
            checkAll.checked = false;
            checkAll.indeterminate = false;
        } else if (selected === total) {
            checkAll.checked = true;
            checkAll.indeterminate = false;
        } else {
            checkAll.checked = false;
            checkAll.indeterminate = true;
        }

        if (selected > 0) {
            btnBulkDelete.classList.remove('hidden');
            btnBulkDownload.classList.remove('hidden');
        } else {
            btnBulkDelete.classList.add('hidden');
            btnBulkDownload.classList.add('hidden');
        }
    }
    
    // Map of cleanName -> loopData for regeneration
    const loopDataMap = new Map();

    // Queue for regeneration
    const regenQueue = [];
    let isRegenerating = false;

    function showToast(msg) {
        toastEl.textContent = msg;
        toastEl.classList.remove('hidden');
        setTimeout(() => { toastEl.classList.add('hidden'); }, 3000);
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async function loadAllLoops() {
        try {
            const [resLoops, resGolden] = await Promise.all([
                fetch('/api/loops'),
                fetch('/api/golden')
            ]);
            const [loops, golden] = await Promise.all([
                resLoops.ok ? resLoops.json() : [],
                resGolden.ok ? resGolden.json() : []
            ]);
            
            const all = [...loops, ...golden];
            all.forEach(loop => {
                const cleanName = loop.name.replace(/[^a-zA-Z0-9_-]/g, '_') || 'loop';
                loopDataMap.set(`${cleanName}.webm`, loop);
            });
        } catch (err) {
            console.error("Failed to load loop data for regeneration", err);
        }
    }

    async function processRegenQueue() {
        if (isRegenerating || regenQueue.length === 0) return;
        isRegenerating = true;
        
        const task = regenQueue.shift();
        
        // Ensure Tone.js is ready
        await initSilentSynths();
        
        const blob = await exportSingleLoopSilent(task.loopData);
        if (blob) {
            try {
                // Новый рендер пишется под именем актуального формата экспорта
                const newName = task.filename.replace(/\.(webm|wav|mp3)$/i, '') + '.' + exportExt();
                await fetch(`/api/export_audio/${newName}`, {
                    method: 'POST',
                    body: blob
                });

                // Reload wavesurfer
                task.ws.load(`/exports/${encodeURIComponent(newName)}?t=${Date.now()}`);
                
                // Keep loading overlay until ready
                task.ws.once('ready', () => {
                    task.loadingOverlay.style.display = 'none';
                    task.loadingOverlay.innerHTML = 'Analyzing...';
                });
                
                task.ws.once('error', (err) => {
                    console.error('WaveSurfer reload error:', err);
                    task.loadingOverlay.innerHTML = '<span style="color:var(--danger)">Failed to load</span>';
                });
                
                showToast(`Regenerated ${task.filename}`);
            } catch (err) {
                console.error("Failed to upload regenerated audio:", err);
                task.loadingOverlay.innerHTML = '<span style="color:var(--danger)">Failed</span>';
            }
        } else {
            task.loadingOverlay.innerHTML = '<span style="color:var(--danger)">Failed</span>';
        }

        isRegenerating = false;
        processRegenQueue();
    }

    function queueRegeneration(filename, loopData, ws, loadingOverlay) {
        loadingOverlay.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Regenerating...';
        loadingOverlay.style.display = 'flex';
        
        regenQueue.push({ filename, loopData, ws, loadingOverlay });
        showToast("Added to regeneration queue");
        processRegenQueue();
    }

    async function loadExports() {
        exportsList.innerHTML = '<div style="color: var(--text-muted);">Loading exports...</div>';
        
        // Destroy old wavesurfer instances
        wavesurfers.forEach(ws => ws.destroy());
        wavesurfers.length = 0;

        await loadAllLoops();

        try {
            const res = await fetch('/api/exports');
            if (!res.ok) throw new Error('Failed to fetch exports');
            const files = await res.json();

            if (files.length === 0) {
                exportsList.innerHTML = '<div style="color: var(--text-muted);">No exported files found.</div>';
                return;
            }

            exportsList.innerHTML = '';

            // Clear selections
            selectedExports.clear();
            updateBulkActionUI();

            files.forEach((file, index) => {
                const card = document.createElement('div');
                card.className = 'export-card';

                const dateObj = new Date(file.created_at * 1000);
                const dateStr = dateObj.toLocaleString();
                
                const hasLoopData = loopDataMap.has(file.filename);
                const regenBtnHtml = hasLoopData ? `
                    <button class="btn icon-btn regen-btn" title="Regenerate Audio">
                        <span class="material-icons">refresh</span>
                    </button>
                ` : '';

                const displayName = file.filename.replace(/\.(webm|wav|mp3)$/i, '');

                card.innerHTML = `
                    <div class="export-info">
                        <div class="export-details">
                            <div class="export-filename" contenteditable="true" spellcheck="false" title="Click to rename">${displayName}</div>
                            <div class="export-meta"><span class="export-duration">…</span></div>
                        </div>
                        <div class="export-controls">
                            <button class="btn icon-btn play-btn" title="Play/Pause">
                                <span class="material-icons">play_arrow</span>
                            </button>
                            <button class="btn icon-btn stop-btn" title="Stop">
                                <span class="material-icons">stop</span>
                            </button>
                            ${regenBtnHtml}
                            <div class="checkbox-wrapper">
                                <input type="checkbox" class="custom-checkbox card-checkbox" data-filename="${file.filename}">
                            </div>
                        </div>
                    </div>
                    <div class="waveform-container" id="waveform-${index}">
                        <div class="waveform-loading">Analyzing...</div>
                    </div>
                    <div class="trimmer-container" style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: rgba(0,0,0,0.15); border-radius: 6px; margin-top: 6px;">
                        <span class="material-icons" style="font-size: 14px; color: #64748b;" title="Trim">content_cut</span>
                        <input type="range" class="trim-start" min="0" max="100" value="0" title="Start trim" style="flex: 1; height: 4px; accent-color: #3b82f6;">
                        <input type="range" class="trim-end" min="0" max="100" value="100" title="End trim" style="flex: 1; height: 4px; accent-color: #3b82f6;">
                        <button class="btn small save-trim-btn" style="padding: 3px 8px; font-size: 11px; white-space: nowrap;"><span class="material-icons" style="font-size: 14px;">save</span></button>
                    </div>
                `;

                exportsList.appendChild(card);

                // Initialize WaveSurfer
                const ws = WaveSurfer.create({
                    container: `#waveform-${index}`,
                    waveColor: '#64748b',
                    progressColor: '#3b82f6',
                    cursorColor: '#f8fafc',
                    barWidth: 2,
                    barGap: 1,
                    barRadius: 2,
                    height: 80,
                    normalize: true,
                    url: `/exports/${encodeURIComponent(file.filename)}?t=${file.created_at}`
                });

                wavesurfers.push(ws);

                const btnPlay = card.querySelector('.play-btn');
                const btnStop = card.querySelector('.stop-btn');
                const btnRegen = card.querySelector('.regen-btn');
                const iconPlay = btnPlay.querySelector('.material-icons');
                const loadingOverlay = card.querySelector('.waveform-loading');

                ws.on('ready', () => {
                    loadingOverlay.style.display = 'none';
                    // Show track duration
                    const dur = ws.getDuration();
                    const durEl = card.querySelector('.export-duration');
                    if (durEl && dur) {
                        const m = Math.floor(dur / 60);
                        const s = Math.floor(dur % 60).toString().padStart(2, '0');
                        durEl.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
                    }
                });

                ws.on('error', (err) => {
                    console.error('WaveSurfer error on', file.filename, err);
                    loadingOverlay.innerHTML = '<span style="color:var(--danger)">Error loading audio</span>';
                });


                ws.on('play', () => {
                    iconPlay.textContent = 'pause';
                    // Pause all others
                    wavesurfers.forEach(otherWs => {
                        if (otherWs !== ws && otherWs.isPlaying()) {
                            otherWs.pause();
                        }
                    });
                });

                ws.on('pause', () => {
                    iconPlay.textContent = 'play_arrow';
                });

                ws.on('finish', () => {
                    iconPlay.textContent = 'play_arrow';
                    ws.stop();
                });

                btnPlay.addEventListener('click', () => {
                    ws.playPause();
                });

                btnStop.addEventListener('click', () => {
                    ws.stop();
                    iconPlay.textContent = 'play_arrow';
                });
                
                if (btnRegen) {
                    btnRegen.addEventListener('click', () => {
                        const loopData = loopDataMap.get(file.filename);
                        if (loopData) {
                            queueRegeneration(file.filename, loopData, ws, loadingOverlay);
                        }
                    });
                }

                // Checkbox logic
                const checkbox = card.querySelector('.card-checkbox');
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        selectedExports.add(file.filename);
                        card.classList.add('selected');
                    } else {
                        selectedExports.delete(file.filename);
                        card.classList.remove('selected');
                    }
                    updateBulkActionUI();
                });

                // Trimmer Logic (compact)
                const trimStart = card.querySelector('.trim-start');
                const trimEnd = card.querySelector('.trim-end');
                const btnSaveTrim = card.querySelector('.save-trim-btn');
                const waveformContainer = card.querySelector('.waveform-container');
                // Add trim overlay lines
                let trimOverlay = null;
                if (waveformContainer) {
                    trimOverlay = document.createElement('div');
                    trimOverlay.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none;';
                    trimOverlay.innerHTML = '<div class="trim-line trim-start-line" style="position: absolute; top: 0; bottom: 0; width: 2px; background: rgba(59,130,246,0.8); left: 0%;"></div><div class="trim-line trim-end-line" style="position: absolute; top: 0; bottom: 0; width: 2px; background: rgba(59,130,246,0.8); left: 100%;"></div>';
                    waveformContainer.style.position = 'relative';
                    waveformContainer.appendChild(trimOverlay);
                }
                if (trimStart && trimEnd && btnSaveTrim) {
                    const updateTrimVisual = () => {
                        const start = parseInt(trimStart.value);
                        const end = parseInt(trimEnd.value);
                        // Ensure start < end
                        if (start >= end) {
                            if (document.activeElement === trimStart) trimEnd.value = Math.min(100, start + 1);
                            else trimStart.value = Math.max(0, end - 1);
                        }
                        if (trimOverlay) {
                            trimOverlay.querySelector('.trim-start-line').style.left = trimStart.value + '%';
                            trimOverlay.querySelector('.trim-end-line').style.left = trimEnd.value + '%';
                        }
                    };
                    trimStart.addEventListener('input', updateTrimVisual);
                    trimEnd.addEventListener('input', updateTrimVisual);
                    btnSaveTrim.addEventListener('click', async () => {
                        const duration = ws.getDuration();
                        if (!duration) return;
                        const startPct = parseInt(trimStart.value) / 100;
                        const endPct = parseInt(trimEnd.value) / 100;
                        if (startPct >= endPct) return;
                        btnSaveTrim.disabled = true;
                        btnSaveTrim.innerHTML = '<span class="material-icons" style="font-size: 14px; animation: spin 1s linear infinite;">sync</span>';
                        try {
                            const buffer = ws.getDecodedData();
                            if (!buffer) throw new Error('No audio data');
                            const sr = buffer.sampleRate;
                            const startSample = Math.floor(buffer.length * startPct);
                            const endSample = Math.floor(buffer.length * endPct);
                            const newLength = endSample - startSample;
                            const trimmedBuffer = new AudioContext().createBuffer(buffer.numberOfChannels, newLength, sr);
                            for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
                                trimmedBuffer.getChannelData(ch).set(buffer.getChannelData(ch).subarray(startSample, endSample));
                            }
                            // Encode as WAV
                            const wavBlob = await new Promise(resolve => {
                                const worker = new Worker(URL.createObjectURL(new Blob([`
                                    self.onmessage = e => {
                                        const {buf, sr} = e.data;
                                        const numCh = buf.length;
                                        const len = buf[0].length;
                                        const ab = new ArrayBuffer(44 + len * numCh * 2);
                                        const view = new DataView(ab);
                                        const writeStr = (off, s) => { for(let i=0;i<s.length;i++) view.setUint8(off+i, s.charCodeAt(i)); };
                                        writeStr(0, 'RIFF'); view.setUint32(4, 36 + len * numCh * 2, true); writeStr(8, 'WAVE');
                                        writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
                                        view.setUint16(22, numCh, true); view.setUint32(24, sr, true);
                                        view.setUint32(28, sr * numCh * 2, true); view.setUint16(32, numCh * 2, true); view.setUint16(34, 16, true);
                                        writeStr(36, 'data'); view.setUint32(40, len * numCh * 2, true);
                                        let off2 = 44;
                                        for(let i=0;i<len;i++) for(let ch=0; ch<numCh; ch++) {
                                            let s = Math.max(-1, Math.min(1, buf[ch][i]));
                                            view.setInt16(off2, s < 0 ? s * 0x8000 : s * 0x7FFF, true); off2+=2;
                                        }
                                        self.postMessage(ab, [ab]);
                                    }
                                `], {type: 'application/javascript'})));
                                const chData = [];
                                for(let c=0;c<trimmedBuffer.numberOfChannels;c++) chData.push(trimmedBuffer.getChannelData(c).slice());
                                worker.postMessage({buf: chData, sr}, []);
                                worker.onmessage = e => resolve(new Blob([e.data], {type: 'audio/wav'}));
                            });
                            const res = await fetch(`/api/exports/trim/${encodeURIComponent(file.filename)}`, { method: 'POST', body: wavBlob, headers: { 'Content-Type': 'audio/wav' } });
                            if (!res.ok) throw new Error('Trim save failed');
                            // Reload card or show success
                            const data = await res.json();
                            ws.load(`/exports/${encodeURIComponent(data.filename)}?t=${Date.now()}`);
                            trimStart.value = 0; trimEnd.value = 100;
                        } catch (err) {
                            console.error('Trim failed', err);
                            alert('Trim failed: ' + err.message);
                        } finally {
                            btnSaveTrim.disabled = false;
                            btnSaveTrim.innerHTML = '<span class="material-icons" style="font-size: 14px;">save</span>';
                        }
                    });
                }

                // Inline Rename Logic
                const filenameEl = card.querySelector('.export-filename');
                filenameEl.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        filenameEl.blur();
                    }
                });
                
                filenameEl.addEventListener('blur', async () => {
                    let newName = filenameEl.textContent.trim().replace(/\s+/g, '_');
                    if (!newName || newName === displayName) {
                        filenameEl.textContent = displayName;
                        return;
                    }
                    
                    try {
                        const res = await fetch(`/api/export_audio/${file.filename}/rename`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ new_filename: newName })
                        });
                        
                        if (res.ok) {
                            const data = await res.json();
                            showToast(`Renamed to ${data.new_filename}`);
                            loadExports(); // refresh everything
                        } else {
                            throw new Error("Rename failed");
                        }
                    } catch (err) {
                        console.error(err);
                        filenameEl.textContent = displayName;
                        showToast("Failed to rename file");
                    }
                });
            });

        } catch (err) {
            console.error(err);
            exportsList.innerHTML = '<div style="color: var(--danger);">Error loading exports. Check console.</div>';
            showToast("Failed to load exports");
        }
    }

    btnRefresh.addEventListener('click', loadExports);

    // Master Checkbox
    checkAll.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        const checkboxes = document.querySelectorAll('.card-checkbox');
        
        checkboxes.forEach(cb => {
            cb.checked = isChecked;
            const filename = cb.dataset.filename;
            const card = cb.closest('.export-card');
            if (isChecked) {
                selectedExports.add(filename);
                card.classList.add('selected');
            } else {
                selectedExports.delete(filename);
                card.classList.remove('selected');
            }
        });
        updateBulkActionUI();
    });

    // Bulk Delete
    btnBulkDelete.addEventListener('click', async () => {
        if (selectedExports.size === 0) return;
        if (!confirm(`Delete ${selectedExports.size} files?`)) return;

        btnBulkDelete.disabled = true;
        btnBulkDelete.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Deleting...';

        try {
            const filesToDelete = Array.from(selectedExports);
            for (const filename of filesToDelete) {
                await fetch(`/api/export_audio/${filename}`, { method: 'DELETE' });
            }
            showToast(`Deleted ${filesToDelete.length} files`);
            loadExports();
        } catch (err) {
            console.error(err);
            showToast("Failed to delete some files");
        } finally {
            btnBulkDelete.disabled = false;
            btnBulkDelete.innerHTML = '<span class="material-icons">delete</span> Delete';
        }
    });

    // Bulk Download
    btnBulkDownload.addEventListener('click', async () => {
        if (selectedExports.size === 0) return;

        btnBulkDownload.disabled = true;
        btnBulkDownload.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Downloading...';

        try {
            const res = await fetch('/api/export_audio/local_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filenames: Array.from(selectedExports) })
            });
            
            if (res.ok) {
                const data = await res.json();
                showToast(`Saved to ${data.destination}`);
                // Deselect after download
                checkAll.checked = false;
                checkAll.dispatchEvent(new Event('change'));
            } else {
                throw new Error("Download failed");
            }
        } catch (err) {
            console.error(err);
            showToast("Failed to copy files locally");
        } finally {
            btnBulkDownload.disabled = false;
            btnBulkDownload.innerHTML = '<span class="material-icons">download</span> Download';
        }
    });

    // Initial load
    loadExports();
});
