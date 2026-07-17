// ============================================================
// generate.js — Loop Generator UI logic
// ============================================================

const STYLES = [
    { id: "neoclassical_major",    icon: "🎹", name: "Neoclassical · Major",          desc: "Arpeggio + melody, bright key" },
    { id: "neoclassical_minor",    icon: "🎹", name: "Neoclassical · Minor",          desc: "Arpeggio + melody, dark key" },
    { id: "baroque_major",         icon: "🎻", name: "Baroque · Major",               desc: "Pachelbel / Passamezzo · Alberti, broken arp" },
    { id: "baroque_minor",         icon: "🎻", name: "Baroque · Minor",               desc: "Andalusian / La Folia / Romanesca · random texture" },
    { id: "baroque_passacaglia",   icon: "⛪", name: "Baroque · Passacaglia",         desc: "Chromatic lament bass · walking + block chords (Purcell, Bach)" },
    { id: "baroque_pachelbel",     icon: "🕍", name: "Baroque · Pachelbel",           desc: "I–V–vi–iii–IV–I–IV–V · broken arpeggio" },
    { id: "baroque_circle",        icon: "🌀", name: "Baroque · Circle of Fifths",    desc: "i–iv–VII–III–VI–ii°–V–i · Alberti/murky, 2-voice counterpoint" },
    { id: "baroque_folia",         icon: "💃", name: "Baroque · La Folia",            desc: "8-chord ostinato · fast Alberti (Corelli, Vivaldi)" },
    { id: "jazz_major",            icon: "🎷", name: "Jazz · Major",                  desc: "Walking bass + shell comping" },
    { id: "jazz_minor",            icon: "🎷", name: "Jazz · Minor",                  desc: "ii°-V-i, blue notes" },
    { id: "modal_folk",            icon: "🪕", name: "Modal Folk",                    desc: "Dorian drone, folk melody" },
    { id: "classical_alberti",     icon: "🎼", name: "Classical · Alberti Bass",      desc: "Mozart/Haydn broken-triad pattern" },
    { id: "renaissance_dorian",    icon: "🏰", name: "Renaissance · Dorian",          desc: "4-voice imitation, Phrygian cadence" },
    { id: "renaissance_phrygian",  icon: "🏰", name: "Renaissance · Phrygian",        desc: "4-voice imitation, Phrygian mode" },
    { id: "renaissance_mixolydian",icon: "🏰", name: "Renaissance · Mixolydian",      desc: "4-voice imitation, Landini cadence" },
    { id: "bossa_nova",            icon: "🌴", name: "Bossa Nova",                    desc: "Clave syncopation, complex jazz chords" },
    { id: "lofi",                  icon: "🎧", name: "Lo-Fi Hip Hop",                 desc: "Lazy arpeggiato, heavy swing, maj9 chords" },
    { id: "neo_soul",              icon: "🎵", name: "Neo-Soul / Gospel",             desc: "Passing diminished chords, grace notes" },
    { id: "video_game",            icon: "👾", name: "Video Game / 8-bit",            desc: "Fast arpeggios, driving 8th bass, heroic melodies" },
    { id: "romantic_major",        icon: "🌹", name: "Romantic · Major",              desc: "Wide arpeggios, rubato melody" },
    { id: "romantic_minor",        icon: "🌹", name: "Romantic · Minor",              desc: "Wide arpeggios, rubato melody in minor" },
    { id: "blues",                 icon: "🎸", name: "Blues",                         desc: "12-bar feel, shuffle bass, blues scale" },
    { id: "ragtime",               icon: "🎹", name: "Ragtime",                       desc: "Syncopated melody, oom-pah bass" },
    { id: "waltz_major",           icon: "🎡", name: "Waltz · Major",                 desc: "Classical waltz pattern, 3/4 time" },
    { id: "waltz_minor",           icon: "🎡", name: "Waltz · Minor",                 desc: "Classical waltz pattern, 3/4 time in minor" },
    { id: "einaudi_major",         icon: "🌊", name: "Neoclassical · Einaudi Major",  desc: "Cinematic, sweeping arpeggios, sparse melody" },
    { id: "einaudi_minor",         icon: "🌊", name: "Neoclassical · Einaudi Minor",  desc: "Cinematic, sweeping arpeggios, sparse melody in minor" },
    { id: "glass_major",           icon: "📐", name: "Minimalist · Glass Major",      desc: "Mathematical arpeggios, shifting accents" },
    { id: "glass_minor",           icon: "📐", name: "Minimalist · Glass Minor",      desc: "Mathematical arpeggios, shifting accents in minor" },
    { id: "tiersen_major",         icon: "🎠", name: "Cinematic · Tiersen Major",     desc: "Fast waltz, rapid scalar melodies" },
    { id: "tiersen_minor",         icon: "🎠", name: "Cinematic · Tiersen Minor",     desc: "Fast waltz, rapid scalar melodies in minor" },
    { id: "frahm_major",           icon: "🌫️", name: "Ambient · Major",               desc: "Pulsing ostinato, soft sustained chords" },
    { id: "frahm_minor",           icon: "🌫️", name: "Ambient · Minor",               desc: "Pulsing ostinato, soft sustained chords in minor" },
];

let selectedStyles = [STYLES[0].id];

// ── Build style cards ─────────────────────────────────────────
const grid = document.getElementById("style-grid");
STYLES.forEach(s => {
    const card = document.createElement("div");
    card.className = "style-card" + (selectedStyles.includes(s.id) ? " selected" : "");
    card.dataset.id = s.id;
    card.innerHTML = `
        <span class="sc-icon">${s.icon}</span>
        <span class="sc-name">${s.name}</span>
        <span class="sc-desc">${s.desc}</span>
    `;
    card.addEventListener("click", () => {
        if (selectedStyles.includes(s.id)) {
            if (selectedStyles.length > 1) {
                selectedStyles = selectedStyles.filter(id => id !== s.id);
                card.classList.remove("selected");
            }
        } else {
            selectedStyles.push(s.id);
            card.classList.add("selected");
        }
    });
    grid.appendChild(card);
});

// ── BPM slider ↔ number ───────────────────────────────────────
const bpmSlider = document.getElementById("bpm-slider");
const bpmNumber = document.getElementById("bpm-number");
bpmSlider.addEventListener("input", () => { bpmNumber.value = bpmSlider.value; syncName(); });
bpmNumber.addEventListener("input", () => {
    const v = Math.min(240, Math.max(40, parseInt(bpmNumber.value) || 100));
    bpmSlider.value = v;
    bpmNumber.value = v;
});

// ── Chip Controls ───────────────────────────────────────────────
document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.classList.toggle('selected');
    });
});

function toggleChips(groupId) {
    const group = document.getElementById(groupId);
    const chips = group.querySelectorAll('.chip-btn');
    const allSelected = Array.from(chips).every(c => c.classList.contains('selected'));
    
    chips.forEach(c => {
        if (allSelected) {
            c.classList.remove('selected');
        } else {
            c.classList.add('selected');
        }
    });
}

function getSelectedValues(groupId) {
    const group = document.getElementById(groupId);
    return Array.from(group.querySelectorAll('.chip-btn.selected')).map(chip => chip.dataset.value);
}

// ── Generate ──────────────────────────────────────────────────
const btnGenerate = document.getElementById("btn-generate");
const resultCard  = document.getElementById("gen-result");
const resultMeta  = document.getElementById("result-meta");
const resultActions = document.getElementById("result-actions");

btnGenerate.addEventListener("click", async () => {
    const keys = getSelectedValues("sel-key");
    const meters = getSelectedValues("sel-meter").map(v => parseInt(v));
    const stepsArr = getSelectedValues("sel-steps").map(v => parseInt(v));
    const bpm = parseInt(document.getElementById("bpm-number").value);
    
    if (selectedStyles.length === 0 || keys.length === 0 || meters.length === 0 || stepsArr.length === 0) {
        alert("Please select at least one item from all parameters.");
        return;
    }

    const totalCombos = selectedStyles.length * keys.length * meters.length * stepsArr.length;
    let completed = 0;

    btnGenerate.disabled = true;
    btnGenerate.innerHTML = '<span class="material-icons">hourglass_empty</span> Generating Batch...';
    resultCard.classList.remove("hidden", "error");
    resultActions.classList.add("hidden");
    resultMeta.textContent = `Generated 0 / ${totalCombos}...`;

    for (const style of selectedStyles) {
        for (const key of keys) {
            for (const beats_per_bar of meters) {
                for (const steps of stepsArr) {
                    const seed = Math.floor(Math.random() * 1000000);
                    const payload = { 
                        style: style, 
                        key: key, 
                        bpm: bpm, 
                        steps: steps, 
                        beats_per_bar: beats_per_bar, 
                        seed: seed,
                        is_batch: true
                    };

                    try {
                        const res = await fetch("/api/generate", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload),
                        });
                        
                        if (!res.ok) {
                            console.error(`Error generating ${style} in ${key}`);
                        }
                    } catch (err) {
                        console.error(err);
                    }
                    
                    completed++;
                    resultMeta.textContent = `Generated ${completed} / ${totalCombos}...`;
                }
            }
        }
    }

    resultMeta.innerHTML = `<strong>Done!</strong> Generated ${totalCombos} tracks and added them to the Catalog.`;
    resultActions.classList.remove("hidden");
    btnGenerate.disabled = false;
    btnGenerate.innerHTML = '<span class="material-icons">bolt</span> Batch Generate';
});
