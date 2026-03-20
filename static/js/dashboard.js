const audio = document.getElementById('radio-player');

async function updateDashboard() {
    try {
        const res = await fetch('/api/playlist');
        const data = await res.json();

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

setInterval(updateDashboard, 5000); // cada 5s en vez de 10
updateDashboard();