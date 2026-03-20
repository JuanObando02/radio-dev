async function updatePlaylist() {
    try {
        // 1. Obtener la lista de canciones de nuestra API
        const resPlaylist = await fetch('/api/playlist');
        const dataPlaylist = await resPlaylist.json();
        console.log(dataPlaylist);

        // 2. Intentar obtener qué suena ahora mismo desde Icecast
        // Nota: Usamos el endpoint json de Icecast
        const resIcecast = await fetch('https://stream.juanobando.dev/status-json.xsl');
        const dataIcecast = await resIcecast.json();

        // Sacamos el nombre de la canción que Icecast reporta
        const currentPath = dataIcecast.icestats.source.title || "";
        const nowPlaying = currentPath.split('/').pop(); // Limpiamos la ruta

        const listContainer = document.getElementById('playlist-content');

        listContainer.innerHTML = dataPlaylist.songs.map((song) => {
            // Si el nombre coincide con lo que dice Icecast, la resaltamos
            const isActive = song === nowPlaying ? 'active' : '';
            const icon = song === nowPlaying ? '▶' : '•';
            return `
                <div class="song ${isActive}">
                    <span class="song-num">${icon}</span>
                    <span class="song-name">${song}</span>
                </div>`;
        }).join('');

    } catch (error) {
        console.error("Error actualizando Dashboard:", error);
    }
}

setInterval(updatePlaylist, 10000); // Más rápido: cada 10 seg
updatePlaylist();