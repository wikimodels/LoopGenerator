// App State
const state = {
    loopName: "My New Loop",
    bpm: 120,
    instrument: "piano",
    steps: 16,
    key: "C",
    scale: "Major",
    swing: 0.0,
    notes: [], // Will be populated dynamically
    grid: [], // 2D array [rowIndex][stepIndex] -> boolean
    gridMeta: [], // 2D array [rowIndex][stepIndex] -> { duration, velocity, chance }
    isPlaying: false,
    rating: 0
};

let catalogLoops = [];
let catalogSearchQuery = '';

// Helper: Generate 8 notes for the grid based on key and scale
function generateScale(root, scaleType) {
    const chromatic = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    let intervals;
    if (scaleType === 'Major') {
        intervals = [2, 2, 1, 2, 2, 2, 1];
    } else if (scaleType === 'Minor') {
        intervals = [2, 1, 2, 2, 1, 2, 2];
    } else if (scaleType === 'Pentatonic') {
        // Major pentatonic
        intervals = [2, 2, 3, 2, 3];
    } else {
        intervals = [2, 2, 1, 2, 2, 2, 1];
    }

    let startIdx = chromatic.indexOf(root);
    let currentOctave = 4;
    let notes = [];
    
    let currentIdx = startIdx;
    let intervalIdx = 0;
    
    // Generate exactly 8 notes for a consistent grid
    for (let i = 0; i < 8; i++) {
        notes.push(chromatic[currentIdx] + currentOctave);
        
        let step = intervals[intervalIdx % intervals.length];
        currentIdx += step;
        if (currentIdx >= 12) {
            currentIdx -= 12;
            currentOctave++;
        }
        intervalIdx++;
    }
    
    // Highest pitch at the top (index 0)
    return notes.reverse();
}

function rebuildGridData() {
    if (state.instrument === 'drums') {
        state.notes = ["Crash", "Tom H", "Tom L", "OpenHat", "HiHat", "Clap", "Snare", "Kick"];
        document.getElementById('key-select').disabled = true;
        document.getElementById('scale-select').disabled = true;
    } else {
        state.notes = generateScale(state.key, state.scale);
        document.getElementById('key-select').disabled = false;
        document.getElementById('scale-select').disabled = false;
    }
    state.grid = [];
    state.gridMeta = [];
    for (let r = 0; r < state.notes.length; r++) {
        state.grid.push(new Array(state.steps).fill(false));
        state.gridMeta.push(new Array(state.steps).fill(null).map(() => ({ duration: "8n", velocity: 1.0, chance: 1.0 })));
    }
}

// Initialize grid data on load
rebuildGridData();

// Tone.js Synths
let synths = null;
let currentSynth = null;
let toneSequence = null;
let isAudioInitialized = false;

// DOM Elements
const gridContainer = document.getElementById('sequencer-grid');
const playBtn = document.getElementById('btn-play');
const stopBtn = document.getElementById('btn-stop');
const clearBtn = document.getElementById('btn-clear');
const saveBtn = document.getElementById('btn-save');
const exportBtn = document.getElementById('btn-export');
const insertBtn = document.getElementById('btn-insert-json');
const bpmSlider = document.getElementById('bpm-slider');
const bpmVal = document.getElementById('bpm-val');
const loopNameInput = document.getElementById('loop-name');
const instrumentSelect = document.getElementById('instrument-select');
const keySelect = document.getElementById('key-select');
const scaleSelect = document.getElementById('scale-select');
const stepsSelect = document.getElementById('steps-select');
const loopList = document.getElementById('loop-list');
const toastEl = document.getElementById('toast');

const btnInstructions = document.getElementById('btn-instructions');
const btnCloseModal = document.getElementById('btn-close-modal');
const instructionsModal = document.getElementById('instructions-modal');

const insertModal = document.getElementById('insert-modal');
const btnCloseInsert = document.getElementById('btn-close-insert');
const jsonPasteArea = document.getElementById('json-paste-area');
const btnImportPasted = document.getElementById('btn-import-pasted');
const btnCopyPrompt = document.getElementById('btn-copy-prompt');
const aiPromptText = document.getElementById('ai-prompt-text');

// --- Initialization ---
async function init() {
    createGridUI();
    setupEventListeners();
    await fetchLoops();
}

async function initAudioContext() {
    if (isAudioInitialized) return;
    await Tone.start();
    
    synths = {
        synth: new Tone.PolySynth(Tone.Synth).toDestination(),
        amSynth: new Tone.PolySynth(Tone.AMSynth).toDestination(),
        fmSynth: new Tone.PolySynth(Tone.FMSynth).toDestination(),
        piano: new Tone.Sampler({
            urls: {
                "C4": "C4.mp3",
                "D#4": "Ds4.mp3",
                "F#4": "Fs4.mp3",
                "A4": "A4.mp3",
                "C5": "C5.mp3"
            },
            release: 1,
            baseUrl: "https://tonejs.github.io/audio/salamander/"
        }).toDestination(),
        drums: createDrumKit()
    };
    
    currentSynth = synths[state.instrument] || synths.piano;
    isAudioInitialized = true;
}

function createDrumKit() {
    const kick = new Tone.MembraneSynth().toDestination();
    const snare = new Tone.NoiseSynth({
        noise: { type: "white" },
        envelope: { attack: 0.001, decay: 0.2, sustain: 0 }
    }).toDestination();
    const hihat = new Tone.NoiseSynth({
        noise: { type: "white" },
        envelope: { attack: 0.001, decay: 0.05, sustain: 0 }
    }).toDestination();
    const openHat = new Tone.NoiseSynth({
        noise: { type: "white" },
        envelope: { attack: 0.01, decay: 0.3, sustain: 0 }
    }).toDestination();
    const tomH = new Tone.MembraneSynth({ pitchDecay: 0.05, octaves: 4, oscillator: { type: "sine" } }).toDestination();
    const tomL = new Tone.MembraneSynth({ pitchDecay: 0.05, octaves: 4, oscillator: { type: "sine" } }).toDestination();
    const clap = new Tone.NoiseSynth({
        noise: { type: "pink" },
        envelope: { attack: 0.001, decay: 0.3, sustain: 0 }
    }).toDestination();
    const crash = new Tone.NoiseSynth({
        noise: { type: "pink" },
        envelope: { attack: 0.01, decay: 1.5, sustain: 0 }
    }).toDestination();

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

function createGridUI() {
    gridContainer.innerHTML = '';
    // Columns: 1 for label + state.steps
    // minmax ensures cells don't get larger than 32px but can shrink to 10px if needed to fit
    gridContainer.style.gridTemplateColumns = `max-content repeat(${state.steps}, minmax(10px, 32px))`;

    for (let r = 0; r < state.notes.length; r++) {
        // Label
        const label = document.createElement('div');
        label.className = 'row-label';
        label.innerText = state.notes[r];
        gridContainer.appendChild(label);

        // Cells
        for (let c = 0; c < state.steps; c++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            if (state.grid[r][c]) cell.classList.add('active');
            
            cell.dataset.row = r;
            cell.dataset.col = c;
            
            cell.addEventListener('click', () => {
                toggleCell(r, c, cell);
            });
            
            gridContainer.appendChild(cell);
        }
    }
}

function toggleCell(r, c, cellElement) {
    state.grid[r][c] = !state.grid[r][c];
    if (state.grid[r][c]) {
        // Reset meta on manual toggle
        state.gridMeta[r][c] = { duration: "8n", velocity: 1.0, chance: 1.0 };
        cellElement.classList.add('active');
        // Preview note
        if (isAudioInitialized) {
            if (Tone.context.state !== 'running') Tone.start();
            currentSynth.triggerAttackRelease(state.notes[r], "8n", undefined, 1.0);
        }
    } else {
        cellElement.classList.remove('active');
    }
}

function setupEventListeners() {
    // Initialize audio on first click anywhere
    document.body.addEventListener('click', initAudioContext, { once: true });

    playBtn.addEventListener('click', async () => {
        await initAudioContext();
        await Tone.start();
        
        const playIcon = document.getElementById('play-icon');
        
        if (state.isPlaying) {
            Tone.Transport.pause();
            state.isPlaying = false;
            if (playIcon) playIcon.innerText = 'play_arrow';
            playBtn.classList.remove('paused');
            return;
        }
        
        Tone.Transport.bpm.value = state.bpm;
        Tone.Transport.swing = state.swing;
        Tone.Transport.swingSubdivision = "8n";
        
        if (!toneSequence) {
            setupSequence();
        }
        
        Tone.Transport.start();
        state.isPlaying = true;
        if (playIcon) playIcon.innerText = 'pause';
        playBtn.classList.add('paused');
    });

    stopBtn.addEventListener('click', () => {
        Tone.Transport.stop();
        if (toneSequence) {
            toneSequence.stop();
            toneSequence.dispose();
            toneSequence = null;
        }
        state.isPlaying = false;
        
        const playIcon = document.getElementById('play-icon');
        if (playIcon) playIcon.innerText = 'play_arrow';
        playBtn.classList.remove('paused');
        
        // Remove playing class from all cells
        document.querySelectorAll('.grid-cell.playing').forEach(el => el.classList.remove('playing'));
    });

    clearBtn.addEventListener('click', () => {
        for (let r = 0; r < state.notes.length; r++) {
            state.grid[r].fill(false);
        }
        createGridUI();
    });

    bpmSlider.addEventListener('input', (e) => {
        state.bpm = e.target.value;
        bpmVal.innerText = state.bpm;
        Tone.Transport.bpm.value = state.bpm;
    });

    const swingSlider = document.getElementById('swing-slider');
    const swingVal = document.getElementById('swing-val');

    swingSlider.addEventListener('input', (e) => {
        state.swing = parseFloat(e.target.value);
        swingVal.innerText = state.swing.toFixed(2);
        Tone.Transport.swing = state.swing;
        Tone.Transport.swingSubdivision = "8n";
    });

    loopNameInput.addEventListener('change', (e) => {
        state.loopName = e.target.value;
    });

    instrumentSelect.addEventListener('change', (e) => {
        const oldIsDrums = state.instrument === 'drums';
        state.instrument = e.target.value;
        const newIsDrums = state.instrument === 'drums';
        
        if (isAudioInitialized) {
            currentSynth = synths[state.instrument] || synths.piano;
        }

        if (oldIsDrums !== newIsDrums) {
            handleScaleChange(); // Rebuild grid when switching to/from drums
        }
    });

    keySelect.addEventListener('change', (e) => {
        state.key = e.target.value;
        handleScaleChange();
    });

    scaleSelect.addEventListener('change', (e) => {
        state.scale = e.target.value;
        handleScaleChange();
    });

    stepsSelect.addEventListener('change', (e) => {
        state.steps = parseInt(e.target.value);
        // Resize existing grid without losing notes
        let newGrid = [];
        let newMeta = [];
        for (let r = 0; r < state.notes.length; r++) {
            let newRow = new Array(state.steps).fill(false);
            let newMetaRow = new Array(state.steps).fill(null).map(() => ({ duration: "8n", velocity: 1.0, chance: 1.0 }));
            for (let c = 0; c < Math.min(state.steps, state.grid[r].length); c++) {
                newRow[c] = state.grid[r][c];
                newMetaRow[c] = state.gridMeta[r][c];
            }
            newGrid.push(newRow);
            newMeta.push(newMetaRow);
        }
        state.grid = newGrid;
        state.gridMeta = newMeta;
        createGridUI();
        if (state.isPlaying) setupSequence();
    });

    saveBtn.addEventListener('click', saveLoop);
    
    exportBtn.addEventListener('click', async () => {
        if (state.isPlaying) {
            showToast("Please stop playback before exporting.");
            return;
        }
        await initAudioContext();
        await Tone.start();
        
        showToast("Recording audio... Please wait.");
        exportBtn.disabled = true;

        const recorder = new Tone.Recorder();
        Tone.getDestination().connect(recorder);

        Tone.Transport.bpm.value = state.bpm;
        Tone.Transport.swing = state.swing;
        Tone.Transport.swingSubdivision = "8n";
        setupSequence();
        
        // 8n = 2 steps per beat. 
        const beats = state.steps / 2;
        const durationSec = beats * (60 / state.bpm);

        // Tell sequence to only loop once
        toneSequence.loop = 1;

        recorder.start();
        Tone.Transport.start();

        // Wait for loop to finish + 1.5 seconds for audio tail (reverb/release)
        setTimeout(async () => {
            Tone.Transport.stop();
            const recording = await recorder.stop();
            
            // Download file
            const url = URL.createObjectURL(recording);
            const anchor = document.createElement("a");
            anchor.download = `${state.loopName.replace(/\s+/g, '_')}.webm`;
            anchor.href = url;
            anchor.click();

            exportBtn.disabled = false;
            showToast("Export complete!");
            
            // Reset looping for normal playback
            toneSequence.loop = true;
        }, (durationSec + 1.5) * 1000);
    });

    insertBtn.addEventListener('click', () => {
        insertModal.classList.remove('hidden');
    });

    btnCloseInsert.addEventListener('click', () => {
        insertModal.classList.add('hidden');
    });

    insertModal.addEventListener('click', (e) => {
        if (e.target === insertModal) {
            insertModal.classList.add('hidden');
        }
    });

    btnInstructions.addEventListener('click', () => {
        instructionsModal.classList.remove('hidden');
    });

    btnCloseModal.addEventListener('click', () => {
        instructionsModal.classList.add('hidden');
    });

    instructionsModal.addEventListener('click', (e) => {
        if (e.target === instructionsModal) {
            instructionsModal.classList.add('hidden');
        }
    });

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

    btnCopyPrompt.addEventListener('click', () => {
        aiPromptText.select();
        document.execCommand('copy');
        showToast("Prompt copied to clipboard!");
    });

    // --- Sidebar Search Logic ---
    const sidebarHeader = document.getElementById('sidebar-header');
    const btnSearch = document.getElementById('btn-sidebar-search');
    const btnSearchClose = document.getElementById('btn-sidebar-search-close');
    const searchInput = document.getElementById('sidebar-search-input');

    if (btnSearch && sidebarHeader && searchInput) {
        btnSearch.addEventListener('click', () => {
            sidebarHeader.classList.add('search-active');
            searchInput.focus();
        });

        btnSearchClose.addEventListener('click', () => {
            sidebarHeader.classList.remove('search-active');
            searchInput.value = '';
            catalogSearchQuery = '';
            renderCatalog();
        });

        searchInput.addEventListener('input', (e) => {
            catalogSearchQuery = e.target.value;
            renderCatalog();
        });
    }

    const starRatingContainer = document.getElementById('current-loop-rating');
    if (starRatingContainer) {
        starRatingContainer.querySelectorAll('.star').forEach(star => {
            star.addEventListener('click', async (e) => {
                const val = parseInt(e.target.dataset.value);
                state.rating = state.rating === val ? 0 : val;
                
                starRatingContainer.querySelectorAll('.star').forEach((s, idx) => {
                    s.classList.toggle('filled', idx < state.rating);
                });

                if (state.loopName && state.loopName !== "My New Loop") {
                    try {
                        const filename = state.loopName.replace(/\s+/g, '_') + '.json';
                        await fetch(`/api/meta/${filename}`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ rating: state.rating })
                        });
                        showToast("Rating saved!");
                        fetchLoops(); // Update catalog stars silently
                    } catch(e) { console.error(e); }
                }
            });
            star.addEventListener('mouseenter', (e) => {
                const val = parseInt(e.target.dataset.value);
                starRatingContainer.querySelectorAll('.star').forEach((s, idx) => {
                    s.classList.toggle('hovered', idx < val);
                });
            });
            star.addEventListener('mouseleave', () => {
                starRatingContainer.querySelectorAll('.star').forEach(s => s.classList.remove('hovered'));
            });
        });
    }
}

function handleScaleChange() {
    // Save current active notes before destroying the grid
    let activeOldNotes = [];
    for (let r = 0; r < state.notes.length; r++) {
        for (let c = 0; c < state.steps; c++) {
            if (state.grid[r][c]) {
                activeOldNotes.push({ note: state.notes[r], step: c });
            }
        }
    }

    rebuildGridData();
    
    // Try to map old notes to new grid rows.
    // If the exact note string exists in the new scale, keep it. 
    // Otherwise, we lose it to avoid playing completely wrong notes in the new scale.
    activeOldNotes.forEach(n => {
        let newR = state.notes.indexOf(n.note);
        if (newR !== -1 && n.step < state.steps) {
            state.grid[newR][n.step] = true;
            // Best effort to preserve metadata if we wanted to, but let's just reset
            state.gridMeta[newR][n.step] = { duration: "8n", velocity: 1.0 };
        }
    });

    createGridUI();
    if (state.isPlaying) {
        setupSequence();
    }
}

function setupSequence() {
    if (toneSequence) {
        toneSequence.dispose();
    }

    // Create an array of step indices
    const steps = Array.from({length: state.steps}, (_, i) => i);

    toneSequence = new Tone.Sequence((time, step) => {
        // Collect and play notes for this step
        for (let r = 0; r < state.notes.length; r++) {
            if (state.grid[r][step]) {
                const note = state.notes[r];
                const meta = state.gridMeta[r][step] || { duration: "8n", velocity: 1.0, chance: 1.0 };
                
                if (Math.random() <= meta.chance) {
                    currentSynth.triggerAttackRelease(note, meta.duration, time, meta.velocity);
                }
            }
        }

        // Draw UI (must be deferred to the animation frame)
        Tone.Draw.schedule(() => {
            // Remove playing from all
            document.querySelectorAll('.grid-cell.playing').forEach(el => el.classList.remove('playing'));
            // Add playing to current column
            document.querySelectorAll(`.grid-cell[data-col="${step}"]`).forEach(el => el.classList.add('playing'));
        }, time);

    }, steps, "8n").start(0);
}

// --- API & Data logic ---

function showToast(msg) {
    toastEl.innerText = msg;
    toastEl.classList.remove('hidden');
    setTimeout(() => {
        toastEl.classList.add('hidden');
    }, 3000);
}

function getLoopData() {
    let activeNotes = [];
    for (let r = 0; r < state.notes.length; r++) {
        for (let c = 0; c < state.steps; c++) {
            if (state.grid[r][c]) {
                const meta = state.gridMeta[r][c];
                activeNotes.push({
                    step: c,
                    note: state.notes[r],
                    duration: meta.duration || "8n",
                    velocity: meta.velocity || 1.0
                });
            }
        }
    }
    return {
        name: state.loopName,
        bpm: state.bpm,
        instrument: state.instrument,
        steps: state.steps,
        key: state.key,
        scale: state.scale,
        swing: state.swing,
        rating: state.rating,
        notes: activeNotes
    };
}

function loadLoopData(data) {
    if (!data) return;
    
    state.loopName = data.name || "Loaded Loop";
    loopNameInput.value = state.loopName;
    
    state.bpm = data.bpm || 120;
    bpmSlider.value = state.bpm;
    bpmVal.innerText = state.bpm;
    Tone.Transport.bpm.value = state.bpm;

    state.swing = data.swing || 0.0;
    const swingSlider = document.getElementById('swing-slider');
    const swingVal = document.getElementById('swing-val');
    if (swingSlider && swingVal) {
        swingSlider.value = state.swing;
        swingVal.innerText = state.swing.toFixed(2);
    }
    Tone.Transport.swing = state.swing;
    Tone.Transport.swingSubdivision = "8n";

    state.instrument = data.instrument || "piano";
    instrumentSelect.value = state.instrument;
    if (isAudioInitialized) {
        currentSynth = synths[state.instrument] || synths.piano;
    }

    state.steps = data.steps || 16;
    stepsSelect.value = state.steps;

    state.key = data.key || "C";
    keySelect.value = state.key;

    state.scale = data.scale || "Major";
    scaleSelect.value = state.scale;

    // Reset grid
    rebuildGridData();

    // Populate grid
    if (data.notes) {
        data.notes.forEach(n => {
            let r = state.notes.indexOf(n.note);
            if (r !== -1 && n.step < state.steps) {
                state.grid[r][n.step] = true;
                state.gridMeta[r][n.step] = {
                    duration: n.duration || "8n",
                    velocity: n.velocity !== undefined ? n.velocity : 1.0,
                    chance: n.chance !== undefined ? n.chance : 1.0
                };
            }
        });
    }

    state.rating = data.rating || 0;
    const starRatingContainer = document.getElementById('current-loop-rating');
    if (starRatingContainer) {
        starRatingContainer.querySelectorAll('.star').forEach((s, idx) => {
            s.classList.toggle('filled', idx < state.rating);
        });
    }

    createGridUI();
    showToast("Loop loaded!");
}

async function fetchLoops() {
    try {
        const res = await fetch(`/api/loops?t=${Date.now()}`);
        catalogLoops = await res.json();
        renderCatalog();
    } catch (e) {
        console.error("Failed to fetch loops", e);
    }
}

function renderCatalog() {
    loopList.innerHTML = '';
    
    const filtered = catalogLoops.filter(loop => {
        if (!catalogSearchQuery) return true;
        const name = loop.name || "";
        return name.toLowerCase().includes(catalogSearchQuery.toLowerCase());
    });

    filtered.forEach(loop => {
        const div = document.createElement('div');
        div.className = 'loop-item';
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'name';
        nameSpan.innerText = loop.name;
        
        const btnDelete = document.createElement('button');
        btnDelete.className = 'delete-btn';
        btnDelete.innerHTML = '<span class="material-icons">delete</span>';
        
        // Load on click
        nameSpan.addEventListener('click', () => {
            loadLoopData(loop);
        });

        btnDelete.addEventListener('click', async (e) => {
            e.stopPropagation();
            await deleteLoop(loop._filename);
        });

        div.appendChild(nameSpan);
        div.appendChild(btnDelete);
        loopList.appendChild(div);
    });
}

async function saveLoop() {
    const data = getLoopData();
    try {
        const res = await fetch('/api/loops', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.status === 'success') {
            showToast("Loop saved!");
            fetchLoops(); // Refresh catalog
        }
    } catch (e) {
        console.error(e);
        showToast("Error saving loop");
    }
}

async function deleteLoop(filename) {
    if (!confirm("Are you sure you want to delete this loop?")) return;
    try {
        const res = await fetch(`/api/loops/${filename}`, {
            method: 'DELETE'
        });
        if (res.ok) {
            showToast("Loop deleted");
            fetchLoops();
        }
    } catch (e) {
        console.error(e);
        showToast("Error deleting loop");
    }
}

// Start app
document.addEventListener('DOMContentLoaded', init);
