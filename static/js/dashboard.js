async function updatePlaylist() {
    try {
        const response = await fetch('/api/playlist');
        const data = await response.json();
        const listContainer = document.getElementById('playlist-content');

        listContainer.innerHTML = data.songs.map((song, i) => `
            <div class="song ${i === 0 ? 'active' : ''}">
                <span class="song-num">${i === 0 ? '▶' : i + 1}</span>
                <span class="song-name">${song}</span>
            </div>
        `).join('');
    } catch (error) {
        console.error("Error al obtener la playlist:", error);
    }
}

// Cargar al iniciar
document.addEventListener('DOMContentLoaded', updatePlaylist);

// Actualizar cada 20 segundos
setInterval(updatePlaylist, 20000);