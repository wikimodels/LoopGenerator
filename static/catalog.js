let loopsData = [];
let selectedLoops = new Set();
let isAudioInitialized = false;

// Audio state
let synths = {};
let silentSynths = {};
let recorder = null;
let activeSequence = null;
let activeLoopName = null;
let fft = null;
let eqBars = [];
let animFrameId = null;
let masterBus = null;

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

async function initAudioContext() {
    if (isAudioInitialized) return;
    await Tone.start();

    if (!masterBus) {
        masterBus = new Tone.Channel().toDestination();
        fft = new Tone.FFT(128);
        masterBus.connect(fft);
    }

    // Normal synths (loud)
    synths = {
        synth: new Tone.PolySynth(Tone.Synth).connect(masterBus),
        amSynth: new Tone.PolySynth(Tone.AMSynth).connect(masterBus),
        fmSynth: new Tone.PolySynth(Tone.FMSynth).connect(masterBus),
        piano: new Tone.Sampler({
            urls: { "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3" },
            release: 1,
            baseUrl: "https://tonejs.github.io/audio/salamander/"
        }).connect(masterBus),
        drums: createDrumKit(masterBus)
    };

    // Silent synths for background rendering
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
    const createDrum = (synthNode) => {
        synthNode.connect(dest);
        return synthNode;
    };

    const kick = createDrum(new Tone.MembraneSynth());
    const snare = createDrum(new Tone.NoiseSynth({
        noise: { type: "white" },
        envelope: { attack: 0.001, decay: 0.2, sustain: 0 }
    }));
    const hihat = createDrum(new Tone.MetalSynth({
        frequency: 200,
        envelope: { attack: 0.001, decay: 0.1, release: 0.01 },
        harmonicity: 5.1, modulationIndex: 32, resonance: 4000, octaves: 1.5
    }));
    const openHat = createDrum(new Tone.MetalSynth({
        frequency: 200,
        envelope: { attack: 0.001, decay: 0.4, release: 0.1 },
        harmonicity: 5.1, modulationIndex: 32, resonance: 4000, octaves: 1.5
    }));
    const tomH = createDrum(new Tone.MembraneSynth({ pitchDecay: 0.05, octaves: 4, oscillator: { type: "sine" } }));
    const tomL = createDrum(new Tone.MembraneSynth({ pitchDecay: 0.05, octaves: 4, oscillator: { type: "sine" } }));
    const clap = createDrum(new Tone.NoiseSynth({
        noise: { type: "pink" },
        envelope: { attack: 0.001, decay: 0.3, sustain: 0 }
    }));
    const crash = createDrum(new Tone.MetalSynth({
        frequency: 300,
        envelope: { attack: 0.001, decay: 1.0, release: 0.5 },
        harmonicity: 5.1, modulationIndex: 32, resonance: 4000, octaves: 1.5
    }));

    return {
        triggerAttackRelease: (note, duration, time, velocity) => {
            switch(note) {
                case "Kick": kick.triggerAttackRelease("C2", duration, time, velocity); break;
                case "Snare": snare.triggerAttackRelease(duration, time, velocity); break;
                case "HiHat": hihat.triggerAttackRelease("32n", time, velocity); break;
                case "OpenHat": openHat.triggerAttackRelease("8n", time, velocity); break;
                case "Clap": clap.triggerAttackRelease(duration, time, velocity); break;
                case "Tom H": tomH.triggerAttackRelease("C4", duration, time, velocity); break;
                case "Tom L": tomL.triggerAttackRelease("C3", duration, time, velocity); break;
                case "Crash": crash.triggerAttackRelease("1n", time, velocity); break;
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
    loopsData.forEach(loop => {
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
        info.innerHTML = `
            <div class="item-name">${loop.name}</div>
            <div class="item-meta">
                <span><span class="material-icons">speed</span> ${loop.bpm} BPM</span>
                <span><span class="material-icons">piano</span> ${loop.instrument}</span>
                <span><span class="material-icons">straighten</span> ${loop.steps} steps</span>
            </div>
        `;

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

        btnPlay.addEventListener('click', () => playLoop(loop, btnPlay, btnPause, btnStop));
        btnPause.addEventListener('click', () => pauseLoop(btnPlay, btnPause));
        btnStop.addEventListener('click', () => stopLoop(btnPlay, btnPause, btnStop));

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
    checkAll.checked = loopsData.length > 0 && selectedLoops.size === loopsData.length;
}

function setupEventListeners() {
    document.body.addEventListener('click', initAudioContext, { once: true });

    checkAll.addEventListener('change', (e) => {
        if (e.target.checked) {
            loopsData.forEach(l => selectedLoops.add(l._filename));
        } else {
            selectedLoops.clear();
        }
        renderCatalog(); // lazy way to update all checkboxes
    });

    btnDownload.addEventListener('click', batchExport);
    btnDelete.addEventListener('click', bulkDelete);
}

// --- Playback Logic ---
async function playLoop(loopData, btnPlay, btnPause, btnStop) {
    await initAudioContext();
    if (Tone.context.state !== 'running') await Tone.start();
    
    // If it's already the active loop and we are resuming from pause
    if (activeSequence && activeLoopName === loopData.name && Tone.Transport.state === 'paused') {
        Tone.Transport.start();
        btnPlay.disabled = true;
        btnPause.disabled = false;
        return;
    }

    // Stop any existing entirely different loop
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        document.querySelectorAll('.catalog-item .play').forEach(b => { b.disabled = false; });
        document.querySelectorAll('.catalog-item .pause').forEach(b => { b.disabled = true; });
        document.querySelectorAll('.catalog-item .stop').forEach(b => { b.disabled = true; });
    }

    activeLoopName = loopData.name;
    btnPlay.disabled = true;
    btnPause.disabled = false;
    btnStop.disabled = false;

    Tone.Transport.bpm.value = loopData.bpm || 120;
    Tone.Transport.swing = loopData.swing || 0.0;
    Tone.Transport.swingSubdivision = "8n";

    const currentSynth = synths[loopData.instrument] || synths.piano;
    const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);
    
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
    
    const values = fft.getValue();
    for (let i = 0; i < eqBars.length; i++) {
        // Values array may be larger than 72, we just take the first 72 bands
        let db = values[i] !== undefined ? values[i] : -100;
        if (!isFinite(db)) db = -100;
        
        // More sensitive
        let normalized = (db + 75) / 65; 
        if (normalized < 0) normalized = 0;
        if (normalized > 1) normalized = 1;
        
        normalized = Math.pow(normalized, 1.2);
        
        let height = 4 + (normalized * 36); 
        eqBars[i].style.height = `${height}px`;
    }
    
    animFrameId = requestAnimationFrame(renderEq);
}

function pauseLoop(btnPlay, btnPause) {
    if (activeSequence && Tone.Transport.state === 'started') {
        Tone.Transport.pause();
        btnPlay.disabled = false;
        btnPause.disabled = true;
    }
}

function stopLoop(btnPlay, btnPause, btnStop) {
    if (activeSequence) {
        Tone.Transport.stop();
        activeSequence.stop();
        activeSequence.dispose();
        activeSequence = null;
    }
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
