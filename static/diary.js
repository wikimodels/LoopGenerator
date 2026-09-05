// diary.js
(function(){
    let entries=[], artists=[], prompts=[], selected=new Set(), details=null, createArtists=[], createPrompts=[];
    function showToast(m){ const t=document.getElementById('toast'); if(!t) return; t.textContent=m; t.classList.remove('hidden'); setTimeout(()=>t.classList.add('hidden'),3000); }
    function esc(s){ return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    async function loadArtists(){ try{ const r=await fetch('/api/artists'); const d=await r.json(); artists=Object.keys(d).sort((a,b)=>a.localeCompare(b)); }catch(e){ artists=[]; } }
    async function loadPrompts(){ try{ const r=await fetch('/api/prompts'); const d=await r.json(); prompts=d; }catch(e){ prompts=[]; } }
    async function loadEntries(){ const r=await fetch('/api/diary'); entries=await r.json(); }
    function fillSelects(){
        const optsA = '<option value="">— select —</option>'+artists.map(a=>`<option value="${esc(a)}">${esc(a)}</option>`).join('');
        ['details-artist-select','create-artist-select'].forEach(id=>{ const el=document.getElementById(id); if(el) el.innerHTML=optsA; });
        const optsP = '<option value="">— select —</option>'+prompts.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
        ['details-prompt-select','create-prompt-select'].forEach(id=>{ const el=document.getElementById(id); if(el) el.innerHTML=optsP; });
    }
    function renderChips(containerId, list, isDetails){
        const el=document.getElementById(containerId); if(!el) return;
        el.innerHTML = list.map(v=>{
            const label = isDetails!==undefined ? (prompts.find(p=>p.id===v)?.name || v) : v;
            return `<span class="st-chip st-chip-found" style="display:inline-flex;align-items:center;gap:4px;">${esc(label)}<span class="material-icons" data-rm="${esc(v)}" style="font-size:14px;cursor:pointer;">close</span></span>`;
        }).join('') || '<span style="color:var(--text-muted);font-size:0.8rem;">None</span>';
        el.querySelectorAll('[data-rm]').forEach(x=> x.addEventListener('click', ()=>{
            const v=x.dataset.rm;
            if(containerId==='details-artists-list') details.artists=details.artists.filter(a=>a!==v);
            else if(containerId==='details-prompts-list') details.prompts=details.prompts.filter(a=>a!==v);
            else if(containerId==='create-artists-list') createArtists=createArtists.filter(a=>a!==v);
            else if(containerId==='create-prompts-list') createPrompts=createPrompts.filter(a=>a!==v);
            renderChips(containerId, containerId.includes('details') ? (containerId.includes('artists')?details.artists:details.prompts) : (containerId.includes('artists')?createArtists:createPrompts), containerId.includes('details'));
        }));
    }
    function renderDiary(){
        const list=document.getElementById('diary-list'); if(!list) return;
        const q=(document.getElementById('search-input')?.value||'').toLowerCase();
        const fs=document.getElementById('filter-status')?.value||'';
        list.innerHTML='';
        entries.filter(e=>{
            if(fs && e.status!==fs) return false;
            if(!q) return true;
            return (e.title+' '+e.body+' '+(e.tags||[]).join(' ')).toLowerCase().includes(q);
        }).forEach(e=>{
            const div=document.createElement('div'); div.className='catalog-item artist-item';
            const preview=(e.body||'').slice(0,80).replace(/\n/g,' ');
            div.innerHTML = `<div class="item-info artist-info" style="flex:1;"><div class="artist-name">${esc(e.title)}</div><div class="artist-meta"><span>${esc(e.date)}</span><span>${esc(e.status)}</span><span>${(e.tags||[]).join(', ')}</span></div><div style="font-size:0.78rem;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(preview)}</div></div>
                <button class="btn icon-btn details-btn" title="Details"><span class="material-icons">info</span></button>
                <label class="custom-checkbox-wrapper"><input type="checkbox" value="${esc(e.id)}" ${selected.has(e.id)?'checked':''}><span class="checkmark"></span></label>`;
            div.querySelector('input[type="checkbox"]').addEventListener('change', ev=>{ if(ev.target.checked) selected.add(e.id); else selected.delete(e.id); updateSel(); });
            div.querySelector('.details-btn').addEventListener('click', ev=>{ ev.stopPropagation(); openDetails(e.id); });
            list.appendChild(div);
        });
        updateSel();
    }
    function updateSel(){
        const c=selected.size;
        const el=document.getElementById('selected-diary-count'); if(el) el.textContent=c;
        const btn=document.getElementById('btn-delete-selected-diary'); if(btn) btn.disabled=c===0;
        const chk=document.getElementById('check-all-diary'); const all=document.querySelectorAll('#diary-list input[type="checkbox"]');
        if(chk){ chk.checked=all.length>0&&c===all.length; chk.indeterminate=c>0&&c<all.length; }
    }
    function openDetails(id){
        details=JSON.parse(JSON.stringify(entries.find(e=>e.id===id)));
        details.artists=details.artists||[]; details.prompts=details.prompts||[];
        document.getElementById('details-date').value=details.date||'';
        document.getElementById('details-title').value=details.title||'';
        document.getElementById('details-body').value=details.body||'';
        document.getElementById('details-tags').value=(details.tags||[]).join(', ');
        document.getElementById('details-status').value=details.status||'open';
        fillSelects(); renderChips('details-artists-list', details.artists, true); renderChips('details-prompts-list', details.prompts, true);
        document.getElementById('diary-details-modal').classList.remove('hidden');
    }
    function closeDetails(){ document.getElementById('diary-details-modal').classList.add('hidden'); details=null; }
    async function saveDetails(){
        if(!details) return;
        details.date=document.getElementById('details-date').value;
        details.title=document.getElementById('details-title').value.trim();
        if(!details.title){ showToast('Title required'); return; }
        details.body=document.getElementById('details-body').value;
        details.tags=document.getElementById('details-tags').value.split(',').map(s=>s.trim()).filter(Boolean);
        details.status=document.getElementById('details-status').value;
        try{ const r=await fetch('/api/diary/'+encodeURIComponent(details.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(details)}); if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'save failed'); } showToast('Saved'); closeDetails(); await loadEntries(); renderDiary(); }catch(e){ showToast(e.message); }
    }
    function openCreate(){
        const today=new Date().toISOString().slice(0,10);
        document.getElementById('create-date').value=today;
        document.getElementById('create-title').value='';
        document.getElementById('create-body').value='';
        document.getElementById('create-tags').value='';
        document.getElementById('create-status').value='open';
        createArtists=[]; createPrompts=[]; fillSelects(); renderChips('create-artists-list', createArtists); renderChips('create-prompts-list', createPrompts);
        document.getElementById('diary-create-modal').classList.remove('hidden');
    }
    function closeCreate(){ document.getElementById('diary-create-modal').classList.add('hidden'); }
    async function createEntry(){
        const title=document.getElementById('create-title').value.trim(); if(!title){ showToast('Title required'); return; }
        const rec={ id: crypto.randomUUID(), date: document.getElementById('create-date').value || new Date().toISOString().slice(0,10), title, body: document.getElementById('create-body').value, tags: document.getElementById('create-tags').value.split(',').map(s=>s.trim()).filter(Boolean), artists: createArtists.slice(), prompts: createPrompts.slice(), status: document.getElementById('create-status').value };
        try{ const r=await fetch('/api/diary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(rec)}); if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'create failed'); } showToast('Created'); closeCreate(); await loadEntries(); renderDiary(); }catch(e){ showToast(e.message); }
    }
    async function bulkDelete(){ if(!selected.size) return; if(!confirm(`Delete ${selected.size} entries?`)) return; for(const id of [...selected]){ try{ await fetch('/api/diary/'+encodeURIComponent(id),{method:'DELETE'});}catch(e){} } selected.clear(); await loadEntries(); renderDiary(); }
    async function init(){
        await loadArtists(); await loadPrompts(); await loadEntries(); renderDiary();
        const si=document.getElementById('search-input'), sc=document.getElementById('search-clear');
        if(si) si.addEventListener('input', ()=>{ renderDiary(); if(sc) sc.classList.toggle('hidden', !si.value); });
        if(sc) sc.addEventListener('click', ()=>{ si.value=''; si.dispatchEvent(new Event('input')); });
        const fs=document.getElementById('filter-status'); if(fs) fs.addEventListener('change', renderDiary);
        const ca=document.getElementById('check-all-diary'); if(ca) ca.addEventListener('change', e=>{ document.querySelectorAll('#diary-list input[type="checkbox"]').forEach(c=>{ c.checked=e.target.checked; const id=c.value; if(e.target.checked) selected.add(id); else selected.delete(id); }); updateSel(); });
        document.getElementById('btn-create-entry')?.addEventListener('click', openCreate);
        document.getElementById('btn-delete-selected-diary')?.addEventListener('click', bulkDelete);
        document.getElementById('btn-close-details-modal')?.addEventListener('click', closeDetails);
        document.getElementById('diary-details-modal')?.addEventListener('mousedown', e=>{ if(e.target===e.currentTarget) closeDetails(); });
        document.getElementById('btn-save-entry')?.addEventListener('click', saveDetails);
        document.getElementById('btn-copy-entry')?.addEventListener('click', ()=>{ if(!details) return; navigator.clipboard.writeText(details.body||'').then(()=>showToast('Copied')); });
        document.getElementById('btn-details-add-artist')?.addEventListener('click', ()=>{ const sel=document.getElementById('details-artist-select'); const v=sel.value; if(!v) return; details.artists=details.artists||[]; if(details.artists.includes(v)) return; details.artists.push(v); renderChips('details-artists-list', details.artists, true); });
        document.getElementById('btn-details-add-prompt')?.addEventListener('click', ()=>{ const sel=document.getElementById('details-prompt-select'); const v=sel.value; if(!v) return; details.prompts=details.prompts||[]; if(details.prompts.includes(v)) return; details.prompts.push(v); renderChips('details-prompts-list', details.prompts, true); });
        document.getElementById('btn-close-create-modal')?.addEventListener('click', closeCreate);
        document.getElementById('diary-create-modal')?.addEventListener('mousedown', e=>{ if(e.target===e.currentTarget) closeCreate(); });
        document.getElementById('btn-create-save')?.addEventListener('click', createEntry);
        document.getElementById('btn-create-add-artist')?.addEventListener('click', ()=>{ const sel=document.getElementById('create-artist-select'); const v=sel.value; if(!v||createArtists.includes(v)) return; createArtists.push(v); renderChips('create-artists-list', createArtists); });
        document.getElementById('btn-create-add-prompt')?.addEventListener('click', ()=>{ const sel=document.getElementById('create-prompt-select'); const v=sel.value; if(!v||createPrompts.includes(v)) return; createPrompts.push(v); renderChips('create-prompts-list', createPrompts); });
    }
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
