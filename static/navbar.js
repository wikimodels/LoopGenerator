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
        ${navLink('archive.html', 'inventory_2', 'Archive', 'neutral')}
        ${navLink('artists.html', 'group', 'Artists', 'secondary')}
        ${navLink('prompts.html', 'chat_bubble', 'Prompts', 'secondary')}
        ${navLink('diary.html', 'book', 'Diary', 'secondary')}
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
                        <button class="btn secondary" data-tab="correction">Correction Prompt</button>
                    </div>
                        <button id="btn-copy-ai-prompt" class="btn secondary" style="transform:scale(.8);transform-origin:right center;white-space:nowrap;">
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
        const btnCopy = document.getElementById('btn-copy-ai-prompt');
        const promptEl = document.getElementById('ai-prompt-text');

        if (!btnOpen || !modal) return;

        const tabs = document.getElementById('instructions-tabs');
        const promptText = document.getElementById('ai-prompt-text');
        const DEFAULT_PROMPT = promptEl ? promptEl.value : '';
        const CORRECTION_PROMPT = `Мастер-промт: Аудио-инженерная и гармоническая коррекция JSON-паттерна

Проведи полную аудио-инженерную и гармоническую коррекцию этого JSON-паттерна.


Overlap Cleanup: устрани дубли одной и той же ноты на одном шаге с разной длительностью (оставляй более длинную).
Register Range: мелодия строго в диапазоне A4–D5, не короче 8n на нотах выше A4. Ноты октавы 6+ — недопустимы.
Voice Leading & Harmony: используй только диатонические аккорды тональности (с допущением гармонического минора). Любой аккорд вне этого списка — замени на ближайший диатонический той же функции. Разнеси голоса минимум на малую терцию, чтобы избежать наложения тембров.
Velocity Curve: бас 0.65–0.70, аккомпанемент 0.26–0.30, мелодия 0.48–0.52, самые высокие ноты — нижняя граница диапазона.
Anti-Buzz Gap: если два соседних по времени звука аккомпанемента имеют одинаковую высоту (retrigger), сократи длительность первого на один уровень (4n→8n, 8n→16n), оставляя паузу перед повтором. Не применяй это правило, если следующая нота имеет другую высоту.
Фиксация паттерна: удали все вероятностные параметры ("chance") — 100% детерминированное исполнение.
К названию трека добавь суффикс _Fixed (если его ещё нет).


Верни только готовый исправленный JSON.`;

        function activateTab(btn, text) {
            tabs.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (promptEl) promptEl.value = text;
        }

        // Static tabs: Default / Correction
        const defaultBtn = tabs.querySelector('[data-tab="default"]');
        const correctionBtn = tabs.querySelector('[data-tab="correction"]');
        if (defaultBtn) defaultBtn.addEventListener('click', () => activateTab(defaultBtn, DEFAULT_PROMPT));
        if (correctionBtn) correctionBtn.addEventListener('click', () => activateTab(correctionBtn, CORRECTION_PROMPT));

        btnOpen.addEventListener('click', async () => {
            // Load style-specific instructions from API if available
            try {
                const res = await fetch('/api/instructions');
                if (res.ok) {
                    const instructions = await res.json();
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
        const btnImport = document.getElementById('btn-import-pasted');

        if (!btnOpen || !modal) return;

        btnOpen.addEventListener('click', () => modal.classList.remove('hidden'));
        if (btnClose) btnClose.addEventListener('click', () => modal.classList.add('hidden'));
        modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });

        // Fallback handler for pages without page-specific import logic (e.g., prompts.html, diary.html, artists.html, archive.html, exports.html)
        // Catalog/golden/index have their own handlers — skip there to avoid double import
        const path = location.pathname.split('/').pop() || 'index.html';
        const needsFallback = ['prompts.html', 'diary.html', 'artists.html', 'archive.html', 'exports.html', 'generate.html'].includes(path);
        if (needsFallback && btnImport) {
            btnImport.addEventListener('click', async () => {
                const ta = document.getElementById('json-paste-area');
                const text = ta ? ta.value.trim() : '';
                if (!text) return;
                let data;
                try { data = JSON.parse(text); } catch (e) { alert('Invalid JSON: ' + e.message); return; }
                const problems = window.validateLoopsImport ? await window.validateLoopsImport(data) : [];
                if (problems.length) {
                    alert('Insert JSON: документ не прошёл валидацию:\n\n' + problems.join('\n') + '\n\nИмпорт отменён — исправьте документ и повторите.');
                    return;
                }
                const orig = btnImport.innerHTML;
                btnImport.disabled = true;
                btnImport.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Importing...';
                let successCount = 0;
                const failed = [];
                for (const loop of data) {
                    try {
                        const res = await fetch('/api/loops', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(loop) });
                        if (res.ok) successCount++; else {
                            let detail = `HTTP ${res.status}`;
                            try { const j = await res.json(); if (j.detail) detail = j.detail; } catch (_) {}
                            failed.push(`${loop.name || 'unnamed'}: ${detail}`);
                        }
                    } catch (e) { failed.push(`${loop.name || 'unnamed'}: ${e.message}`); }
                }
                btnImport.disabled = false;
                btnImport.innerHTML = orig;
                if (failed.length) alert('Some tracks were NOT imported (' + failed.length + '):\n\n' + failed.join('\n'));
                if (successCount) {
                    const toast = document.getElementById('toast');
                    if (toast) { toast.textContent = `Imported ${successCount} loops!`; toast.classList.remove('hidden'); setTimeout(()=>toast.classList.add('hidden'), 3000); }
                }
                if (!failed.length) { modal.classList.add('hidden'); if (ta) ta.value = ''; }
            });
        }
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

    // ── Insert JSON: общая валидация документа (используется страницами) ────
    // Возвращает массив строк-проблем; пустой массив = документ валиден.
    window.validateLoopsImport = async function (data) {
        const problems = [];
        if (!Array.isArray(data)) {
            problems.push('Формат: документ должен быть JSON-массивом [...], получено: ' +
                (data === null ? 'null' : Array.isArray(data) ? 'array' : typeof data));
            return problems;
        }
        if (data.length === 0) {
            problems.push('Формат: массив пуст — нечего импортировать.');
            return problems;
        }

        // Имена уже существующих треков (оба каталога)
        const existing = new Set();
        try {
            const [a, b] = await Promise.all([fetch('/api/loops'), fetch('/api/golden')]);
            if (a.ok) (await a.json()).forEach(l => { if (l && l.name) existing.add(l.name); });
            if (b.ok) (await b.json()).forEach(l => { if (l && l.name) existing.add(l.name); });
        } catch (_) {}

        const seen = new Set();
        data.forEach((item, i) => {
            const label = (item && typeof item === 'object' && item.name) ? `"${item.name}"` : `элемент #${i + 1}`;
            if (!item || typeof item !== 'object' || Array.isArray(item)) {
                problems.push(`${label}: не является объектом`);
                return;
            }
            if (typeof item.name !== 'string' || !item.name.trim())
                problems.push(`${label}: поле "name" отсутствует или пустое`);
            if (typeof item.bpm !== 'number' || !Number.isFinite(item.bpm) || item.bpm <= 0)
                problems.push(`${label}: поле "bpm" должно быть положительным числом`);
            if (!Number.isInteger(item.steps) || item.steps <= 0)
                problems.push(`${label}: поле "steps" должно быть целым числом > 0`);
            if (item.instrument !== undefined && typeof item.instrument !== 'string')
                problems.push(`${label}: поле "instrument" должно быть строкой`);
            if (!Array.isArray(item.notes)) {
                problems.push(`${label}: поле "notes" отсутствует или не является массивом`);
            } else {
                const badNote = item.notes.findIndex(n =>
                    !n || typeof n !== 'object' ||
                    !Number.isInteger(n.step) || n.step < 0 ||
                    typeof n.note !== 'string' || !n.note.trim() ||
                    typeof n.duration !== 'string' || !n.duration.trim());
                if (badNote >= 0)
                    problems.push(`${label}: невалидная нота в "notes" (индекс ${badNote}) — нужны step:int>=0, note:"C4", duration:"8n"`);
            }
            if (item.name && typeof item.name === 'string') {
                if (seen.has(item.name))
                    problems.push(`Дубль внутри документа: "${item.name}" встречается больше одного раза`);
                seen.add(item.name);
                if (existing.has(item.name))
                    problems.push(`Дубль с существующими треками: "${item.name}" уже есть в каталоге/golden`);
            }
        });
        return problems;
    };

    // Wire modals after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => { wireHelp(); wireInsert(); wireClearButtons(); });
    } else {
        wireHelp();
        wireInsert();
        wireClearButtons();
    }
})();
