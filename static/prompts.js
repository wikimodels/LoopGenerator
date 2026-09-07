// prompts.js — Prompts page table + modals (v6)
(function () {
    console.log('[prompts.js v6] script loaded');
    let prompts = [];
    let artists = [];
    let selected = new Set();
    let detailsPrompt = null;
    let createArtists = [];
    let createBusy = false;

    // Surface silent JS errors as toasts — "no errors" must be impossible to miss
    window.addEventListener('error', (e) => {
        try {
            const msg = (e && e.message) || (e && e.error && e.error.message) || 'unknown JS error';
            console.error('[prompts.js v6] window.onerror:', e);
            const t = document.getElementById('toast');
            if (t) { t.textContent = 'JS error: ' + msg; t.classList.remove('hidden'); }
        } catch (_) {}
    });

    // Delegated fallback: if direct button wiring ever missed, clicks still work.
    // Busy-guard in createPrompt + idempotent openCreate make double-firing safe.
    document.addEventListener('click', (e) => {
        if (!e.target || !e.target.closest) return;
        if (e.target.closest('#btn-create-save')) {
            if (e.__promptsHandled) return;
            e.__promptsHandled = true;
            console.log('[prompts.js v6] delegated #btn-create-save click');
            createPrompt();
        } else if (e.target.closest('#btn-create-prompt')) {
            if (e.__promptsHandled) return;
            e.__promptsHandled = true;
            console.log('[prompts.js v6] delegated #btn-create-prompt click');
            openCreate();
        } else if (e.target.closest('#btn-format-create-json')) {
            if (e.__promptsHandled) return;
            e.__promptsHandled = true;
            formatCreateJson();
        }
    });
    function showToast(msg, type='success') {
        const t = document.getElementById('toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.remove('hidden', 'toast-success', 'toast-error');
        t.classList.add(type === 'error' ? 'toast-error' : 'toast-success');
        clearTimeout(t.__timer);
        // Errors stay visible longer so they can't be missed
        t.__timer = setTimeout(() => t.classList.add('hidden'), type === 'error' ? 8000 : 3000);
    }
    function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function stripFences(s) {
        // Tolerate ```json ... ``` pasted from AI chats
        if (/^\s*```/.test(s)) s = s.replace(/^\s*```[a-zA-Z]*\s*/, '').replace(/\s*```\s*$/, '');
        return s.trim();
    }
    function repairJson(s) {
        // Auto-format pasted docs: escape raw newlines/tabs inside "..." strings
        // and drop trailing commas — strict JSON.parse rejects both, humans paste both.
        let out = '';
        let inStr = false;
        let escd = false;
        for (let i = 0; i < s.length; i++) {
            const c = s[i];
            if (inStr) {
                if (escd) { out += c; escd = false; }
                else if (c === '\\') { out += c; escd = true; }
                else if (c === '"') { out += c; inStr = false; }
                else if (c === '\n') { out += '\\n'; }
                else if (c === '\r') { if (s[i + 1] !== '\n') out += '\\n'; }
                else if (c === '\t') { out += '\\t'; }
                else if (c < ' ') { out += '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'); }
                else { out += c; }
            } else {
                out += c;
                if (c === '"') inStr = true;
            }
        }
        return out.replace(/,\s*([}\]])/g, '$1');
    }
    function parsePromptJson(raw) {
        // Strict first (exact errors), repaired fallback (multiline lyrics etc.)
        const text = stripFences((raw || '').trim());
        if (!text) return [];
        try { return JSON.parse(text); }
        catch (e1) {
            try { return JSON.parse(repairJson(text)); }
            catch (e2) { throw e1; }
        }
    }
    function updateCreateJsonHint() {
        const ta = document.getElementById('create-prompt-json');
        const hint = document.getElementById('create-json-hint');
        if (!ta || !hint) return;
        const raw = stripFences(ta.value.trim());
        if (!raw) { hint.textContent = 'Empty — will be saved as []'; hint.style.color = 'var(--text-muted)'; return; }
        try {
            const v = JSON.parse(raw);
            const n = Array.isArray(v) ? v.length : 1;
            hint.textContent = '✓ Valid JSON — ' + n + ' item' + (n === 1 ? '' : 's');
            hint.style.color = '#4ade80';
        } catch (e) {
            try {
                const v = JSON.parse(repairJson(raw));
                const n = Array.isArray(v) ? v.length : 1;
                hint.textContent = '✓ Valid — line breaks will be auto-fixed on save (' + n + ' item' + (n === 1 ? '' : 's') + ')';
                hint.style.color = '#fbbf24';
            } catch (e2) {
                hint.textContent = '✗ Invalid JSON: ' + e.message;
                hint.style.color = '#f87171';
            }
        }
    }
    function formatCreateJson() {
        const ta = document.getElementById('create-prompt-json');
        if (!ta) return;
        try {
            const v = parsePromptJson(ta.value);
            ta.value = JSON.stringify(Array.isArray(v) ? v : [v], null, 2);
            updateCreateJsonHint();
            showToast('Formatted');
        } catch (e) { showToast('Cannot format: ' + e.message, 'error'); }
    }

    async function loadArtists() {
        try { const r = await fetch('/api/artists'); const d = await r.json(); artists = Object.keys(d).sort((a,b)=>a.localeCompare(b)); } catch(e){ artists=[]; }
    }
    async function loadPrompts() {
        const r = await fetch('/api/prompts');
        if(!r.ok) throw new Error('load prompts failed: HTTP ' + r.status);
        prompts = await r.json();
    }
    function fillArtistSelect(sel) {
        if (!sel) return;
        sel.innerHTML = '<option value="">— select artist —</option>' + artists.map(a=>`<option value="${esc(a)}">${esc(a)}</option>`).join('');
    }

    function renderArtistsChips(containerId, list) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = list.map(a=>`
            <span class="st-chip st-chip-found" style="display:inline-flex;align-items:center;gap:4px;">${esc(a)}
                <span class="material-icons" data-remove="${esc(a)}" style="font-size:14px;cursor:pointer;">close</span>
            </span>`).join('') || '<span style="color:var(--text-muted);font-size:0.8rem;">No artists</span>';
        el.querySelectorAll('[data-remove]').forEach(x=> x.addEventListener('click', () => {
            const name = x.dataset.remove;
            if (el.id === 'details-artists-list') {
                detailsPrompt.artists = (detailsPrompt.artists||[]).filter(v=>v!==name);
                renderArtistsChips('details-artists-list', detailsPrompt.artists);
            } else {
                createArtists = createArtists.filter(v=>v!==name);
                renderArtistsChips('create-artists-list', createArtists);
            }
        }));
    }

    function renderPrompts() {
        const list = document.getElementById('prompts-list');
        if (!list) return;
        const q = (document.getElementById('search-input')?.value || '').toLowerCase();
        list.innerHTML = '';
        prompts.filter(p=> !q || p.name.toLowerCase().includes(q)).sort((a,b)=> String(a.name||'').localeCompare(String(b.name||''), undefined, {sensitivity:'base'})).forEach(p=>{
            const div = document.createElement('div');
            div.className = 'catalog-item artist-item';
            div.innerHTML = `
                <div class="item-info artist-info" style="flex:1;">
                    <div class="artist-name" title="Click to edit">${esc(p.name)}</div>
                </div>
                <button class="btn icon-btn copy-btn" title="Copy prompt"><span class="material-icons">content_copy</span></button>
                <button class="btn icon-btn details-btn" title="Details"><span class="material-icons">info</span></button>
                <label class="custom-checkbox-wrapper">
                    <input type="checkbox" value="${esc(p.id)}" ${selected.has(p.id)?'checked':''}>
                    <span class="checkmark"></span>
                </label>
            `;
            div.querySelector('input[type="checkbox"]').addEventListener('change', e=>{
                if(e.target.checked) selected.add(p.id); else selected.delete(p.id);
                updateSelectionUI();
            });
            div.querySelector('.copy-btn').addEventListener('click', e=>{
                e.stopPropagation();
                navigator.clipboard.writeText(JSON.stringify(p.prompt, null, 2)).then(()=> showToast('Copied'));
            });
            div.querySelector('.details-btn').addEventListener('click', e=>{
                e.stopPropagation();
                openDetails(p.id);
            });
            // Inline rename — click name to edit, Enter to save
            const nameEl = div.querySelector('.artist-name');
            nameEl.addEventListener('click', () => {
                if (nameEl.isContentEditable) return;
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
                if (!newName || newName === p.name) { nameEl.textContent = p.name; return; }
                const oldName = p.name;
                p.name = newName;
                try {
                    const r = await fetch('/api/prompts/'+encodeURIComponent(p.id), {
                        method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(p)
                    });
                    if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'rename failed'); }
                    showToast('Renamed');
                    renderPrompts();
                } catch(e){
                    p.name = oldName;
                    nameEl.textContent = oldName;
                    showToast(e.message, 'error');
                }
            });
            nameEl.addEventListener('keydown', e=>{
                if(e.key==='Enter'){ e.preventDefault(); nameEl.blur(); }
                if(e.key==='Escape'){ nameEl.textContent = p.name; nameEl.blur(); }
            });
            list.appendChild(div);
        });
        updateSelectionUI();
    }
    function updateSelectionUI() {
        const c = selected.size;
        const el = document.getElementById('selected-prompt-count');
        if(el) el.textContent = c;
        const btn = document.getElementById('btn-delete-selected-prompts');
        if(btn) btn.disabled = c===0;
        const chk = document.getElementById('check-all-prompts');
        const all = document.querySelectorAll('#prompts-list input[type="checkbox"]');
        if(chk){ chk.checked = all.length>0 && c===all.length; chk.indeterminate = c>0 && c<all.length; }
    }

    // Details modal
    function openDetails(id) {
        detailsPrompt = JSON.parse(JSON.stringify(prompts.find(p=>p.id===id)));
        document.getElementById('details-prompt-json').value = JSON.stringify(detailsPrompt.prompt, null, 2);
        document.getElementById('details-comment').value = detailsPrompt.comment||'';
        fillArtistSelect(document.getElementById('details-artist-select'));
        renderArtistsChips('details-artists-list', detailsPrompt.artists||[]);
        document.getElementById('prompt-details-modal').classList.remove('hidden');
    }
    function closeDetails(){ document.getElementById('prompt-details-modal').classList.add('hidden'); detailsPrompt=null; }
    async function saveDetails(){
        if(!detailsPrompt) return;
        const btn = document.getElementById('btn-save-prompt');
        const orig = btn ? btn.innerHTML : '';
        if(btn){ btn.disabled = true; btn.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Saving...'; }
        try {
            const raw = document.getElementById('details-prompt-json').value.trim();
            detailsPrompt.prompt = raw ? parsePromptJson(raw) : [];
            detailsPrompt.comment = document.getElementById('details-comment').value;
            const r = await fetch('/api/prompts/'+encodeURIComponent(detailsPrompt.id), {
                method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(detailsPrompt)
            });
            if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'save failed'); }
            showToast('Saved');
            closeDetails();
            await loadPrompts(); renderPrompts();
        } catch(e){ showToast(e.message, 'error'); }
        finally { if(btn){ btn.disabled = false; btn.innerHTML = orig; } }
    }
    function copyDetails(){
        try{ const v = document.getElementById('details-prompt-json').value; navigator.clipboard.writeText(v).then(()=>showToast('Copied')); }catch(e){}
    }

    // Create modal
    function openCreate(){
        document.getElementById('create-prompt-name').value='';
        document.getElementById('create-prompt-json').value='';
        document.getElementById('create-comment').value='';
        createArtists=[]; fillArtistSelect(document.getElementById('create-artist-select')); renderArtistsChips('create-artists-list', createArtists);
        updateCreateJsonHint();
        document.getElementById('prompt-create-modal').classList.remove('hidden');
    }
    function closeCreate(){ document.getElementById('prompt-create-modal').classList.add('hidden'); }
    async function createPrompt(){
        console.log('[prompts.js v6] createPrompt invoked');
        if (createBusy) { console.log('[prompts.js v6] createPrompt already in-flight, ignoring'); return; }
        createBusy = true;
        try {
            const name = document.getElementById('create-prompt-name').value.trim();
            if(!name){ showToast('Name required', 'error'); return; }
            let prompt;
            try{
                prompt = parsePromptJson(document.getElementById('create-prompt-json').value);
                if (prompt && !Array.isArray(prompt)) prompt = [prompt];
            }
            catch(e){ showToast('Invalid JSON: ' + e.message, 'error'); return; }
            const uid = (window.crypto && typeof crypto.randomUUID === 'function')
                ? crypto.randomUUID()
                : 'id-' + Date.now().toString(36) + '-' + Math.random().toString(16).slice(2);
            const rec = { id: uid, name, prompt, comment: document.getElementById('create-comment').value, artists: createArtists.slice() };
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 20000);
            let r;
            try { r = await fetch('/api/prompts', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(rec), signal: ctrl.signal}); }
            finally { clearTimeout(timer); }
            if(!r.ok){ let msg='create failed'; try{ const j=await r.json(); msg=j.detail||msg; }catch(e){} throw new Error(msg); }
            showToast('Created'); closeCreate(); await loadPrompts(); renderPrompts();
        }catch(e){
            const msg = (e && e.name === 'AbortError')
                ? 'Request timed out after 20s (server did not respond)'
                : (e.message||'create failed');
            console.error('[prompts.js v6] createPrompt failed:', e);
            showToast(msg, 'error');
        }
        finally { createBusy = false; }
    }

    async function bulkDelete(){
        if(!selected.size) return;
        if(!confirm(`Delete ${selected.size} prompt(s)?`)) return;
        for(const id of [...selected]){ try{ await fetch('/api/prompts/'+encodeURIComponent(id), {method:'DELETE'}); }catch(e){} }
        selected.clear(); await loadPrompts(); renderPrompts();
    }

    async function init(){
        console.log('[prompts.js v6] init, buttons present:',
            'btn-create-prompt=' + !!document.getElementById('btn-create-prompt'),
            'btn-create-save=' + !!document.getElementById('btn-create-save'),
            'prompt-create-modal=' + !!document.getElementById('prompt-create-modal'));
        // Wire UI first — so buttons work even if data load fails
        // search
        const si = document.getElementById('search-input');
        const sc = document.getElementById('search-clear');
        if(si){ si.addEventListener('input', ()=>{ renderPrompts(); if(sc) sc.classList.toggle('hidden', !si.value); }); }
        if(sc){ sc.addEventListener('click', ()=>{ si.value=''; si.dispatchEvent(new Event('input')); }); }
        // check all
        const ca = document.getElementById('check-all-prompts');
        if(ca){ ca.addEventListener('change', e=>{ document.querySelectorAll('#prompts-list input[type="checkbox"]').forEach(c=>{ c.checked=e.target.checked; const id=c.value; if(e.target.checked) selected.add(id); else selected.delete(id); }); updateSelectionUI(); }); }
        // header buttons
        document.getElementById('btn-create-prompt')?.addEventListener('click', openCreate);
        document.getElementById('btn-delete-selected-prompts')?.addEventListener('click', bulkDelete);
        // details modal
        document.getElementById('btn-close-details-modal')?.addEventListener('click', closeDetails);
        document.getElementById('prompt-details-modal')?.addEventListener('mousedown', e=>{ if(e.target===e.currentTarget) closeDetails(); });
        document.getElementById('btn-save-prompt')?.addEventListener('click', saveDetails);
        document.getElementById('btn-copy-prompt')?.addEventListener('click', copyDetails);
        document.getElementById('btn-add-artist-to-prompt')?.addEventListener('click', ()=>{
            const sel = document.getElementById('details-artist-select'); const v = sel.value; if(!v) return;
            detailsPrompt.artists = detailsPrompt.artists||[]; if(!detailsPrompt.artists.includes(v)) detailsPrompt.artists.push(v);
            renderArtistsChips('details-artists-list', detailsPrompt.artists);
        });
        // create modal
        document.getElementById('btn-close-create-modal')?.addEventListener('click', closeCreate);
        document.getElementById('prompt-create-modal')?.addEventListener('mousedown', e=>{ if(e.target===e.currentTarget) closeCreate(); });
        document.getElementById('btn-create-save')?.addEventListener('click', createPrompt);
        document.getElementById('btn-format-create-json')?.addEventListener('click', formatCreateJson);
        document.getElementById('create-prompt-json')?.addEventListener('input', updateCreateJsonHint);
        document.getElementById('btn-create-add-artist')?.addEventListener('click', ()=>{
            const sel = document.getElementById('create-artist-select'); const v = sel.value; if(!v) return;
            if(!createArtists.includes(v)) createArtists.push(v);
            renderArtistsChips('create-artists-list', createArtists);
        });
        // Then load data
        try { await loadArtists(); }
        catch(e){ console.error('loadArtists failed', e); artists=[]; }
        try { await loadPrompts(); }
        catch(e){ console.error('loadPrompts failed', e); showToast(e.message, 'error'); prompts=[]; }
        renderPrompts();
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
