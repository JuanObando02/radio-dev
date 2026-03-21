let allSongs = [];
let currentSong = '';
let queue = [];

async function updateDashboard() {
    try {
        const [playlistRes, statsRes] = await Promise.all([
            fetch('/api/playlist'),
            fetch('/api/now-playing')
        ]);
        const data = await playlistRes.json();
        const stats = await statsRes.json();

        // --- Oyentes ---
        const source = stats?.icestats?.source;
        document.getElementById('listeners').textContent = source?.listeners ?? '—';
        document.getElementById('peak').textContent = source?.listener_peak ?? '—';
        document.getElementById('stream-start').textContent = source?.stream_start
            ? new Date(source.stream_start).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
            : '—';

        if (!data.songs || data.songs.length === 0) {
            document.getElementById('playlist-content').innerHTML =
                '<p style="padding: 20px; color: #555;">⏱ Cargando playlist...</p>';
            return;
        }

        allSongs = data.songs;
        currentSong = data.now_playing;
        queue = data.queue || [];

        renderPlaylist();
        renderQueue();

        // Scroll automático a la canción activa
        const activeEl = document.querySelector('#playlist-scroll .song.active');
        if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

    } catch (e) {
        console.error("Error:", e);
    }
}

function songRow(song, indicator, showBtn = true) {
    const isActive = song === currentSong;
    const btnHtml = showBtn && !isActive
        ? `<button class="btn-next" onclick="playNext('${song.replace(/'/g, "\\'")}', this)">+ Cola</button>`
        : '';
    return `
        <div class="song ${isActive ? 'active' : ''}">
            <span class="song-num">${indicator}</span>
            <span class="song-name" title="${song}">${song}</span>
            ${btnHtml}
        </div>`;
}

function renderPlaylist() {
    const container = document.getElementById('playlist-content');
    container.innerHTML = allSongs.map((song, i) => {
        const isActive = song === currentSong;
        return songRow(song, isActive ? '▶' : i + 1);
    }).join('');
}

function renderQueue() {
    const container = document.getElementById('queue-content');
    if (queue.length === 0) {
        container.innerHTML = '<p class="search-empty">La cola está vacía — las canciones siguientes las elige Liquidsoap en shuffle</p>';
        return;
    }
    container.innerHTML = queue.map((song, i) => songRow(song, i + 1, false)).join('');
}

function searchSongs(query) {
    const container = document.getElementById('search-results');
    const q = query.trim().toLowerCase();

    if (!q) {
        container.innerHTML = '<p class="search-empty">Escribe para buscar canciones</p>';
        return;
    }

    const results = allSongs.filter(s => s.toLowerCase().includes(q));

    if (results.length === 0) {
        container.innerHTML = '<p class="search-empty">No se encontraron canciones</p>';
        return;
    }

    container.innerHTML = results.map((song, i) => songRow(song, allSongs.indexOf(song) + 1)).join('');
}

async function playNext(songName, btn) {
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const res = await fetch(`/api/play-next/${encodeURIComponent(songName)}`, { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = '✓';
            setTimeout(updateDashboard, 500);
        } else {
            btn.textContent = 'Error';
            btn.disabled = false;
        }
    } catch (e) {
        btn.textContent = 'Error';
        btn.disabled = false;
    }
}

setInterval(updateDashboard, 5000);
updateDashboard();