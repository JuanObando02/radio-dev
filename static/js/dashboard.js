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
        const listeners = source?.listeners ?? '—';
        const peak = source?.listener_peak ?? '—';
        const streamStart = source?.stream_start
            ? new Date(source.stream_start).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
            : '—';

        document.getElementById('listeners').textContent = listeners;
        document.getElementById('peak').textContent = peak;
        document.getElementById('stream-start').textContent = streamStart;

        // --- Playlist ---
        const container = document.getElementById('playlist-content');

        if (!data.songs || data.songs.length === 0) {
            container.innerHTML = '<p style="padding: 20px;">⏱ Cargando playlist...</p>';
            return;
        }

        const nowPlaying = data.now_playing;
        const nextSong = data.next_song;

        container.innerHTML = data.songs.map((song, i) => {
            const isActive = song === nowPlaying ? 'active' : '';
            const isNext = song === nextSong ? 'next' : '';

            let indicator = i + 1;
            if (isActive) indicator = '▶';
            else if (isNext) indicator = '⏭';

            return `
                <div class="song ${isActive} ${isNext}">
                    <span class="song-num">${indicator}</span>
                    <span class="song-name">${song}</span>
                    ${!isActive ? `
                    <button class="btn-next" onclick="playNext('${song.replace(/'/g, "\\'")}', this)">
                        Siguiente
                    </button>` : ''}
                </div>`;
        }).join('');

    } catch (e) {
        console.error("Error:", e);
    }
}

async function playNext(songName, btn) {
    btn.disabled = true;
    btn.textContent = '...';
    try {
        const res = await fetch(`/api/play-next/${encodeURIComponent(songName)}`, {
            method: 'POST'
        });
        const data = await res.json();
        if (data.ok) {
            btn.textContent = '✓ Encolada';
            // Refrescar el dashboard para mostrar el indicador ⏭
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