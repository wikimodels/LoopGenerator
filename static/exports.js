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
                await fetch(`/api/export_audio/${task.filename}`, {
                    method: 'POST',
                    body: blob
                });
                
                // Reload wavesurfer
                task.ws.load(`/exports/${encodeURIComponent(task.filename)}?t=${Date.now()}`);
                
                // Keep loading overlay until ready
                task.ws.once('ready', () => {
                    task.loadingOverlay.style.display = 'none';
                    task.loadingOverlay.innerHTML = 'Analyzing...';
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

                const displayName = file.filename.replace(/\.webm$/i, '');

                card.innerHTML = `
                    <div class="export-info">
                        <div class="export-details">
                            <div class="export-filename" contenteditable="true" spellcheck="false" title="Click to rename">${displayName}</div>
                            <div class="export-meta">${formatBytes(file.size)} &bull; ${dateStr}</div>
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
