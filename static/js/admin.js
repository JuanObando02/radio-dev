let allSongs = [];

async function loadData() {
    try {
        const res = await authFetch('/admin/api/songs');
        const data = await res.json();
        allSongs = data.songs;
        document.getElementById('total-songs').textContent = data.total;
        document.getElementById('disk-used').textContent = data.disk_used;
        document.getElementById('disk-free').textContent = data.disk_free;
        renderSongs(allSongs);
        
        // También actualizar el título actual si el elemento existe
        const nowPlayingEl = document.getElementById('now-playing-title');
        if (nowPlayingEl) {
            // Reusar la lógica del dashboard para obtener el título real
            const statsRes = await fetch('/api/now-playing');
            const stats = await statsRes.json();
            const title = stats?.icestats?.source?.title || '—';
            nowPlayingEl.textContent = title;
        }
    } catch (e) {
        console.error(e);
    }
}

function renderSongs(songs) {
    const container = document.getElementById('songs-list');
    if (!songs.length) {
        container.innerHTML = '<div class="song-row"><span class="song-row-name" style="color:#666">No hay canciones</span></div>';
        return;
    }
    container.innerHTML = songs.map(song => `
<div class="song-row" id="row-${btoa(encodeURIComponent(song))}">
    <span class="song-row-name" title="${song}">${song}</span>
    <div style="display: flex; gap: 8px;">
        <button class="btn-danger" style="border-color: #1DB954; color: #1DB954;" onclick="playNextDirect('${song.replace(/'/g, "\\'")}', this)">Play Next</button>
        <button class="btn-danger" onclick="deleteSong('${song.replace(/'/g, "\\'")}', this)">Eliminar</button>
    </div>
</div>
`).join('');
}

function filterSongs(query) {
    const q = query.toLowerCase();
    const filtered = q ? allSongs.filter(s => s.toLowerCase().includes(q)) : allSongs;
    renderSongs(filtered);
}

async function deleteSong(name, btn) {
    if (!confirm(`¿Eliminar "${name}"?`)) return;
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const res = await authFetch(`/admin/api/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await res.json();
        if (data.ok) {
            allSongs = allSongs.filter(s => s !== name);
            filterSongs(document.getElementById('filter-input').value);
            document.getElementById('total-songs').textContent = allSongs.length;
        } else {
            btn.textContent = 'Error';
            btn.disabled = false;
        }
    } catch (e) {
        btn.textContent = 'Error';
        btn.disabled = false;
    }
}

async function playNextDirect(songName, btn) {
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const res = await fetch(`/api/play-next/${encodeURIComponent(songName)}`, { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = '✓';
            setTimeout(() => {
                btn.textContent = 'Play Next';
                btn.disabled = false;
            }, 2000);
        } else {
            btn.textContent = 'Error';
            btn.disabled = false;
        }
    } catch (e) {
        btn.textContent = 'Error';
        btn.disabled = false;
    }
}

// Upload handlers
const uploadArea = document.getElementById('upload-area');
const uploadInput = document.getElementById('upload-input');

if (uploadArea) {
    uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('drag'); });
    uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag'));
    uploadArea.addEventListener('drop', e => {
        e.preventDefault();
        uploadArea.classList.remove('drag');
        uploadFiles(e.dataTransfer.files);
    });
}

if (uploadInput) {
    uploadInput.addEventListener('change', () => uploadFiles(uploadInput.files));
}

async function uploadFiles(files) {
    if (!files.length) return;
    const wrap = document.getElementById('progress-bar-wrap');
    const bar = document.getElementById('progress-bar');
    const status = document.getElementById('upload-status');
    wrap.style.display = 'block';

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        status.textContent = `Subiendo ${i + 1}/${files.length}: ${file.name}`;
        bar.style.width = `${((i) / files.length) * 100}%`;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await authFetch('/admin/api/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (!data.ok) status.textContent = `Error subiendo ${file.name}`;
        } catch (e) {
            status.textContent = `Error: ${e}`;
        }
    }

    bar.style.width = '100%';
    status.textContent = `✅ ${files.length} archivo(s) subido(s)`;
    setTimeout(() => { wrap.style.display = 'none'; bar.style.width = '0%'; }, 2000);
    loadData();
}

async function logout() {
    await authFetch('/admin/logout', { method: 'POST' });
    window.location.href = '/admin';
}

function authFetch(url, options = {}) {
    const token = localStorage.getItem('admin_token');
    return fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        }
    });
}

async function skipCurrentSong(btn) {
    if (!confirm('¿Saltar la canción actual?')) return;
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const res = await authFetch('/api/admin/skip', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = '⏭️ Saltada';
            setTimeout(() => {
                btn.textContent = 'Saltar canción';
                btn.disabled = false;
            }, 2000);
        } else {
            alert(data.message || 'Error al saltar canción');
            btn.textContent = 'Saltar canción';
            btn.disabled = false;
        }
    } catch (e) {
        console.error(e);
        btn.textContent = 'Saltar canción';
        btn.disabled = false;
    }
}

// Alias para el botón que agregó el usuario
async function skipSong() {
    const btn = event.target || {};
    return skipCurrentSong(btn);
}

// Initial load
if (document.getElementById('songs-list')) {
    loadData();
    setInterval(loadData, 30000);
}
