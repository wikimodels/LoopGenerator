// prompts.js — Prompts page table + modals
(function () {
    let prompts = [];
    let artists = [];
    let selected = new Set();
    let detailsPrompt = null;
    let createArtists = [];

    function showToast(msg, type='success') {
        const t = document.getElementById('toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.remove('hidden', 'toast-success', 'toast-error');
        t.classList.add(type === 'error' ? 'toast-error' : 'toast-success');
        setTimeout(() => t.classList.add('hidden'), 3000);
    }
    function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

    async function loadArtists() {
        try { const r = await fetch('/api/artists'); const d = await r.json(); artists = Object.keys(d).sort((a,b)=>a.localeCompare(b)); } catch(e){ artists=[]; }
    }
    async function loadPrompts() {
        const r = await fetch('/api/prompts'); prompts = await r.json();
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
        prompts.filter(p=> !q || p.name.toLowerCase().includes(q)).forEach(p=>{
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
            detailsPrompt.prompt = raw ? JSON.parse(raw) : [];
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
        document.getElementById('prompt-create-modal').classList.remove('hidden');
    }
    function closeCreate(){ document.getElementById('prompt-create-modal').classList.add('hidden'); }
    async function createPrompt(){
        const name = document.getElementById('create-prompt-name').value.trim();
        if(!name){ showToast('Name required', 'error'); return; }
        let prompt; try{ const raw = document.getElementById('create-prompt-json').value.trim(); prompt = raw ? JSON.parse(raw) : []; }catch(e){ showToast('Invalid JSON', 'error'); return; }
        const rec = { id: crypto.randomUUID(), name, prompt, comment: document.getElementById('create-comment').value, artists: createArtists.slice() };
        try{
            const r = await fetch('/api/prompts', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(rec)});
            if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'create failed'); }
            showToast('Created'); closeCreate(); await loadPrompts(); renderPrompts();
        }catch(e){ showToast(e.message, 'error'); }
    }

    async function bulkDelete(){
        if(!selected.size) return;
        if(!confirm(`Delete ${selected.size} prompt(s)?`)) return;
        for(const id of [...selected]){ try{ await fetch('/api/prompts/'+encodeURIComponent(id), {method:'DELETE'}); }catch(e){} }
        selected.clear(); await loadPrompts(); renderPrompts();
    }

    async function init(){
        await loadArtists();
        await loadPrompts();
        renderPrompts();
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
        document.getElementById('btn-create-add-artist')?.addEventListener('click', ()=>{
            const sel = document.getElementById('create-artist-select'); const v = sel.value; if(!v) return;
            if(!createArtists.includes(v)) createArtists.push(v);
            renderArtistsChips('create-artists-list', createArtists);
        });
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
