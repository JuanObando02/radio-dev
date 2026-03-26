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
            ? new Date(source.stream_start).toLocaleString('es-CO', { 
                day: '2-digit', 
                month: 'short', 
                year: 'numeric', 
                hour: '2-digit', 
                minute: '2-digit' 
            })
            : '—';
        document.getElementById('now-playing-title').textContent = data.now_playing || '—';
        document.getElementById('total-songs').textContent = data.songs?.length || '0';

        // Reseteo del botón de skip si la canción cambió
        const btnSkip = document.getElementById('btn-skip');
        if (currentSong && currentSong !== data.now_playing) {
            if (btnSkip) {
                btnSkip.disabled = false;
                btnSkip.innerHTML = `⏭ Saltar (<span id="skip-count">0</span>/<span id="skip-required">0</span>)`;
            }
        }

        if (!data.songs || data.songs.length === 0) {
            document.getElementById('playlist-content').innerHTML =
                '<p style="padding: 20px; color: #555;">⏱ Cargando playlist...</p>';
            return;
        }

        allSongs = data.songs;
        currentSong = data.now_playing;
        queue = data.queue || [];

        // Actualizar datos del skip en UI
        if (stats.skip_required !== undefined) {
            btnSkip.style.display = 'flex';
            const skipCountEl = document.getElementById('skip-count');
            const skipReqEl = document.getElementById('skip-required');
            if (skipCountEl) skipCountEl.textContent = stats.skip_votes;
            if (skipReqEl) skipReqEl.textContent = stats.skip_required;
            
            // Si backend indica 0 votos, y nosotros estábamos deshabilitados, nos reactivamos
            // (esto previene quedarse trabado si hubo un reinicio rápido)
            if (stats.skip_votes === 0 && btnSkip.disabled && btnSkip.innerHTML.includes('Votaste')) {
                btnSkip.disabled = false;
                btnSkip.innerHTML = `⏭ Saltar (<span id="skip-count">0</span>/<span id="skip-required">${stats.skip_required}</span>)`;
            }
        }

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

async function searchYoutube() {
    const query = document.getElementById('yt-search-input').value.trim();
    const container = document.getElementById('yt-results');

    if (!query) return;

    container.innerHTML = '<p class="search-empty">🔍 Buscando...</p>';

    try {
        const res = await fetch('/api/search-youtube', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await res.json();

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<p class="search-empty">No se encontraron resultados</p>';
            return;
        }

        container.innerHTML = data.results.map(v => `
            <div class="yt-result">
                <img class="yt-thumb" src="${v.thumbnail || ''}" onerror="this.style.display='none'">
                <div class="yt-info">
                    <div class="yt-title" title="${v.title}">${v.title}</div>
                    <div class="yt-meta">${v.channel} · ${v.duration}</div>
                </div>
                <button class="btn-next" onclick="requestDownload('${v.url.replace(/'/g, "\\'")}', '${v.title.replace(/'/g, "\\'")}', '${v.channel.replace(/'/g, "\\'")}', '${v.duration}', this)">
                    ⬇ Pedir
                </button>
            </div>
        `).join('');

    } catch (e) {
        container.innerHTML = '<p class="search-empty">Error al buscar</p>';
    }
}

async function requestDownload(url, title, channel, duration, btn) {
    btn.disabled = true;
    btn.textContent = '...';

    try {
        const res = await fetch('/api/request-download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title, channel, duration })
        });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = '✓ Enviado';
        } else {
            btn.textContent = 'Error';
            btn.disabled = false;
        }
    } catch (e) {
        btn.textContent = 'Error';
        btn.disabled = false;
    }
}

// Enter para buscar en YouTube
document.getElementById('yt-search-input')
    .addEventListener('keydown', e => { if (e.key === 'Enter') searchYoutube(); });

async function voteSkip() {
    const btn = document.getElementById('btn-skip');
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Votando...';

    try {
        const res = await fetch('/api/vote-skip', { method: 'POST' });
        const data = await res.json();
        
        if (res.ok && data.ok) {
            if (data.skipped) {
                btn.innerHTML = '✨ Saltado';
                setTimeout(updateDashboard, 1000);
            } else {
                btn.innerHTML = '✅ Votado';
                setTimeout(updateDashboard, 500);
            }
        } else {
            alert(data.error || "Ocurrió un error al votar");
            if (data.error && data.error.includes("Ya has votado")) {
                btn.disabled = true;
                btn.innerHTML = '✅ Ya votaste';
            } else {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }
    } catch (e) {
        alert("Error de conexión");
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

setInterval(updateDashboard, 5000);
updateDashboard();