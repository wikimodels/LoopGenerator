// artists.js — Artists management page
(function () {
    // ── State ────────────────────────────────────────────────────────────────
    let artistsData = {};          // { artist: [trackNames] } — единый источник правды
    let selectedArtists = new Set();
    let currentArtist = null;      // артист, чья модалка открыта

    // ── Utils ────────────────────────────────────────────────────────────────
    function showToast(msg) {
        const t = document.getElementById('toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.remove('hidden');
        setTimeout(() => t.classList.add('hidden'), 3000);
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }

    async function apiPost(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            let detail = `HTTP ${res.status}`;
            try { const j = await res.json(); if (j.detail) detail = j.detail; } catch (_) {}
            throw new Error(detail);
        }
        return res.json();
    }

    async function apiDelete(url) {
        const res = await fetch(url, { method: 'DELETE' });
        if (!res.ok) {
            let detail = `HTTP ${res.status}`;
            try { const j = await res.json(); if (j.detail) detail = j.detail; } catch (_) {}
            throw new Error(detail);
        }
        return res.json();
    }

    // ── Data ─────────────────────────────────────────────────────────────────
    async function loadArtists() {
        try {
            const res = await fetch('/api/artists');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            artistsData = await res.json();
        } catch (e) {
            console.error('Failed to load artists', e);
            artistsData = {};
        }
    }

    // ── Rendering ────────────────────────────────────────────────────────────
    function renderArtists() {
        const list = document.getElementById('artists-list');
        if (!list) return;
        list.innerHTML = '';

        Object.keys(artistsData).sort((a, b) => a.localeCompare(b)).forEach(artist => {
            const trackCount = (artistsData[artist] || []).length;

            const div = document.createElement('div');
            div.className = 'catalog-item artist-item';
            div.dataset.artist = artist;

            div.innerHTML = `
                <label class="custom-checkbox-wrapper">
                    <input type="checkbox" value="${escapeHtml(artist)}" ${selectedArtists.has(artist) ? 'checked' : ''}>
                    <span class="checkmark"></span>
                </label>
                <div class="item-info artist-info">
                    <div class="artist-name" title="Click to edit">${escapeHtml(artist)}</div>
                    <div class="artist-meta">
                        <span>${trackCount} track${trackCount !== 1 ? 's' : ''}</span>
                        <button class="btn icon-btn tracks-btn" title="Manage tracks">
                            <span class="material-icons">queue_music</span>
                        </button>
                    </div>
                </div>
            `;

            // Checkbox (нативный label — без доп. обработчиков клика)
            div.querySelector('input[type="checkbox"]').addEventListener('change', (e) => {
                if (e.target.checked) selectedArtists.add(artist);
                else selectedArtists.delete(artist);
                updateSelectionUI();
            });

            // Имя — клик для переименования (как треки в каталоге)
            const nameEl = div.querySelector('.artist-name');
            nameEl.addEventListener('click', () => startArtistRename(artist, nameEl));

            // Кнопка Треки
            div.querySelector('.tracks-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                openArtistTracksModal(artist);
            });

            list.appendChild(div);
        });

        updateSelectionUI();
    }

    function updateSelectionUI() {
        const count = selectedArtists.size;
        document.getElementById('selected-artist-count').textContent = count;
        document.getElementById('btn-delete-selected-artists').disabled = count === 0;
        const all = document.querySelectorAll('.artist-item input[type="checkbox"]');
        const chkAll = document.getElementById('check-all-artists');
        chkAll.checked = all.length > 0 && count === all.length;
        chkAll.indeterminate = count > 0 && count < all.length;
    }

    // ── Rename (inline, как имена треков) ────────────────────────────────────
    function startArtistRename(artist, nameEl) {
        if (nameEl.isContentEditable) return;
        nameEl.contentEditable = 'true';
        nameEl.focus();
        const range = document.createRange();
        range.selectNodeContents(nameEl);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);

        nameEl.addEventListener('blur', () => finishArtistRename(artist, nameEl), { once: true });
        nameEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); nameEl.blur(); }
        });
    }

    async function finishArtistRename(artist, nameEl) {
        nameEl.contentEditable = 'false';
        const newName = nameEl.textContent.trim();
        if (!newName || newName === artist) { nameEl.textContent = artist; return; }

        if (artistsData.hasOwnProperty(newName)) {
            alert(`Artist "${newName}" already exists`);
            nameEl.textContent = artist;
            return;
        }

        try {
            await apiPost('/api/artists/rename', { old_name: artist, new_name: newName });
            artistsData[newName] = artistsData[artist] || [];
            delete artistsData[artist];
            if (selectedArtists.has(artist)) {
                selectedArtists.delete(artist);
                selectedArtists.add(newName);
            }
            showToast(`Renamed to "${newName}"`);
            renderArtists();
        } catch (e) {
            showToast('Rename failed: ' + e.message);
            nameEl.textContent = artist;
        }
    }

    // ── Tracks Modal (простое текстовое поле, треки построчно) ───────────────
    function openArtistTracksModal(artist) {
        currentArtist = artist;
        document.getElementById('modal-artist-name').textContent = artist;
        const tracks = (artistsData[artist] || []).slice().sort((a, b) => a.localeCompare(b));
        document.getElementById('artist-tracks-textarea').value = tracks.join('\n');
        document.getElementById('artist-tracks-modal').classList.remove('hidden');
    }

    function closeArtistTracksModal() {
        document.getElementById('artist-tracks-modal').classList.add('hidden');
        currentArtist = null;
    }

    async function saveArtistTracks() {
        if (!currentArtist) return;
        const ta = document.getElementById('artist-tracks-textarea');
        // Парсим строки: трим, пустые — вон, дубликаты — вон
        const seen = new Set();
        const tracks = ta.value.split('\n')
            .map(l => l.trim())
            .filter(l => l && !seen.has(l) && seen.add(l));
        try {
            await apiPost('/api/artists/tracks', { artist: currentArtist, tracks });
            artistsData[currentArtist] = tracks;
            showToast(`Saved ${tracks.length} track(s) for "${currentArtist}"`);
            closeArtistTracksModal();
            renderArtists();
        } catch (e) {
            showToast('Save failed: ' + e.message);
        }
    }

    function copyArtistTracks() {
        const ta = document.getElementById('artist-tracks-textarea');
        const text = ta.value.trim();
        if (!text) { showToast('Nothing to copy'); return; }
        navigator.clipboard.writeText(text).then(() => showToast('Copied')).catch(() => showToast('Copy failed'));
    }

    // ── Add / Delete artists ─────────────────────────────────────────────────
    async function addArtist() {
        const name = (prompt('New artist name:') || '').trim();
        if (!name) return;
        if (artistsData.hasOwnProperty(name)) { showToast('Artist already exists'); return; }
        try {
            await apiPost('/api/artists', { name });
            artistsData[name] = [];
            showToast('Artist added: ' + name);
            renderArtists();
        } catch (e) {
            showToast('Add failed: ' + e.message);
        }
    }

    async function bulkDeleteArtists() {
        if (!selectedArtists.size) return;
        if (!confirm(`Delete ${selectedArtists.size} artist(s)? Their track lists will be removed.`)) return;
        let deleted = 0;
        for (const artist of [...selectedArtists]) {
            try {
                await apiDelete('/api/artists/' + encodeURIComponent(artist));
                delete artistsData[artist];
                deleted++;
            } catch (e) {
                console.error('Delete failed for', artist, e);
            }
        }
        selectedArtists.clear();
        showToast(`Deleted ${deleted} artist(s)`);
        renderArtists();
    }

    // ── Init ─────────────────────────────────────────────────────────────────
    async function init() {
        await loadArtists();
        renderArtists();

        document.getElementById('btn-add-artist').addEventListener('click', addArtist);
        document.getElementById('btn-delete-selected-artists').addEventListener('click', bulkDeleteArtists);
        document.getElementById('check-all-artists').addEventListener('change', (e) => {
            document.querySelectorAll('.artist-item input[type="checkbox"]').forEach(chk => {
                chk.checked = e.target.checked;
                const artist = chk.closest('.artist-item').dataset.artist;
                if (e.target.checked) selectedArtists.add(artist);
                else selectedArtists.delete(artist);
            });
            updateSelectionUI();
        });

        // Tracks modal
        document.getElementById('btn-close-tracks-modal').addEventListener('click', closeArtistTracksModal);
        document.getElementById('artist-tracks-modal').addEventListener('mousedown', (e) => {
            if (e.target === e.currentTarget) closeArtistTracksModal();
        });
        document.getElementById('btn-save-tracks').addEventListener('click', saveArtistTracks);
        document.getElementById('btn-copy-tracks').addEventListener('click', copyArtistTracks);

        // Поиск по артистам
        const searchInput = document.getElementById('search-input');
        const searchClear = document.getElementById('search-clear');
        searchInput.addEventListener('input', () => {
            const q = searchInput.value.toLowerCase();
            document.querySelectorAll('.artist-item').forEach(item => {
                const name = (item.dataset.artist || '').toLowerCase();
                item.style.display = name.includes(q) ? '' : 'none';
            });
            searchClear.classList.toggle('hidden', !q);
        });
        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();