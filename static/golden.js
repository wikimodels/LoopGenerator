let loopsData = [];
let filteredLoops = [];
let loopMeta = {};   // { filename: { rating, tags, notes } }
let selectedLoops = new Set();
let isAudioInitialized = false;
let currentSearchQuery = '';
let currentStarFilter = 0;

// Audio state
let synths = {};
let silentSynths = {};
let recorder = null;
let exportLimiter = null;
let exportRecorderNode = null;
let activeSequence = null;
let activeLoopName = null;
let activeItemEl = null; // DOM element of the currently active catalog-item
let fft = null;       // native AnalyserNode
let eqBars = [];
let animFrameId = null;
let playbackId = 0;
let loopBpmMap = {};      // { filename: bpmValue } — per-track BPM override
let exportCancelled = false;

// Modal specific state
let isPreviewing = false;
let previewSequence = null;

// DOM Elements
const catalogList = document.getElementById('catalog-list');
const checkAll = document.getElementById('check-all');
const selectedCount = document.getElementById('selected-count');
const btnDownload = document.getElementById('btn-download-selected');
const btnDownloadJson = document.getElementById('btn-download-json');
const btnInsertJson = document.getElementById('btn-insert-json');
const btnMergeDownload = document.getElementById('btn-merge-download');
const btnDelete = document.getElementById('btn-delete-selected');
const progressContainer = document.getElementById('progress-container');
const progressText = document.getElementById('progress-text');
const progressFill = document.getElementById('progress-fill');
const toastEl = document.getElementById('toast');

// Export Audio Overlay Elements
const btnExportAudio = document.getElementById('btn-export-audio');
const exportOverlay = document.getElementById('export-overlay');
const exportCurrentTrack = document.getElementById('export-current-track');
const exportProgressFill = document.getElementById('export-progress-fill');
const exportProgressPct = document.getElementById('export-progress-pct');
const exportTrackList = document.getElementById('export-track-list');
const btnCancelExport = document.getElementById('btn-cancel-export');

// Modal Elements
const mergeModal = document.getElementById('merge-modal');
const btnCloseMergeModal = document.getElementById('btn-close-merge-modal');
const mergeTrackList = document.getElementById('merge-track-list');
const mergeBpmSlider = document.getElementById('merge-bpm-slider');
const mergeBpmVal = document.getElementById('merge-bpm-val');
const btnMergePreview = document.getElementById('btn-merge-preview');
const mergePreviewIcon = document.getElementById('merge-preview-icon');
const btnMergeConfirmDownload = document.getElementById('btn-merge-confirm-download');
const mergeProgressContainer = document.getElementById('merge-progress-container');
const mergeProgressText = document.getElementById('merge-progress-text');
const mergeProgressFill = document.getElementById('merge-progress-fill');

// Insert JSON Modal Elements
const insertModal = document.getElementById('insert-modal');
const btnCloseInsert = document.getElementById('btn-close-insert');
const btnImportPasted = document.getElementById('btn-import-pasted');
const jsonPasteArea = document.getElementById('json-paste-area');

// Bank of words for poetic loop names
const poeticWords = {
    actions: ["Echoes", "Dancing", "Lost", "Shadows", "Rhythm", "Whispers", "Memories", "Footsteps", "Dreams", "Visions", "Signals", "Voices", "Secrets", "Illusions", "Sparks", "Fragments", "Awakening", "Journey", "Falling", "Floating", "Drifting", "Running", "Hiding", "Waiting", "Breathing", "Fading", "Glowing", "Vibrations", "Pulses", "Glimmers"],
    prepositions: ["In", "Of", "Under", "Beyond", "Through", "Across", "Within", "Towards", "Above", "Below"],
    places: ["Future", "Dark", "Quantum Space", "Neon", "Night", "Abyss", "Void", "City", "Ocean", "Forest", "Desert", "Cosmos", "Galaxy", "Simulation", "Matrix", "Storm", "Silence", "Nebula", "Horizon", "Twilight", "Dawn", "Dusk", "Midnight", "Unknown", "Aether", "Rain", "Mist", "Shadows", "Light", "Eternity"]
};

function generatePoeticName() {
    const action = poeticWords.actions[Math.floor(Math.random() * poeticWords.actions.length)];
    const prep = poeticWords.prepositions[Math.floor(Math.random() * poeticWords.prepositions.length)];
    const place = poeticWords.places[Math.floor(Math.random() * poeticWords.places.length)];
    
    return `${action} ${prep} ${place}`;
}

// --- Initialization ---
async function init() {
    await fetchMeta();
    await fetchLoops();
    
    // Generate 72 bars dynamically
    const headerEq = document.getElementById('header-eq');
    headerEq.innerHTML = '';
    for(let i = 0; i < 72; i++) {
        const bar = document.createElement('div');
        bar.className = 'eq-bar';
        headerEq.appendChild(bar);
    }
    
    const mergeEq = document.getElementById('merge-eq');
    if (mergeEq) {
        mergeEq.innerHTML = '';
        for(let i = 0; i < 72; i++) {
            const bar = document.createElement('div');
            bar.className = 'eq-bar';
            mergeEq.appendChild(bar);
        }
    }
    
    eqBars = Array.from(document.querySelectorAll('.eq-bar'));

    // Generate overlay EQ bars (CSS-animated, independent of audio)
    const exportEqEl = document.getElementById('export-eq');
    if (exportEqEl) {
        exportEqEl.innerHTML = '';
        const barHeights = [8,18,26,14,28,10,22,16,28,12,24,20,8,26,18,28,14,22,10,24,16,28,12,20];
        const barDurs   = [0.5,0.7,0.4,0.85,0.6,0.9,0.45,0.65,0.55,0.75,0.5,0.8,0.6,0.4,0.7,0.5,0.85,0.65,0.75,0.45,0.6,0.8,0.55,0.7];
        barHeights.forEach((h, i) => {
            const bar = document.createElement('div');
            bar.className = 'export-eq-bar';
            bar.style.setProperty('--h', `${h}px`);
            bar.style.setProperty('--dur', `${barDurs[i]}s`);
            exportEqEl.appendChild(bar);
        });
    }
    
    setupEventListeners();
}

async function fetchMeta() {
    try {
        const res = await fetch('/api/meta');
        loopMeta = await res.json();
    } catch(e) {
        loopMeta = {};
    }
}

async function setRating(filename, rating) {
    // Toggle off if clicking same star
    const current = (loopMeta[filename] || {}).rating || 0;
    const newRating = current === rating ? 0 : rating;
    loopMeta[filename] = { ...(loopMeta[filename] || {}), rating: newRating };
    try {
        await fetch(`/api/meta/${filename}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rating: newRating })
        });
        // If rating dropped below 5, track moved back to loops/ — refresh golden list
        if (newRating !== 5) {
            await fetchLoops();
        }
    } catch(e) { console.error('Failed to save rating', e); }
    return newRating;
}

function buildStarRating(filename, currentRating) {
    const container = document.createElement('div');
    container.className = 'star-rating';
    for (let i = 1; i <= 5; i++) {
        const star = document.createElement('span');
        star.className = 'star' + (i <= currentRating ? ' filled' : '');
        star.textContent = '★';
        star.dataset.value = i;
        star.addEventListener('mouseenter', () => {
            container.querySelectorAll('.star').forEach((s, idx) => {
                s.classList.toggle('hovered', idx < i);
            });
        });
        star.addEventListener('mouseleave', () => {
            container.querySelectorAll('.star').forEach(s => s.classList.remove('hovered'));
        });
        star.addEventListener('click', async (e) => {
            e.stopPropagation();
            const newR = await setRating(filename, i);
            container.querySelectorAll('.star').forEach((s, idx) => {
                s.classList.toggle('filled', idx < newR);
            });
        });
        container.appendChild(star);
    }
    return container;
}

async function initAudioContext() {
    if (isAudioInitialized) return;
    await Tone.start();

    // Native AnalyserNode — just listens to whatever plays, never touches the signal chain
    const ctx = Tone.getContext().rawContext;
    fft = ctx.createAnalyser();
    fft.fftSize = 256;
    fft.smoothingTimeConstant = 0.8;
    Tone.getDestination().output.connect(fft);

    // Normal synths — plain .toDestination(), no routing magic
    synths = {
        synth: new Tone.PolySynth(Tone.Synth).toDestination(),
        amSynth: new Tone.PolySynth(Tone.AMSynth).toDestination(),
        fmSynth: new Tone.PolySynth(Tone.FMSynth).toDestination(),
        piano: new Tone.Sampler({
            urls: { "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3" },
            release: 1,
            baseUrl: "https://tonejs.github.io/audio/salamander/"
        }).toDestination(),
        drums: createDrumKit()
    };

    // Silent synths for background rendering (export).
    recorder = new Tone.Recorder();
    exportLimiter = new Tone.Limiter(-2);
    
    // Dedicated node for the recorder (we disconnect/reconnect this one)
    exportRecorderNode = new Tone.Gain(1);
    exportLimiter.connect(exportRecorderNode);
    exportRecorderNode.connect(recorder);

    // DUMMY PATH TO DESTINATION: 
    // This keeps the AudioContext alive and running in real-time even when 
    // the browser tab is in the background. It outputs 100% silence.
    const silentPath = new Tone.Gain(0).toDestination();
    exportLimiter.connect(silentPath);

    silentSynths = {
        synth: new Tone.PolySynth(Tone.Synth).connect(exportLimiter),
        amSynth: new Tone.PolySynth(Tone.AMSynth).connect(exportLimiter),
        fmSynth: new Tone.PolySynth(Tone.FMSynth).connect(exportLimiter),
        piano: new Tone.Sampler({
            urls: { "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3" },
            release: 1,
            baseUrl: "https://tonejs.github.io/audio/salamander/"
        }).connect(exportLimiter),
        drums: createDrumKit(exportLimiter)
    };

    isAudioInitialized = true;
}

function createDrumKit(outputNode) {
    const dest = outputNode || Tone.getDestination();
    const mk = (s) => { s.connect(dest); return s; };

    return {
        triggerAttackRelease: (note, duration, time, velocity) => {
            switch(note) {
                case "Kick":    mk(new Tone.MembraneSynth()).triggerAttackRelease("C2", duration, time, velocity); break;
                case "Snare":   mk(new Tone.NoiseSynth({ noise:{type:"white"}, envelope:{attack:0.001,decay:0.2,sustain:0} })).triggerAttackRelease(duration, time, velocity); break;
                case "HiHat":   mk(new Tone.NoiseSynth({ noise:{type:"white"}, envelope:{attack:0.001,decay:0.05,sustain:0} })).triggerAttackRelease(duration, time, velocity); break;
                case "OpenHat": mk(new Tone.NoiseSynth({ noise:{type:"white"}, envelope:{attack:0.01,decay:0.3,sustain:0} })).triggerAttackRelease(duration, time, velocity); break;
                case "Clap":    mk(new Tone.NoiseSynth({ noise:{type:"pink"}, envelope:{attack:0.001,decay:0.3,sustain:0} })).triggerAttackRelease(duration, time, velocity); break;
                case "Tom H":   mk(new Tone.MembraneSynth({pitchDecay:0.05,octaves:4,oscillator:{type:"sine"}})).triggerAttackRelease("C4", duration, time, velocity); break;
                case "Tom L":   mk(new Tone.MembraneSynth({pitchDecay:0.05,octaves:4,oscillator:{type:"sine"}})).triggerAttackRelease("C3", duration, time, velocity); break;
                case "Crash":   mk(new Tone.NoiseSynth({ noise:{type:"pink"}, envelope:{attack:0.01,decay:1.5,sustain:0} })).triggerAttackRelease(duration, time, velocity); break;
            }
        }
    };
}


function showToast(msg) {
    toastEl.innerText = msg;
    toastEl.classList.remove('hidden');
    setTimeout(() => { toastEl.classList.add('hidden'); }, 3000);
}

// --- Data Fetching & Rendering ---
async function fetchLoops() {
    try {
        const res = await fetch(`/api/golden?t=${Date.now()}`);
        loopsData = await res.json();
        renderCatalog();
    } catch (e) {
        console.error("Failed to fetch golden loops", e);
    }
}

function renderCatalog() {
    catalogList.innerHTML = '';
    
    filteredLoops = loopsData.filter(loop => {
        // Search only (no star filter — all tracks here are 5-star)
        if (currentSearchQuery) {
            const query = currentSearchQuery.toLowerCase();
            const textToSearch = `${loop.name} ${loop.instrument}`.toLowerCase();
            if (!textToSearch.includes(query)) return false;
        }
        return true;
    });

    if (filteredLoops.length === 0) {
        catalogList.innerHTML = `
            <div class="empty-golden">
                <span class="material-icons">star_border</span>
                <p>No golden loops yet.<br>Rate any track <strong>5 stars</strong> in the Catalog to add it here.</p>
            </div>`;
        return;
    }

    filteredLoops.forEach(loop => {
        const div = document.createElement('div');
        div.className = 'catalog-item';
        
        // Checkbox
        const chkWrapper = document.createElement('label');
        chkWrapper.className = 'custom-checkbox-wrapper';
        chkWrapper.innerHTML = `
            <input type="checkbox" value="${loop._filename}" ${selectedLoops.has(loop._filename) ? 'checked' : ''}>
            <span class="checkmark"></span>
        `;
        chkWrapper.querySelector('input').addEventListener('change', (e) => {
            if (e.target.checked) selectedLoops.add(loop._filename);
            else selectedLoops.delete(loop._filename);
            updateSelection();
        });

        // Info
        const info = document.createElement('div');
        info.className = 'item-info';

        const nameEl = document.createElement('div');
        nameEl.className = 'item-name';
        nameEl.textContent = loop.name;
        nameEl.title = 'Click to edit name';

        nameEl.addEventListener('click', (e) => {
            if (nameEl.isContentEditable) return;
            e.stopPropagation();
            nameEl.contentEditable = 'true';
            nameEl.focus();
            const range = document.createRange();
            range.selectNodeContents(nameEl);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        });

        nameEl.addEventListener('blur', async () => {
            nameEl.contentEditable = 'false';
            const newName = nameEl.textContent.trim();
            if (newName && newName !== loop.name) {
                const oldFilename = loop._filename;
                loop.name = newName;
                try {
                    const res = await fetch('/api/loops', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(loop)
                    });
                    const result = await res.json();
                    if (result.status === 'success') {
                        const newFilename = result.filename;
                        if (newFilename !== oldFilename) {
                            await fetch(`/api/loops/${oldFilename}`, { method: 'DELETE' });
                            if (loopMeta[oldFilename]) {
                                await fetch(`/api/meta/${newFilename}`, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(loopMeta[oldFilename])
                                });
                            }
                        }
                        showToast("Name updated!");
                        fetchLoops(); // Reload fully
                    }
                } catch (e) {
                    console.error(e);
                    showToast("Error updating name");
                    nameEl.textContent = loop.name;
                }
            } else {
                nameEl.textContent = loop.name;
            }
        });

        nameEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                nameEl.blur();
            }
        });

        const metaEl = document.createElement('div');
        metaEl.className = 'item-meta';
        metaEl.innerHTML = `
            <span><span class="material-icons">speed</span> ${loop.bpm} BPM</span>
            <span><span class="material-icons">piano</span> ${loop.instrument}</span>
            <span><span class="material-icons">straighten</span> ${loop.steps} steps</span>
        `;

        // Stars placed after meta tags, inside item-info
        const currentRating = (loopMeta[loop._filename] || {}).rating || 0;
        const stars = buildStarRating(loop._filename, currentRating);

        info.appendChild(nameEl);
        info.appendChild(metaEl);

        // Controls
        const controls = document.createElement('div');
        controls.className = 'item-controls';
        
        const btnPlayToggle = document.createElement('button');
        btnPlayToggle.className = 'btn icon-btn play';
        btnPlayToggle.innerHTML = '<span class="material-icons">play_arrow</span>';
        btnPlayToggle.title = 'Play / Pause';

        const btnStop = document.createElement('button');
        btnStop.className = 'btn icon-btn stop';
        btnStop.innerHTML = '<span class="material-icons">stop</span>';
        btnStop.disabled = true;
        btnStop.title = 'Stop';

        btnPlayToggle.addEventListener('click', () => {
            if (activeSequence && activeLoopName === loop.name && Tone.Transport.state === 'started') {
                pauseLoop(btnPlayToggle, div);
            } else {
                playLoop(loop, btnPlayToggle, btnStop, div);
            }
        });
        btnStop.addEventListener('click', () => stopLoop(btnPlayToggle, btnStop, div));

        controls.appendChild(btnPlayToggle);
        controls.appendChild(btnStop);

        // BPM Control — same pattern as Merge Modal BPM slider
        const bpmControl = document.createElement('div');
        bpmControl.className = 'item-bpm-control';
        const currentBpm = loopBpmMap[loop._filename] !== undefined ? loopBpmMap[loop._filename] : (loop.bpm || 120);
        bpmControl.innerHTML = `
            <span class="material-icons icon-label" title="Export BPM">speed</span>
            <input type="range" min="60" max="240" value="${currentBpm}"
                   class="slider compact-slider item-bpm-slider"
                   data-filename="${loop._filename}">
            <span class="val-display item-bpm-val">${currentBpm}</span>
        `;
        const bpmSliderEl = bpmControl.querySelector('.item-bpm-slider');
        const bpmValEl    = bpmControl.querySelector('.item-bpm-val');
        bpmSliderEl.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            loopBpmMap[loop._filename] = val;
            bpmValEl.textContent = val;
            // Live-update transport if this exact track is currently playing
            if (activeLoopName === loop.name && Tone.Transport.state === 'started') {
                Tone.Transport.bpm.value = val;
            }
        });
        bpmSliderEl.addEventListener('change', async (e) => {
            const val = parseInt(e.target.value);
            loop.bpm = val;
            try {
                await fetch(`/api/loops/${loop._filename}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(loop)
                });
            } catch (err) { console.error("Auto-save BPM failed", err); }
        });
        bpmSliderEl.addEventListener('click', (e) => e.stopPropagation());

        // State indicator dot (left side)
        const indicator = document.createElement('div');
        indicator.className = 'track-indicator';

        div.appendChild(indicator);
        div.appendChild(info);
        div.appendChild(controls);
        div.appendChild(stars);
        div.appendChild(bpmControl);
        div.appendChild(chkWrapper);

        catalogList.appendChild(div);
    });
    updateSelection();
}

function updateSelection() {
    selectedCount.innerText = selectedLoops.size;
    btnDownload.disabled = selectedLoops.size === 0;
    if (btnDownloadJson) btnDownloadJson.disabled = selectedLoops.size === 0;
    if (btnMergeDownload) btnMergeDownload.disabled = selectedLoops.size === 0;
    if (btnExportAudio) btnExportAudio.disabled = selectedLoops.size === 0;
    btnDelete.disabled = selectedLoops.size === 0;
    
    if (filteredLoops.length === 0) {
        checkAll.checked = false;
        checkAll.indeterminate = false;
    } else {
        // Check how many of the currently visible (filtered) loops are selected
        const selectedVisible = filteredLoops.filter(l => selectedLoops.has(l._filename)).length;
        checkAll.checked = selectedVisible === filteredLoops.length;
        checkAll.indeterminate = selectedVisible > 0 && selectedVisible < filteredLoops.length;
    }
}

function setupEventListeners() {
    document.body.addEventListener('click', initAudioContext, { once: true });

    checkAll.addEventListener('change', (e) => {
        if (e.target.checked) {
            filteredLoops.forEach(l => selectedLoops.add(l._filename));
        } else {
            filteredLoops.forEach(l => selectedLoops.delete(l._filename));
        }
        renderCatalog(); 
    });

    // Search
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchQuery = e.target.value;
            renderCatalog();
        });
    }

    // No star filter on Golden Fund page — all tracks here are 5-star

    btnDownload.addEventListener('click', batchExport);
    btnDelete.addEventListener('click', bulkDelete);
    if (btnExportAudio) btnExportAudio.addEventListener('click', bulkExportAudio);
    if (btnCancelExport) btnCancelExport.addEventListener('click', () => { exportCancelled = true; });

    if (btnDownloadJson) {
        btnDownloadJson.addEventListener('click', () => {
            const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
            if (loopsToExport.length === 0) return;

            const cleanLoops = loopsToExport.map(l => {
                const { _filename, ...rest } = l;
                return rest;
            });

            const dataStr = JSON.stringify(cleanLoops, null, 2);
            const blob = new Blob([dataStr], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement("a");
            a.href = url;
            a.download = "Selected_Loops.json";
            a.click();
            URL.revokeObjectURL(url);
            showToast("JSON downloaded!");
        });
    }

    if (btnInsertJson) {
        btnInsertJson.addEventListener('click', () => {
            insertModal.classList.remove('hidden');
        });
    }

    if (btnCloseInsert) {
        btnCloseInsert.addEventListener('click', () => {
            insertModal.classList.add('hidden');
        });
    }

    if (insertModal) {
        insertModal.addEventListener('click', (e) => {
            if (e.target === insertModal) {
                insertModal.classList.add('hidden');
            }
        });
    }

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
                fetchLoops(); // refresh catalog
                
                insertModal.classList.add('hidden');
                jsonPasteArea.value = ''; // clear after success
            } catch (err) {
                showToast("Invalid JSON text");
                console.error(err);
            }
        });
    }

    // Global listener to stop playback when clicking away
    document.addEventListener('mousedown', (e) => {
        if (!activeSequence) return;
        
        // Ignore clicks within the currently playing track's item
        if (activeItemEl && activeItemEl.contains(e.target)) return;
        
        // Ignore clicks on checkboxes (so user can select tracks while listening)
        if (e.target.closest('.custom-checkbox-wrapper') || e.target.closest('input[type="checkbox"]')) return;
        
        // Ignore clicks on search input and stars
        if (e.target.tagName.toLowerCase() === 'input' || e.target.closest('.star-filter')) return;

        // Ignore clicks on play/stop buttons of other tracks, let their click handlers manage switching
        if (e.target.closest('.item-controls')) return;

        // Stop the track for any other click on the page (including disabled buttons)
        stopLoop(null, null, activeItemEl);
    });

    if (btnMergeDownload) {
        btnMergeDownload.addEventListener('click', openMergeModal);
    }
    
    if (btnCloseMergeModal) {
        btnCloseMergeModal.addEventListener('click', closeMergeModal);
    }
    
    if (mergeModal) {
        mergeModal.addEventListener('click', (e) => {
            if (e.target === mergeModal) closeMergeModal();
        });
    }

    if (mergeBpmSlider) {
        mergeBpmSlider.addEventListener('input', (e) => {
            const val = e.target.value;
            mergeBpmVal.innerText = val;
            if (isPreviewing) {
                Tone.Transport.bpm.value = parseInt(val);
            }
        });
    }

    if (btnMergePreview) {
        btnMergePreview.addEventListener('click', togglePreview);
    }

    if (btnMergeConfirmDownload) {
        btnMergeConfirmDownload.addEventListener('click', mergeExportFromModal);
    }
}

// Helper: clear state classes from an item element
function clearItemState(el) {
    if (!el) return;
    el.classList.remove('is-loading', 'is-playing', 'is-paused');
}

// --- Playback Logic ---
async function playLoop(loopData, btnPlayToggle, btnStop, itemEl) {
    const isResuming = (activeSequence && activeLoopName === loopData.name && Tone.Transport.state === 'paused');

    // Stop any existing loop and clear its state synchronously BEFORE any async gaps
    if (!isResuming && activeSequence) {
        stopLoop(null, null, activeItemEl);
    }

    const currentId = ++playbackId;

    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();

    if (currentId !== playbackId) return; // Abort if another play was clicked

    // If resuming from pause on the same loop
    if (isResuming) {
        Tone.Transport.start();
        btnPlayToggle.innerHTML = '<span class="material-icons">pause</span>';
        btnPlayToggle.classList.add('paused-state');
        if (activeItemEl) {
            clearItemState(activeItemEl);
            activeItemEl.classList.add('is-playing');
        }
        return;
    }

    // Set loading state immediately
    activeItemEl = itemEl;
    activeLoopName = loopData.name;
    clearItemState(itemEl);
    itemEl.classList.add('is-loading');

    document.querySelectorAll('.catalog-item .play').forEach(b => { 
        b.innerHTML = '<span class="material-icons">play_arrow</span>';
        b.classList.remove('paused-state');
        b.disabled = false; 
    });

    btnPlayToggle.innerHTML = '<span class="material-icons">pause</span>';
    btnPlayToggle.classList.add('paused-state');
    btnStop.disabled = false;

    Tone.Transport.bpm.value = (loopBpmMap[loopData._filename] !== undefined ? loopBpmMap[loopData._filename] : (loopData.bpm || 120));
    Tone.Transport.swing = loopData.swing || 0.0;
    Tone.Transport.swingSubdivision = "8n";

    const currentSynth = synths[loopData.instrument] || synths.piano;
    const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);

    // Transition from loading → playing
    clearItemState(itemEl);
    itemEl.classList.add('is-playing');
    
    // Preserve full metadata for notes
    const stepNotes = {};
    loopData.notes.forEach(n => {
        if (!stepNotes[n.step]) stepNotes[n.step] = [];
        stepNotes[n.step].push(n);
    });

    let loopCounter = 0;
    
    activeSequence = new Tone.Sequence((time, step) => {
        if (step === 0) loopCounter++;
        
        // Stop automatically after 3 loops
        if (loopCounter > 3) {
            Tone.Transport.scheduleOnce(() => {
                stopLoop(btnPlayToggle, btnStop, itemEl);
            }, time);
            return;
        }

        if (stepNotes[step]) {
            stepNotes[step].forEach(n => {
                let chance = n.chance !== undefined ? n.chance : 1.0;
                let velocity = n.velocity !== undefined ? n.velocity : 1.0;
                if (Math.random() <= chance) {
                    currentSynth.triggerAttackRelease(n.note, n.duration || "8n", time, velocity);
                }
            });
        }
    }, stepsArray, "8n").start(0);

    Tone.Transport.start();
    
    // Start equalizer loop
    if (animFrameId) cancelAnimationFrame(animFrameId);
    renderEq();
}

function renderEq() {
    if (!fft || !eqBars.length || Tone.Transport.state !== 'started') {
        eqBars.forEach(bar => bar.style.height = '4px');
        return;
    }

    const bufferLength = fft.frequencyBinCount; // = fftSize / 2 = 128
    const dataArray = new Uint8Array(bufferLength);
    fft.getByteFrequencyData(dataArray);

    const numBarsPerEq = 72;
    for (let i = 0; i < eqBars.length; i++) {
        const localIndex = i % numBarsPerEq;
        const binIndex = Math.floor((localIndex / numBarsPerEq) * bufferLength);
        const value = dataArray[binIndex]; // 0–255
        const normalized = value / 255;
        const height = Math.round(4 + (normalized * 36));
        eqBars[i].style.height = `${height}px`;
    }

    animFrameId = requestAnimationFrame(renderEq);
}

function pauseLoop(btnPlayToggle, itemEl) {
    if (activeSequence && Tone.Transport.state === 'started') {
        Tone.Transport.pause();
        btnPlayToggle.innerHTML = '<span class="material-icons">play_arrow</span>';
        btnPlayToggle.classList.remove('paused-state');
        if (itemEl) {
            clearItemState(itemEl);
            itemEl.classList.add('is-paused');
        }
    }
}

function stopLoop(btnPlayToggle, btnStop, itemEl) {
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
    clearItemState(itemEl || activeItemEl);
    activeItemEl = null;
    if (btnPlayToggle) {
        btnPlayToggle.innerHTML = '<span class="material-icons">play_arrow</span>';
        btnPlayToggle.classList.remove('paused-state');
        btnPlayToggle.disabled = false;
    }
    if (btnStop) btnStop.disabled = true;

    document.querySelectorAll('.catalog-item .play').forEach(b => { 
        b.innerHTML = '<span class="material-icons">play_arrow</span>';
        b.classList.remove('paused-state');
        b.disabled = false; 
    });
    document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });

    // Stop eq
    if (animFrameId) cancelAnimationFrame(animFrameId);
    eqBars.forEach(bar => bar.style.height = '4px');
}

// --- Batch Export Logic ---
async function batchExport() {
    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();

    // Stop playback if playing
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
    document.querySelectorAll('.catalog-item .play').forEach(b => { 
        b.innerHTML = '<span class="material-icons">play_arrow</span>';
        b.classList.remove('paused-state');
        b.disabled = false; 
    });
    document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });

    btnDownload.disabled = true;
    btnDelete.disabled = true;
    progressContainer.classList.remove('hidden');

    const zip = new JSZip();
    const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
    const total = loopsToExport.length;

    for (let i = 0; i < total; i++) {
        const loop = loopsToExport[i];
        
        // Update UI
        progressText.innerText = `Exporting: ${loop.name} (${i + 1}/${total})...`;
        const percent = (i / total) * 100;
        progressFill.style.width = `${percent}%`;

        const blob = await exportSingleLoopSilent(loop);
        
        // Add to ZIP (skip if export bailed out)
        if (blob) {
            const cleanName = loop.name.replace(/[^a-zA-Z0-9_-]/g, '_') || 'loop';
            zip.file(`${cleanName}.webm`, blob);
        }
    }

    progressText.innerText = `Packaging ZIP archive...`;
    progressFill.style.width = `100%`;

    const zipBlob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(zipBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Loops_Export.zip";
    a.click();

    setTimeout(() => {
        progressContainer.classList.add('hidden');
        progressFill.style.width = `0%`;
        btnDownload.disabled = false;
        selectedLoops.clear();
        updateSelection();
        renderCatalog();
        showToast("Batch export completed successfully!");
    }, 1500);
}

// --- Bulk Audio Export (individual files, one by one) ---
async function bulkExportAudio() {
    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();

    // Stop any playing loop
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
    document.querySelectorAll('.catalog-item .play').forEach(b => { 
        b.innerHTML = '<span class="material-icons">play_arrow</span>';
        b.classList.remove('paused-state');
        b.disabled = false; 
    });
    document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });

    const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
    if (loopsToExport.length === 0) return;

    exportCancelled = false;

    // Populate track list in overlay
    exportTrackList.innerHTML = '';
    loopsToExport.forEach((loop, idx) => {
        const bpm = loopBpmMap[loop._filename] !== undefined ? loopBpmMap[loop._filename] : (loop.bpm || 120);
        const durationSec = loop.steps * 30 / bpm;
        const item = document.createElement('div');
        item.className = 'export-track-item';
        item.id = `export-track-item-${idx}`;
        item.innerHTML = `
            <div class="export-track-item-row">
                <span class="export-track-status material-icons">radio_button_unchecked</span>
                <span class="export-track-name">${loop.name}</span>
                <span class="export-track-bpm">${bpm} BPM</span>
            </div>
            <div class="export-track-progress">
                <div class="export-track-progress-bg">
                    <div class="export-track-progress-fill"></div>
                </div>
                <span class="export-track-progress-time">0.0s / ${durationSec.toFixed(1)}s</span>
            </div>
        `;
        exportTrackList.appendChild(item);
    });

    // Reset progress
    exportProgressFill.style.width = '0%';
    exportProgressPct.textContent = `0% (0/${loopsToExport.length})`;
    exportCurrentTrack.textContent = 'Preparing...';

    // Show overlay
    exportOverlay.classList.remove('hidden');

    const total = loopsToExport.length;

    for (let i = 0; i < total; i++) {
        if (exportCancelled) break;

        const loop = loopsToExport[i];
        const overrideBpm = loopBpmMap[loop._filename] !== undefined ? loopBpmMap[loop._filename] : (loop.bpm || 120);

        exportCurrentTrack.textContent = loop.name;

        // Mark as in-progress and start real-time progress bar
        const trackItem = document.getElementById(`export-track-item-${i}`);
        const durationSec = loop.steps * 30 / overrideBpm;
        let trackProgressInterval = null;
        if (trackItem) {
            trackItem.querySelector('.export-track-status').textContent = 'hourglass_empty';
            trackItem.classList.add('in-progress');
            trackItem.scrollIntoView({ block: 'nearest' });

            const progressFill = trackItem.querySelector('.export-track-progress-fill');
            const progressTime = trackItem.querySelector('.export-track-progress-time');
            const totalSec = durationSec + 1.5; // match exportSingleLoopSilent timeout
            const startTime = Date.now();

            trackProgressInterval = setInterval(() => {
                const elapsed = (Date.now() - startTime) / 1000;
                const pct = Math.min(elapsed / totalSec, 1) * 100;
                if (progressFill) progressFill.style.width = `${pct.toFixed(1)}%`;
                if (progressTime) progressTime.textContent =
                    `${Math.min(elapsed, durationSec).toFixed(1)}s / ${durationSec.toFixed(1)}s`;
            }, 100);
        }

        const blob = await exportSingleLoopSilent(loop, overrideBpm);
        if (trackProgressInterval) clearInterval(trackProgressInterval);
        // Snap bar to 100% on completion
        if (trackItem) {
            const pf = trackItem.querySelector('.export-track-progress-fill');
            const pt = trackItem.querySelector('.export-track-progress-time');
            if (pf) pf.style.width = '100%';
            if (pt) pt.textContent = `${durationSec.toFixed(1)}s / ${durationSec.toFixed(1)}s`;
        }

        if (exportCancelled || blob === null) break;

        // Download immediately
        const cleanName = loop.name.replace(/[^a-zA-Z0-9_-]/g, '_') || 'loop';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${cleanName}.webm`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 2000);

        // Mark as done
        if (trackItem) {
            trackItem.querySelector('.export-track-status').textContent = 'check_circle';
            trackItem.classList.remove('in-progress');
            trackItem.classList.add('done');
        }

        // Update progress
        const percent = Math.round(((i + 1) / total) * 100);
        exportProgressFill.style.width = `${percent}%`;
        exportProgressPct.textContent = `${percent}% (${i + 1}/${total})`;
    }

    if (exportCancelled) {
        exportCurrentTrack.textContent = 'Cancelled.';
        setTimeout(() => {
            exportOverlay.classList.add('hidden');
            showToast('Export cancelled.');
            alert('Export cancelled by user.');
        }, 800);
    } else {
        exportCurrentTrack.textContent = 'Done! \u2713';
        setTimeout(() => {
            exportOverlay.classList.add('hidden');
            showToast(`Exported ${total} track(s) successfully!`);
            alert(`✓ Export complete!\n${total} file(s) downloaded successfully.`);
            selectedLoops.clear();
            updateSelection();
            renderCatalog();
        }, 800);
    }
}

function exportSingleLoopSilent(loopData, overrideBpm) {
    return new Promise(async (resolve) => {
        const currentSynth = silentSynths[loopData.instrument] || silentSynths.piano;
        const bpm = overrideBpm || loopData.bpm || 120;

        // ── 1. Wait for all audio samples to load (piano Sampler loads from CDN).
        //       Without this, the first few notes are silent → gaps in the exported file.
        //       Cap the wait at 10 s so we don't hang on a slow/down CDN.
        try {
            const loadTimeout = new Promise((_, rej) =>
                setTimeout(() => rej(new Error('load timeout')), 10000)
            );
            await Promise.race([Tone.loaded(), loadTimeout]);
        } catch (e) {
            console.warn('exportSingleLoopSilent: sample load timeout, exporting anyway', e);
        }

        if (exportCancelled) { resolve(null); return; }

        if (Tone.context.state !== 'running') {
            await Tone.context.resume();
        }

        // ── 2. Fresh Tone.Recorder for every track.
        if (recorder) {
            try { 
                if (recorder.state === "started") {
                    await recorder.stop(); 
                }
            } catch (_) {}
            try { recorder.dispose(); } catch (_) {}
        }
        recorder = new Tone.Recorder();
        exportRecorderNode.disconnect();
        exportRecorderNode.connect(recorder);

        // ── 3. Reset Transport completely before each track.
        Tone.Transport.stop();
        Tone.Transport.cancel();
        Tone.Transport.position = 0;
        Tone.Transport.bpm.value = bpm;
        Tone.Transport.swing = loopData.swing || 0.0;
        Tone.Transport.swingSubdivision = "8n";

        const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);
        const stepNotes = {};
        loopData.notes.forEach(n => {
            if (!stepNotes[n.step]) stepNotes[n.step] = [];
            stepNotes[n.step].push(n);
        });

        // Each step = one "8n" (eighth note). durationSec = steps * 30 / bpm
        const durationSec = loopData.steps * 30 / bpm;

        const tempSequence = new Tone.Sequence((time, step) => {
            if (stepNotes[step]) {
                stepNotes[step].forEach(n => {
                    const chance   = n.chance   !== undefined ? n.chance   : 1.0;
                    const velocity = n.velocity !== undefined ? n.velocity : 1.0;
                    if (Math.random() <= chance) {
                        currentSynth.triggerAttackRelease(n.note, n.duration || "8n", time, velocity);
                    }
                });
            }
        }, stepsArray, "8n").start(0);

        // Play exactly once — do NOT loop
        tempSequence.loop = false;

        // ── 4. Start recorder, then wait 150 ms pre-roll so MediaRecorder is
        //       guaranteed in 'recording' state before audio starts flowing.
        recorder.start();
        await new Promise(res => setTimeout(res, 150));
        if (exportCancelled) {
            try { await recorder.stop(); } catch (_) {}
            tempSequence.dispose();
            resolve(null);
            return;
        }
        Tone.Transport.start();

        // Allow cancel to abort mid-render
        let exportTimeoutId;
        const cancelWatcher = setInterval(() => {
            if (exportCancelled) {
                clearInterval(cancelWatcher);
                clearTimeout(exportTimeoutId);
                Tone.Transport.stop();
                tempSequence.stop();
                tempSequence.dispose();
                if (recorder && recorder.state === "started") {
                    recorder.stop().then(() => resolve(null)).catch(() => resolve(null));
                } else {
                    resolve(null);
                }
            }
        }, 250);

        exportTimeoutId = setTimeout(async () => {
            clearInterval(cancelWatcher);
            Tone.Transport.stop();
            tempSequence.stop();
            tempSequence.dispose();

            // Hard safety: if recorder.stop() hangs, bail after 8 s
            let recording = null;
            if (recorder && recorder.state === "started") {
                const hardTimeout = new Promise(res => setTimeout(() => res(null), 8000));
                recording = await Promise.race([recorder.stop(), hardTimeout]);
            }
            resolve(recording);
        }, (durationSec + 1.5) * 1000);
    });
}

// --- Merge Modal Logic ---


function openMergeModal() {
    const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
    if (loopsToExport.length === 0) return;

    // Populate track list
    mergeTrackList.innerHTML = '';
    loopsToExport.forEach(loop => {
        const div = document.createElement('div');
        div.className = 'merge-track-item';
        div.innerHTML = `
            <div class="merge-track-item-header">
                <span class="name">${loop.name}</span>
                <div class="meta">
                    <span><span class="material-icons">speed</span> ${loop.bpm}</span>
                    <span><span class="material-icons">piano</span> ${loop.instrument}</span>
                </div>
            </div>
            <div class="track-volume">
                <span class="material-icons" style="font-size:16px;">volume_up</span>
                <input type="range" class="merge-track-vol compact-slider" data-filename="${loop._filename}" min="0" max="2" step="0.05" value="1.0">
            </div>
        `;
        mergeTrackList.appendChild(div);
    });

    // Default BPM to first track
    const firstLoop = loopsToExport.find(l => l._filename === selectedLoops.values().next().value) || loopsToExport[0];
    const defaultBpm = firstLoop.bpm || 120;
    mergeBpmSlider.value = defaultBpm;
    mergeBpmVal.innerText = defaultBpm;

    mergeProgressContainer.classList.add('hidden');
    mergeProgressFill.style.width = '0%';
    btnMergeConfirmDownload.disabled = false;
    
    // Stop any existing playback in catalog
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
    document.querySelectorAll('.catalog-item .play').forEach(b => { 
        b.innerHTML = '<span class="material-icons">play_arrow</span>';
        b.classList.remove('paused-state');
        b.disabled = false; 
    });
    document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });

    mergeModal.classList.remove('hidden');
}

function closeMergeModal() {
    stopPreview();
    mergeModal.classList.add('hidden');
}

async function togglePreview() {
    if (isPreviewing) {
        stopPreview();
    } else {
        await startPreview();
    }
}

async function startPreview() {
    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();

    const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
    if (loopsToExport.length === 0) return;

    const targetBpm = parseInt(mergeBpmSlider.value);
    const firstLoop = loopsToExport.find(l => l._filename === selectedLoops.values().next().value) || loopsToExport[0];
    const targetSwing = firstLoop.swing || 0.0;

    let maxSteps = 0;
    loopsToExport.forEach(l => {
        if (l.steps > maxSteps) maxSteps = l.steps;
    });

    Tone.Transport.bpm.value = targetBpm;
    Tone.Transport.swing = targetSwing;
    Tone.Transport.swingSubdivision = "8n";

    const stepsArray = Array.from({length: maxSteps}, (_, i) => i);
    const masterStepNotes = {}; 
    for (let s = 0; s < maxSteps; s++) { masterStepNotes[s] = []; }

    const trackVolumes = {};
    document.querySelectorAll('.merge-track-vol').forEach(slider => {
        trackVolumes[slider.dataset.filename] = parseFloat(slider.value);
        slider.addEventListener('input', (e) => {
            trackVolumes[slider.dataset.filename] = parseFloat(e.target.value);
        });
    });

    loopsToExport.forEach(loopData => {
        const loopLen = loopData.steps;
        const synthName = loopData.instrument;
        loopData.notes.forEach(n => {
            for (let targetStep = n.step; targetStep < maxSteps; targetStep += loopLen) {
                masterStepNotes[targetStep].push({
                    loopFilename: loopData._filename,
                    synthName: synthName,
                    note: n.note,
                    duration: n.duration || "8n",
                    velocity: n.velocity !== undefined ? n.velocity : 1.0,
                    chance: n.chance !== undefined ? n.chance : 1.0
                });
            }
        });
    });

    previewSequence = new Tone.Sequence((time, step) => {
        const notesToPlay = masterStepNotes[step];
        if (notesToPlay) {
            notesToPlay.forEach(n => {
                if (Math.random() <= n.chance) {
                    // Use regular synths for preview playback
                    const currentSynth = synths[n.synthName] || synths.piano;
                    const volMultiplier = trackVolumes[n.loopFilename] !== undefined ? trackVolumes[n.loopFilename] : 1.0;
                    currentSynth.triggerAttackRelease(n.note, n.duration, time, n.velocity * volMultiplier);
                }
            });
        }
    }, stepsArray, "8n").start(0);

    previewSequence.loop = true; // Loop endlessly for preview until stopped
    
    Tone.Transport.start();
    isPreviewing = true;
    if (btnMergePreview) {
        btnMergePreview.innerHTML = '<span class="material-icons" id="merge-preview-icon">pause</span> Pause';
        btnMergePreview.classList.add('paused-state');
    }
    
    // Resume EQ visualizer if present
    if (animFrameId) cancelAnimationFrame(animFrameId);
    renderEq();
}

function stopPreview() {
    if (previewSequence) {
        Tone.Transport.stop();
        previewSequence.stop();
        previewSequence.dispose();
        previewSequence = null;
    }
    isPreviewing = false;
    if (btnMergePreview) {
        btnMergePreview.innerHTML = '<span class="material-icons" id="merge-preview-icon">play_arrow</span> Preview';
        btnMergePreview.classList.remove('paused-state');
    }
    
    if (animFrameId) cancelAnimationFrame(animFrameId);
    eqBars.forEach(bar => bar.style.height = '4px');
}

async function mergeExportFromModal() {
    stopPreview();
    
    btnMergeConfirmDownload.disabled = true;
    btnMergePreview.disabled = true;
    btnCloseMergeModal.disabled = true;

    mergeProgressContainer.classList.remove('hidden');
    mergeProgressText.innerText = "Rendering Audio...";
    mergeProgressFill.style.width = "50%";

    const loopsToExport = loopsData.filter(l => selectedLoops.has(l._filename));
    const targetBpm = parseInt(mergeBpmSlider.value);
    const firstLoop = loopsToExport.find(l => l._filename === selectedLoops.values().next().value) || loopsToExport[0];
    const targetSwing = firstLoop.swing || 0.0;

    let maxSteps = 0;
    loopsToExport.forEach(l => {
        if (l.steps > maxSteps) maxSteps = l.steps;
    });

    Tone.Transport.bpm.value = targetBpm;
    Tone.Transport.swing = targetSwing;
    Tone.Transport.swingSubdivision = "8n";

    const stepsArray = Array.from({length: maxSteps}, (_, i) => i);
    const masterStepNotes = {}; 
    for (let s = 0; s < maxSteps; s++) { masterStepNotes[s] = []; }

    const trackVolumes = {};
    document.querySelectorAll('.merge-track-vol').forEach(slider => {
        trackVolumes[slider.dataset.filename] = parseFloat(slider.value);
    });

    loopsToExport.forEach(loopData => {
        const loopLen = loopData.steps;
        const synthName = loopData.instrument;
        loopData.notes.forEach(n => {
            for (let targetStep = n.step; targetStep < maxSteps; targetStep += loopLen) {
                masterStepNotes[targetStep].push({
                    loopFilename: loopData._filename,
                    synthName: synthName,
                    note: n.note,
                    duration: n.duration || "8n",
                    velocity: n.velocity !== undefined ? n.velocity : 1.0,
                    chance: n.chance !== undefined ? n.chance : 1.0
                });
            }
        });
    });

    const masterSequence = new Tone.Sequence((time, step) => {
        const notesToPlay = masterStepNotes[step];
        if (notesToPlay) {
            notesToPlay.forEach(n => {
                if (Math.random() <= n.chance) {
                    // Use silentSynths for recording!
                    const currentSynth = silentSynths[n.synthName] || silentSynths.piano;
                    const volMultiplier = trackVolumes[n.loopFilename] !== undefined ? trackVolumes[n.loopFilename] : 1.0;
                    currentSynth.triggerAttackRelease(n.note, n.duration, time, n.velocity * volMultiplier);
                }
            });
        }
    }, stepsArray, "8n").start(0);

    masterSequence.loop = 1;

    // 8n = 2 steps per beat
    const beats = maxSteps / 2;
    const durationSec = beats * (60 / targetBpm);

    recorder.start();
    Tone.Transport.start();

    setTimeout(async () => {
        Tone.Transport.stop();
        masterSequence.stop();
        masterSequence.dispose();
        
        const recording = await recorder.stop();
        mergeProgressFill.style.width = "100%";
        
        const url = URL.createObjectURL(recording);
        const a = document.createElement("a");
        a.href = url;
        
        let selectedBaseName = "Merged_Loop";
        const pianoLoop = loopsToExport.find(l => l.instrument === "piano");
        if (pianoLoop) {
            selectedBaseName = pianoLoop.name;
        } else {
            const nonDrumLoop = loopsToExport.find(l => l.instrument !== "drums");
            if (nonDrumLoop) {
                selectedBaseName = nonDrumLoop.name;
            } else if (loopsToExport.length > 0) {
                selectedBaseName = loopsToExport[0].name;
            }
        }
        
        const generatedName = selectedBaseName.replace(/\s+/g, '_');
        a.download = `---Loop_${generatedName}.webm`;
        a.click();
        URL.revokeObjectURL(url);
        
        setTimeout(() => {
            closeMergeModal();
            updateSelection();
            renderCatalog();
            showToast("Merged audio downloaded!");
            
            // Restore UI state
            btnMergeConfirmDownload.disabled = false;
            btnMergePreview.disabled = false;
            btnCloseMergeModal.disabled = false;
        }, 1500);

    }, (durationSec + 1.5) * 1000);
}

async function bulkDelete() {
    if (selectedLoops.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedLoops.size} loop(s)?`)) return;

    btnDelete.disabled = true;
    let deleted = 0;

    for (const filename of selectedLoops) {
        try {
            const res = await fetch(`/api/loops/${filename}`, { method: 'DELETE' });
            if (res.ok) deleted++;
        } catch (e) {
            console.error(e);
        }
    }

    showToast(`Deleted ${deleted} loops.`);
    selectedLoops.clear();
    await fetchLoops();
}

// Start
document.addEventListener('DOMContentLoaded', init);
