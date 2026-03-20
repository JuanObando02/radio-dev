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
        const nowPlaying = data.now_playing;

        container.innerHTML = data.songs.map((song, i) => {
            const isActive = (song === nowPlaying) ? 'active' : '';
            return `
                <div class="song ${isActive}">
                    <span class="song-num">${isActive ? '▶' : i + 1}</span>
                    <span class="song-name">${song}</span>
                </div>`;
        }).join('');

    } catch (e) {
        console.error("Error:", e);
    }
}

setInterval(updateDashboard, 5000);
updateDashboard();