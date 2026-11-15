/**
 * SoundFlow Visual Player (Simulación Interactiva)
 * Permite simular reproducción, pausa, avance, retroceso y volumen sin audio real ni protegido.
 */

document.addEventListener('DOMContentLoaded', () => {
    const playBtn = document.getElementById('sf-play-btn');
    const playIcon = document.getElementById('sf-play-icon');
    const prevBtn = document.getElementById('sf-prev-btn');
    const nextBtn = document.getElementById('sf-next-btn');
    const progressBar = document.getElementById('sf-progress-bar');
    const progressFill = document.getElementById('sf-progress-fill');
    const currentTimeEl = document.getElementById('sf-current-time');
    const durationEl = document.getElementById('sf-duration');
    const playerTitle = document.getElementById('sf-player-title');
    const playerArtist = document.getElementById('sf-player-artist');
    const playerCover = document.getElementById('sf-player-cover');
    const volumeSlider = document.getElementById('sf-volume-slider');

    let isPlaying = false;
    let currentSeconds = 0;
    let totalSeconds = 210;
    let intervalId = null;

    // Recuperar estado previo de sessionStorage si existe
    const savedState = sessionStorage.getItem('sf_player_state');
    if (savedState) {
        try {
            const data = JSON.parse(savedState);
            playerTitle.textContent = data.title || "SoundFlow Session";
            playerArtist.textContent = data.artist || "SoundFlow Artist";
            if (data.cover) playerCover.src = data.cover;
            if (data.duration) totalSeconds = data.duration;
            durationEl.textContent = formatTime(totalSeconds);
        } catch (e) {
            console.error("Error al cargar estado del reproductor", e);
        }
    }

    function formatTime(secs) {
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    function updateProgress() {
        if (!isPlaying) return;
        currentSeconds++;
        if (currentSeconds >= totalSeconds) {
            currentSeconds = 0;
        }
        const pct = (currentSeconds / totalSeconds) * 100;
        progressFill.style.width = `${pct}%`;
        currentTimeEl.textContent = formatTime(currentSeconds);
    }

    function togglePlay() {
        isPlaying = !isPlaying;
        if (isPlaying) {
            playIcon.className = "fas fa-pause";
            if (!intervalId) {
                intervalId = setInterval(updateProgress, 1000);
            }
        } else {
            playIcon.className = "fas fa-play";
            if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
            }
        }
    }

    if (playBtn) {
        playBtn.addEventListener('click', togglePlay);
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            currentSeconds = 0;
            progressFill.style.width = '0%';
            currentTimeEl.textContent = '0:00';
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            currentSeconds = Math.min(totalSeconds, currentSeconds + 15);
            const pct = (currentSeconds / totalSeconds) * 100;
            progressFill.style.width = `${pct}%`;
            currentTimeEl.textContent = formatTime(currentSeconds);
        });
    }

    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const width = rect.width;
            const pct = Math.max(0, Math.min(1, clickX / width));
            currentSeconds = Math.floor(pct * totalSeconds);
            progressFill.style.width = `${pct * 100}%`;
            currentTimeEl.textContent = formatTime(currentSeconds);
        });
    }

    // Escuchar botones de reproducir en tarjetas o listas
    document.querySelectorAll('.sf-btn-play-trigger').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const title = btn.getAttribute('data-title') || "Canción";
            const artist = btn.getAttribute('data-artist') || "Artista";
            const cover = btn.getAttribute('data-cover') || "/static/musica/img/cover_placeholder.svg";
            const duration = parseInt(btn.getAttribute('data-duration') || "200", 10);

            playerTitle.textContent = title;
            playerArtist.textContent = artist;
            playerCover.src = cover;
            totalSeconds = duration;
            currentSeconds = 0;
            durationEl.textContent = formatTime(totalSeconds);
            currentTimeEl.textContent = "0:00";
            progressFill.style.width = "0%";

            sessionStorage.setItem('sf_player_state', JSON.stringify({
                title, artist, cover, duration
            }));

            if (!isPlaying) {
                togglePlay();
            }
        });
    });

    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            const volIcon = document.getElementById('sf-vol-icon');
            const val = parseInt(e.target.value, 10);
            if (val === 0) {
                volIcon.className = "fas fa-volume-mute";
            } else if (val < 50) {
                volIcon.className = "fas fa-volume-down";
            } else {
                volIcon.className = "fas fa-volume-up";
            }
        });
    }
});
