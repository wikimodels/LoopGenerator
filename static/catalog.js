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
let activeSequence = null;
let activeLoopName = null;
let activeItemEl = null; // DOM element of the currently active catalog-item
let fft = null;       // native AnalyserNode
let eqBars = [];
let animFrameId = null;

// DOM Elements
const catalogList = document.getElementById('catalog-list');
const checkAll = document.getElementById('check-all');
const selectedCount = document.getElementById('selected-count');
const btnDownload = document.getElementById('btn-download-selected');
const btnDelete = document.getElementById('btn-delete-selected');
const progressContainer = document.getElementById('progress-container');
const progressText = document.getElementById('progress-text');
const progressFill = document.getElementById('progress-fill');
const toastEl = document.getElementById('toast');

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
    eqBars = Array.from(document.querySelectorAll('.eq-bar'));
    
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

    // Silent synths for background rendering (export)
    recorder = new Tone.Recorder();
    silentSynths = {
        synth: new Tone.PolySynth(Tone.Synth).connect(recorder),
        amSynth: new Tone.PolySynth(Tone.AMSynth).connect(recorder),
        fmSynth: new Tone.PolySynth(Tone.FMSynth).connect(recorder),
        piano: new Tone.Sampler({
            urls: { "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3" },
            release: 1,
            baseUrl: "https://tonejs.github.io/audio/salamander/"
        }).connect(recorder),
        drums: createDrumKit(recorder)
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
        const res = await fetch('/api/loops');
        loopsData = await res.json();
        renderCatalog();
    } catch (e) {
        console.error("Failed to fetch loops", e);
    }
}

function renderCatalog() {
    catalogList.innerHTML = '';
    
    filteredLoops = loopsData.filter(loop => {
        // Search
        if (currentSearchQuery) {
            const query = currentSearchQuery.toLowerCase();
            const textToSearch = `${loop.name} ${loop.instrument}`.toLowerCase();
            if (!textToSearch.includes(query)) return false;
        }
        // Star Filter
        if (currentStarFilter > 0) {
            const rating = (loopMeta[loop._filename] || {}).rating || 0;
            if (rating !== currentStarFilter) return false;
        }
        return true;
    });

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
        info.appendChild(stars);

        // Controls
        const controls = document.createElement('div');
        controls.className = 'item-controls';
        
        const btnPlay = document.createElement('button');
        btnPlay.className = 'btn icon-btn play';
        btnPlay.innerHTML = '<span class="material-icons">play_arrow</span>';
        btnPlay.title = 'Play (3 times)';
        
        const btnPause = document.createElement('button');
        btnPause.className = 'btn icon-btn secondary';
        btnPause.innerHTML = '<span class="material-icons">pause</span>';
        btnPause.disabled = true;
        btnPause.title = 'Pause';

        const btnStop = document.createElement('button');
        btnStop.className = 'btn icon-btn stop';
        btnStop.innerHTML = '<span class="material-icons">stop</span>';
        btnStop.disabled = true;
        btnStop.title = 'Stop';

        btnPlay.addEventListener('click', () => playLoop(loop, btnPlay, btnPause, btnStop, div));
        btnPause.addEventListener('click', () => pauseLoop(btnPlay, btnPause, div));
        btnStop.addEventListener('click', () => stopLoop(btnPlay, btnPause, btnStop, div));

        controls.appendChild(btnPlay);
        controls.appendChild(btnPause);
        controls.appendChild(btnStop);

        div.appendChild(chkWrapper);
        div.appendChild(info);
        div.appendChild(controls);

        catalogList.appendChild(div);
    });
    updateSelection();
}

function updateSelection() {
    selectedCount.innerText = selectedLoops.size;
    btnDownload.disabled = selectedLoops.size === 0;
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

    // Header Star Filter
    const starFilterEl = document.getElementById('star-filter');
    if (starFilterEl) {
        starFilterEl.querySelectorAll('.star').forEach(star => {
            star.addEventListener('click', (e) => {
                const val = parseInt(e.target.dataset.value);
                currentStarFilter = currentStarFilter === val ? 0 : val;
                
                // update UI
                starFilterEl.querySelectorAll('.star').forEach((s, idx) => {
                    s.classList.toggle('filled', idx < currentStarFilter);
                });
                renderCatalog();
            });
        });
    }

    btnDownload.addEventListener('click', batchExport);
    btnDelete.addEventListener('click', bulkDelete);
}

// Helper: clear state classes from an item element
function clearItemState(el) {
    if (!el) return;
    el.classList.remove('is-loading', 'is-playing', 'is-paused');
}

// --- Playback Logic ---
async function playLoop(loopData, btnPlay, btnPause, btnStop, itemEl) {
    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();

    // If resuming from pause on the same loop
    if (activeSequence && activeLoopName === loopData.name && Tone.Transport.state === 'paused') {
        Tone.Transport.start();
        btnPlay.disabled = true;
        btnPause.disabled = false;
        if (activeItemEl) {
            clearItemState(activeItemEl);
            activeItemEl.classList.add('is-playing');
        }
        return;
    }

    // Stop any existing loop and clear its state
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        clearItemState(activeItemEl);
        document.querySelectorAll('.catalog-item .play').forEach(b => { b.disabled = false; });
        document.querySelectorAll('.catalog-item .pause').forEach(b => { b.disabled = true; });
        document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });
    }

    // Set loading state immediately
    activeItemEl = itemEl;
    activeLoopName = loopData.name;
    clearItemState(itemEl);
    itemEl.classList.add('is-loading');
    btnPlay.disabled = true;
    btnPause.disabled = true;
    btnStop.disabled = true;

    Tone.Transport.bpm.value = loopData.bpm || 120;
    Tone.Transport.swing = loopData.swing || 0.0;
    Tone.Transport.swingSubdivision = "8n";

    const currentSynth = synths[loopData.instrument] || synths.piano;
    const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);

    // Transition from loading → playing
    clearItemState(itemEl);
    itemEl.classList.add('is-playing');
    btnPause.disabled = false;
    btnStop.disabled = false;
    
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
                stopLoop(btnPlay, btnPause, btnStop);
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

    for (let i = 0; i < eqBars.length; i++) {
        // Map 72 bars across 128 frequency bins
        const binIndex = Math.floor((i / eqBars.length) * bufferLength);
        const value = dataArray[binIndex]; // 0–255
        const normalized = value / 255;
        const height = 4 + (normalized * 36);
        eqBars[i].style.height = `${height}px`;
    }

    animFrameId = requestAnimationFrame(renderEq);
}

function pauseLoop(btnPlay, btnPause, itemEl) {
    if (activeSequence && Tone.Transport.state === 'started') {
        Tone.Transport.pause();
        btnPlay.disabled = false;
        btnPause.disabled = true;
        if (itemEl) {
            clearItemState(itemEl);
            itemEl.classList.add('is-paused');
        }
    }
}

function stopLoop(btnPlay, btnPause, btnStop, itemEl) {
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
    clearItemState(itemEl || activeItemEl);
    activeItemEl = null;
    if (btnPlay) btnPlay.disabled = false;
    if (btnPause) btnPause.disabled = true;
    if (btnStop) btnStop.disabled = true;

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
    document.querySelectorAll('.catalog-item .play').forEach(b => { b.disabled = false; });
    document.querySelectorAll('.catalog-item .pause').forEach(b => { b.disabled = true; });
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
        
        // Add to ZIP
        const cleanName = loop.name.replace(/[^a-zA-Z0-9_-]/g, '_') || 'loop';
        zip.file(`${cleanName}.webm`, blob);
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

function exportSingleLoopSilent(loopData) {
    return new Promise(async (resolve) => {
        const currentSynth = silentSynths[loopData.instrument] || silentSynths.piano;
        Tone.Transport.bpm.value = loopData.bpm || 120;
        Tone.Transport.swing = loopData.swing || 0.0;
        Tone.Transport.swingSubdivision = "8n";
        
        const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);
        const stepNotes = {};
        loopData.notes.forEach(n => {
            if (!stepNotes[n.step]) stepNotes[n.step] = [];
            stepNotes[n.step].push(n);
        });

        // 8n = 2 steps per beat
        const beats = loopData.steps / 2;
        const durationSec = beats * (60 / loopData.bpm);

        const tempSequence = new Tone.Sequence((time, step) => {
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

        tempSequence.loop = 1; // Play exactly 1 time
        
        recorder.start();
        Tone.Transport.start();

        setTimeout(async () => {
            Tone.Transport.stop();
            tempSequence.stop();
            tempSequence.dispose();
            
            const recording = await recorder.stop();
            resolve(recording);
        }, (durationSec + 1.5) * 1000); // Wait for sequence + tail
    });
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
