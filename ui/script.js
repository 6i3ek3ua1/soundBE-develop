// Global State
let systemRunning = false;
let history = [];

// Initialize Eel
if (typeof eel !== 'undefined') {
    eel.expose(onTextRecognized);
    eel.expose(onTextTranslated);
    eel.expose(onSystemStatus);
    eel.expose(onError);
}

// On page load
document.addEventListener('DOMContentLoaded', function() {
    loadSystemStatus();
    loadDeviceList();
});

// Start Capture
async function startCapture() {
    try {
        const device = document.getElementById('deviceSelect').value;
        const deviceIdx = device ? parseInt(device) : null;

        if (typeof eel !== 'undefined') {
            await eel.start_capture(deviceIdx);
        }

        systemRunning = true;
        updateUI();
    } catch (error) {
        console.error('Error starting capture:', error);
        showError('Ошибка при запуске захвата: ' + error);
    }
}

// Stop Capture
async function stopCapture() {
    try {
        if (typeof eel !== 'undefined') {
            await eel.stop_capture();
        }

        systemRunning = false;
        updateUI();
    } catch (error) {
        console.error('Error stopping capture:', error);
        showError('Ошибка при остановке захвата: ' + error);
    }
}

// Toggle Settings
function toggleSettings() {
    const panel = document.getElementById('settingsPanel');
    panel.classList.toggle('hidden');
}

// Load System Status
async function loadSystemStatus() {
    if (typeof eel !== 'undefined') {
        try {
            const status = await eel.get_system_status();
            onSystemStatus(status);
        } catch (error) {
            console.error('Error loading status:', error);
        }
    }
}

// Load Device List
async function loadDeviceList() {
    if (typeof eel !== 'undefined') {
        try {
            const devices = await eel.get_audio_devices();
            const select = document.getElementById('deviceSelect');

            devices.forEach((device, idx) => {
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = device;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading devices:', error);
        }
    }
}

// Update UI based on system state
function updateUI() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusIndicator = document.getElementById('statusIndicator');

    if (systemRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusIndicator.className = 'status-indicator running';
        statusIndicator.innerHTML = '🟢 Работает';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusIndicator.className = 'status-indicator stopped';
        statusIndicator.innerHTML = '⚫ Остановлена';
    }
}

// Callbacks from Python

function onTextRecognized(data) {
    console.log('Text recognized:', data);

    const text = data.text || '';
    const inferTime = (data.infer_time || 0).toFixed(2);

    // Update recognized text display
    const recognizedDiv = document.getElementById('recognizedText');
    recognizedDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;

    // Update time badge
    document.getElementById('asrTime').textContent = `${inferTime}s`;

    // Update status
    document.getElementById('statusIndicator').className = 'status-indicator processing';
    document.getElementById('statusIndicator').innerHTML = '🟡 Обработка...';
}

function onTextTranslated(data) {
    console.log('Text translated:', data);

    const originalText = data.original_text || '';
    const translatedText = data.translated_text || '';
    const inferTime = (data.infer_time || 0).toFixed(2);

    // Update translated text display
    const translatedDiv = document.getElementById('translatedText');
    translatedDiv.innerHTML = `<p>${escapeHtml(translatedText)}</p>`;

    // Update time badge
    document.getElementById('translationTime').textContent = `${inferTime}s`;

    // Add to history
    addToHistory(originalText, translatedText);

    // Reset status
    if (systemRunning) {
        document.getElementById('statusIndicator').className = 'status-indicator running';
        document.getElementById('statusIndicator').innerHTML = '🟢 Работает';
    }
}

function onSystemStatus(status) {
    console.log('System status:', status);

    document.getElementById('statusIndicator').textContent =
        status.running ? '🟢 Работает' : '⚫ Остановлена';
    document.getElementById('asrModel').textContent = status.asr_model || '-';
    document.getElementById('translationModel').textContent =
        status.translation_enabled ? 'Qwen2-4B-Instruct' : 'Отключена';

    systemRunning = status.running;
    updateUI();
}

function onError(data) {
    console.error('System error:', data);
    showError(`Ошибка: ${data.error} (${data.stage})`);
}

// Helper Functions

function addToHistory(original, translated) {
    const timestamp = new Date().toLocaleTimeString('ru-RU');
    const item = {
        timestamp,
        original,
        translated,
    };

    history.unshift(item);
    if (history.length > 50) {
        history.pop();
    }

    updateHistoryDisplay();
}

function updateHistoryDisplay() {
    const historyList = document.getElementById('historyList');

    if (history.length === 0) {
        historyList.innerHTML = '<p class="placeholder">История пуста</p>';
        return;
    }

    historyList.innerHTML = history
        .map(
            (item, idx) =>
                `
        <div class="history-item">
            <span class="timestamp">${item.timestamp}</span>
            <div class="original"><strong>RU:</strong> ${escapeHtml(item.original)}</div>
            <div class="translated"><strong>EN:</strong> ${escapeHtml(item.translated)}</div>
        </div>
        `
        )
        .join('');
}

function clearHistory() {
    if (confirm('Вы уверены, что хотите очистить историю?')) {
        history = [];
        updateHistoryDisplay();
    }
}

function showError(message) {
    const errorEl = document.getElementById('errorMessage');
    errorEl.textContent = message;

    setTimeout(() => {
        errorEl.textContent = '-';
    }, 5000);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
}

// Refresh status periodically
setInterval(loadSystemStatus, 5000);
