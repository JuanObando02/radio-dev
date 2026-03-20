async function updatePlaylist() {
    try {
        // 1. Pedir la lista local
        const resPlaylist = await fetch('/api/playlist');
        const dataPlaylist = await resPlaylist.json();

        // 2. Pedir el estado actual a través de NUESTRO PROXY
        const resIcecast = await fetch('/api/now-playing'); // <--- Ruta interna
        const dataIcecast = await resIcecast.json();

        // Extraer el nombre (ajustado según el JSON que me mostraste)
        // Nota: Si 'title' no aparece, usaremos un fallback
        const source = dataIcecast.icestats.source;
        const currentTitle = source.title || "Transmitiendo...";

        const listContainer = document.getElementById('playlist-content');
        listContainer.innerHTML = dataPlaylist.songs.map((song, i) => {
            // Comparamos si la canción de la lista es la que suena
            const isActive = currentTitle.includes(song) ? 'active' : '';
            return `
                <div class="song ${isActive}">
                    <span class="song-num">${isActive ? '▶' : i + 1}</span>
                    <span class="song-name">${song}</span>
                </div>`;
        }).join('');

    } catch (error) {
        console.error("Error en el Dashboard:", error);
    }
}

setInterval(updatePlaylist, 10000); // Más rápido: cada 10 seg
updatePlaylist();