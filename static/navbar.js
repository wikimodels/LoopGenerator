// navbar.js — shared navigation bar for all pages
// Usage: add <script src="navbar.js"></script> BEFORE the page-specific script.
// On index.html set <body data-page="editor">.
// Other pages don't need data-page (nav links only).

(function () {
    const PAGE = document.body.dataset.page || '';
    const IS_EDITOR = PAGE === 'editor';

    // ── Determine active page from current filename ──────────────────────────
    const path = location.pathname.split('/').pop() || 'index.html';

    function navLink(href, icon, label, extraClass) {
        const active = path === href ? ' nav-active' : '';
        const cls = `btn nav-btn${extraClass ? ' ' + extraClass : ''}${active}`;
        return `<a href="${href}" class="${cls}" title="${label}">
            <span class="material-icons">${icon}</span><span class="nav-label">${label}</span>
        </a>`;
    }

    // ── Navbar HTML ──────────────────────────────────────────────────────────
    const navbarHTML = `
<header class="top-bar shared-navbar" id="shared-navbar">
    <div class="logo">
        <span class="material-icons">graphic_eq</span>
        <span class="logo-text">LoopGen</span>
    </div>
    <nav class="nav-links">
        ${navLink('index.html', 'piano', 'Editor', 'secondary')}
        ${navLink('catalog.html', 'library_music', 'Catalog', 'secondary')}
        ${navLink('golden.html', 'star', 'Golden', 'accent')}
        ${navLink('exports.html', 'graphic_eq', 'Exports', 'neutral')}
        ${navLink('generate.html', 'auto_awesome', 'Generate', 'primary')}
    </nav>
    <div class="nav-divider"></div>
    <div class="nav-actions">
        <!-- Destructive clear buttons — icon only -->
        <button id="btn-clear-loops"   class="btn nav-btn danger" title="Delete all Loops"><span class="material-icons">folder_delete</span></button>
        <button id="btn-clear-exports" class="btn nav-btn danger" title="Delete all Audio Exports"><span class="material-icons">delete_sweep</span></button>
        <button id="btn-clear-catalog" class="btn nav-btn danger" title="Delete Catalog"><span class="material-icons">delete_forever</span></button>
        <div class="nav-divider"></div>
        <!-- Always visible -->
        <button id="btn-instructions" class="btn nav-btn secondary" title="Help / AI Prompt">
            <span class="material-icons">help_outline</span><span class="nav-label">Help</span>
        </button>
        <button id="btn-insert-json" class="btn nav-btn secondary" title="Insert JSON">
            <span class="material-icons">data_object</span><span class="nav-label">Insert JSON</span>
        </button>
        <!-- Editor-only -->
        <button id="btn-export" class="btn nav-btn secondary nav-editor-only" title="Export Audio">
            <span class="material-icons">download</span><span class="nav-label">Export Audio</span>
        </button>
        <button id="btn-save" class="btn nav-btn primary nav-editor-only" title="Save Loop">
            <span class="material-icons">save</span><span class="nav-label">Save</span>
        </button>
    </div>
</header>`;


    // ── Help / Instructions Modal ────────────────────────────────────────────
    const instructionsModalHTML = `
<div id="instructions-modal" class="modal hidden">
    <div class="modal-content wide">
        <div class="modal-header">
            <h2>Instructions &amp; AI Prompt</h2>
            <button id="btn-close-modal" class="modal-close-btn"><span class="material-icons">close</span></button>
        </div>
        <div class="modal-body">
            <div class="ai-prompt-container" style="margin:20px 0;">
                <div style="display:flex;justify-content:space-between;margin-bottom:.5rem;align-items:flex-end;">
                    <div id="instructions-tabs" class="tabs-container" style="display:flex;gap:8px;flex-wrap:wrap;">
                        <button class="btn secondary active" data-tab="default">Default Prompt</button>
                    </div>
                    <button id="btn-copy-prompt" class="btn secondary" style="transform:scale(.8);transform-origin:right center;white-space:nowrap;">
                        <span class="material-icons">content_copy</span> Copy Prompt
                    </button>
                </div>
                <textarea id="ai-prompt-text" class="input-text prompt-textarea" readonly>
You are an expert music producer, beatmaker, and sound designer. I am building a custom web-based step sequencer using Tone.js and I need you to generate loops for me.

IMPORTANT: Before doing anything else, please recall and review the official Tone.js documentation, especially regarding Timing/Time notation (such as "16n", "8n", "8t", "4n", "2m", etc.) and note formats.

Once you have that context, generate a JSON file containing a musical loop. You MUST strictly follow these technical constraints:

1. Format: The output MUST be a JSON ARRAY containing one or more loop objects.
Example:
[
  {
    "name": "Cyberpunk FM Bassline",
    "bpm": 130,
    "instrument": "piano",
    "steps": 16,
    "key": "A",
    "scale": "Minor",
    "swing": 0.0,
    "notes": [
      {"step": 0, "note": "A4", "duration": "16n", "velocity": 1.0},
      {"step": 3, "note": "C5", "duration": "16n", "velocity": 0.6}
    ]
  }
]

2. The "notes" Array Rules:
- "step": Integer (0-indexed). For a 16-step loop, steps are 0–15.
- "duration": MUST use valid Tone.js notation ("16n", "8n", "4n", "32n", "8t").
- "velocity": Float 0.0–1.0. Use heavily for groove, accents, ghost notes!
- "chance" (optional): Float 0.0–1.0 — probability of the note playing.

3. "note" Pitch Rules (CRITICAL):
A. Melodic ("piano", "synth", "amSynth", "fmSynth"):
- Standard scientific pitch notation (e.g., "C4", "D#5", "Bb3").
- All notes MUST belong to the specified key and scale.
- Multiple notes on the same step = chords.

B. Drum Kit ("drums"):
- "note" MUST be exactly: "Kick", "Snare", "Clap", "HiHat", "OpenHat", "Tom H", "Tom L", "Crash"
- Do NOT use "Crash", "OpenHat", "HiHat", "Clap", or "Snare" without permission.

4. Musical Guidelines:
- "piano": Real acoustic piano.
- "synth": PolySynth (chords/pads).
- "amSynth": AM Synth (bells/electric pianos).
- "fmSynth": FM Synth (aggressive/metallic basses/leads).
- Add polyrhythms, syncopation, realistic velocities.

5. Duration Requirement:
- Minimum 8 seconds real time. Calculate steps/BPM accordingly.

6. Mixed Loops Naming:
- Pattern: ---Loop_{loop_name}

Output JSON within markdown code tags. Suggestions/explanations outside the block are welcome.
                </textarea>
            </div>
        </div>
    </div>
</div>`;

    // ── Insert JSON Modal ────────────────────────────────────────────────────
    const insertModalHTML = `
<div id="insert-modal" class="modal hidden">
    <div class="modal-content wide">
        <div class="modal-header">
            <h2>Insert JSON Loops</h2>
            <button id="btn-close-insert" class="modal-close-btn"><span class="material-icons">close</span></button>
        </div>
        <div class="modal-body">
            <p>Paste a JSON <strong>Array</strong> of loop objects to import them into your catalog.</p>
            <textarea id="json-paste-area" class="input-text large-textarea" placeholder='[
  {
    &quot;name&quot;: &quot;Loop 1&quot;,
    ...
  }
]'></textarea>
            <div style="display:flex;justify-content:flex-end;">
                <button id="btn-import-pasted" class="btn primary">
                    <span class="material-icons">playlist_add</span> Import Array
                </button>
            </div>
        </div>
    </div>
</div>`;

    // ── Inject into DOM ──────────────────────────────────────────────────────
    // Navbar goes inside .app-container (flex column), before main content
    const appContainer = document.querySelector('.app-container');
    if (appContainer) {
        appContainer.insertAdjacentHTML('afterbegin', navbarHTML);
    } else {
        document.body.insertAdjacentHTML('afterbegin', navbarHTML);
    }

    // Inject modals only if not already present (page may have its own copy)
    if (!document.getElementById('instructions-modal')) {
        document.body.insertAdjacentHTML('beforeend', instructionsModalHTML);
    }
    if (!document.getElementById('insert-modal')) {
        document.body.insertAdjacentHTML('beforeend', insertModalHTML);
    }

    // Hide editor-only buttons on non-editor pages
    if (!IS_EDITOR) {
        document.querySelectorAll('.nav-editor-only').forEach(el => el.style.display = 'none');
    }

    // ── Wire up Help modal ───────────────────────────────────────────────────
    function wireHelp() {
        const btnOpen = document.getElementById('btn-instructions');
        const modal = document.getElementById('instructions-modal');
        const btnClose = document.getElementById('btn-close-modal');
        const btnCopy = document.getElementById('btn-copy-prompt');
        const promptEl = document.getElementById('ai-prompt-text');

        if (!btnOpen || !modal) return;

        btnOpen.addEventListener('click', async () => {
            // Load style-specific instructions from API if available
            try {
                const res = await fetch('/api/instructions');
                if (res.ok) {
                    const instructions = await res.json();
                    const tabs = document.getElementById('instructions-tabs');
                    if (tabs && instructions.length > 0) {
                        instructions.forEach(inst => {
                            if (!tabs.querySelector(`[data-tab="${inst.name}"]`)) {
                                const btn = document.createElement('button');
                                btn.className = 'btn secondary';
                                btn.dataset.tab = inst.name;
                                btn.textContent = inst.name;
                                btn.addEventListener('click', () => {
                                    tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                                    btn.classList.add('active');
                                    if (promptEl) promptEl.value = inst.content;
                                });
                                tabs.appendChild(btn);
                            }
                        });
                    }
                }
            } catch (_) { }
            modal.classList.remove('hidden');
        });

        if (btnClose) btnClose.addEventListener('click', () => modal.classList.add('hidden'));
        modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });

        if (btnCopy && promptEl) {
            btnCopy.addEventListener('click', () => {
                navigator.clipboard.writeText(promptEl.value).then(() => {
                    btnCopy.textContent = 'Copied!';
                    setTimeout(() => {
                        btnCopy.innerHTML = '<span class="material-icons">content_copy</span> Copy Prompt';
                    }, 1500);
                });
            });
        }
    }

    // ── Wire up Insert JSON modal ────────────────────────────────────────────
    function wireInsert() {
        const btnOpen = document.getElementById('btn-insert-json');
        const modal = document.getElementById('insert-modal');
        const btnClose = document.getElementById('btn-close-insert');

        if (!btnOpen || !modal) return;

        // Only open the modal — actual import logic lives in page JS
        // (catalog.js / golden.js / app.js each handle #btn-import-pasted themselves)
        btnOpen.addEventListener('click', () => modal.classList.remove('hidden'));
        if (btnClose) btnClose.addEventListener('click', () => modal.classList.add('hidden'));
        modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });
    }

    // ── Wire up clear-all buttons ────────────────────────────────────────────
    function navToast(msg) {
        const t = document.getElementById('toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.remove('hidden');
        setTimeout(() => t.classList.add('hidden'), 3000);
    }

    function wireClearButtons() {
        const actions = [
            { id: 'btn-clear-loops', url: '/api/clear/loops', label: 'files in Downloads\\Loops folder' },
            { id: 'btn-clear-exports', url: '/api/clear/exports', label: 'audio exports' },
            { id: 'btn-clear-catalog', url: '/api/clear/catalog', label: 'entire catalog (loops + golden)' },
        ];
        actions.forEach(({ id, url, label }) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.addEventListener('click', async () => {
                if (!confirm(`Delete ALL ${label}? This cannot be undone.`)) return;
                try {
                    const res = await fetch(url, { method: 'DELETE' });
                    const data = await res.json();
                    navToast(`✓ Deleted ${data.deleted} file(s) from ${label}`);
                    setTimeout(() => location.reload(), 1000);
                } catch (e) {
                    navToast(`Error clearing ${label}`);
                }
            });
        });
    }

    // Wire modals after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => { wireHelp(); wireInsert(); wireClearButtons(); });
    } else {
        wireHelp();
        wireInsert();
        wireClearButtons();
    }
})();
