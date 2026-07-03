// ============================================================
// generate.js — Loop Generator UI logic
// ============================================================

const STYLES = [
    { id: "neoclassical_major",   icon: "🎹", name: "Neoclassical · Major",       desc: "Arpeggio + melody, bright key" },
    { id: "neoclassical_minor",   icon: "🎹", name: "Neoclassical · Minor",       desc: "Arpeggio + melody, dark key" },
    { id: "baroque_major",        icon: "🎻", name: "Baroque · Major",            desc: "Circle-of-fifths, polyphony" },
    { id: "baroque_minor",        icon: "🎻", name: "Baroque · Minor",            desc: "Circle-of-fifths, polyphony minor" },
    { id: "jazz_major",           icon: "🎷", name: "Jazz · Major",               desc: "Walking bass + shell comping" },
    { id: "jazz_minor",           icon: "🎷", name: "Jazz · Minor",               desc: "ii°-V-i, blue notes" },
    { id: "modal_folk",           icon: "🪕", name: "Modal Folk",                 desc: "Dorian drone, folk melody" },
    { id: "classical_alberti",    icon: "🎼", name: "Classical · Alberti Bass",   desc: "Mozart/Haydn broken-triad pattern" },
    { id: "renaissance_dorian",   icon: "🏰", name: "Renaissance · Dorian",       desc: "4-voice imitation, Phrygian cadence" },
    { id: "renaissance_phrygian", icon: "🏰", name: "Renaissance · Phrygian",     desc: "4-voice imitation, Phrygian mode" },
    { id: "renaissance_mixolydian", icon: "🏰", name: "Renaissance · Mixolydian", desc: "4-voice imitation, Landini cadence" },
];

let selectedStyle = STYLES[0].id;
let nameOverride = false;   // true when user typed something in the name field

// ── Build style cards ─────────────────────────────────────────
const grid = document.getElementById("style-grid");
STYLES.forEach(s => {
    const card = document.createElement("div");
    card.className = "style-card" + (s.id === selectedStyle ? " selected" : "");
    card.dataset.id = s.id;
    card.innerHTML = `
        <span class="sc-icon">${s.icon}</span>
        <span class="sc-name">${s.name}</span>
        <span class="sc-desc">${s.desc}</span>
    `;
    card.addEventListener("click", () => {
        document.querySelectorAll(".style-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        selectedStyle = s.id;
        if (!nameOverride) syncName();
    });
    grid.appendChild(card);
});

// ── Auto-name ─────────────────────────────────────────────────
function autoName() {
    const style = STYLES.find(s => s.id === selectedStyle);
    const key   = document.getElementById("sel-key").value;
    const bpm   = document.getElementById("bpm-number").value;
    // match what generate_loop() produces: "Style Title in Key"
    const title = selectedStyle.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    return `${title} in ${key}`;
}

function syncName() {
    if (!nameOverride) document.getElementById("name-input").value = autoName();
}

document.getElementById("sel-key").addEventListener("change", syncName);
document.getElementById("btn-reset-name").addEventListener("click", () => {
    nameOverride = false;
    document.getElementById("name-input").value = autoName();
});
document.getElementById("name-input").addEventListener("input", () => {
    nameOverride = true;
});
syncName();

// ── BPM slider ↔ number ───────────────────────────────────────
const bpmSlider = document.getElementById("bpm-slider");
const bpmNumber = document.getElementById("bpm-number");
bpmSlider.addEventListener("input", () => { bpmNumber.value = bpmSlider.value; syncName(); });
bpmNumber.addEventListener("input", () => {
    const v = Math.min(240, Math.max(40, parseInt(bpmNumber.value) || 100));
    bpmSlider.value = v;
    bpmNumber.value = v;
});

// ── Seed controls ─────────────────────────────────────────────
const seedEnable = document.getElementById("seed-enable");
const seedValue  = document.getElementById("seed-value");
const btnRandom  = document.getElementById("btn-random-seed");

seedEnable.addEventListener("change", () => {
    const on = seedEnable.checked;
    seedValue.disabled  = !on;
    btnRandom.disabled  = !on;
});
btnRandom.addEventListener("click", () => {
    seedValue.value = Math.floor(Math.random() * 100000);
});

// ── Generate ──────────────────────────────────────────────────
const btnGenerate = document.getElementById("btn-generate");
const resultCard  = document.getElementById("gen-result");
const resultIcon  = document.getElementById("result-icon");
const resultTitle = document.getElementById("result-title");
const resultMeta  = document.getElementById("result-meta");

btnGenerate.addEventListener("click", async () => {
    const name  = document.getElementById("name-input").value.trim();
    const key   = document.getElementById("sel-key").value;
    const bpm   = parseInt(bpmNumber.value);
    const steps = parseInt(document.getElementById("sel-steps").value);
    const seed  = seedEnable.checked ? parseInt(seedValue.value) : null;

    const payload = { style: selectedStyle, key, bpm, steps };
    if (name) payload.name = name;
    if (seed !== null && !isNaN(seed)) payload.seed = seed;

    btnGenerate.disabled = true;
    btnGenerate.innerHTML = '<span class="material-icons">hourglass_empty</span> Generating...';
    resultCard.classList.add("hidden");

    try {
        const res = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Server error");
        }

        const loop = data.loop;
        resultCard.classList.remove("hidden", "error");
        resultIcon.textContent  = "✓";
        resultTitle.textContent = loop.name;
        resultMeta.innerHTML =
            `Style: <strong>${loop.style.replace(/_/g," ")}</strong> &nbsp;·&nbsp; ` +
            `Key: <strong>${loop.key} ${loop.scale}</strong> &nbsp;·&nbsp; ` +
            `BPM: <strong>${loop.bpm}</strong> &nbsp;·&nbsp; ` +
            `Steps: <strong>${loop.steps}</strong> &nbsp;·&nbsp; ` +
            `Notes: <strong>${loop.notes.length}</strong><br>` +
            `Saved as: <code style="font-size:.72rem;opacity:.7">${data.filename}</code>`;

    } catch (err) {
        resultCard.classList.remove("hidden");
        resultCard.classList.add("error");
        resultIcon.textContent  = "✗";
        resultTitle.textContent = "Generation failed";
        resultMeta.textContent  = err.message;
    } finally {
        btnGenerate.disabled = false;
        btnGenerate.innerHTML = '<span class="material-icons">bolt</span> Generate &amp; Save';
    }
});

document.getElementById("btn-generate-another").addEventListener("click", () => {
    resultCard.classList.add("hidden");
    if (!nameOverride) syncName();
});
