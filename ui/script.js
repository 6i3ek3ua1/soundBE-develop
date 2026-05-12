let systemRunning = false;
let history = [];
let modelsReady = false;
let modelsLoading = false;

const LANGUAGE_LABELS = {
    '': 'Автоопределение',
    en: 'Английский',
    ru: 'Русский',
    es: 'Испанский',
    fr: 'Французский',
    de: 'Немецкий',
    zh: 'Китайский',
    English: 'Английский',
    Russian: 'Русский',
    Spanish: 'Испанский',
    French: 'Французский',
    German: 'Немецкий',
    Chinese: 'Китайский',
    'the detected language': 'Автоопределение',
};

if (typeof eel !== 'undefined') {
    console.log('Eel is available');
    eel.expose(onTextRecognized);
    eel.expose(onTextTranslated);
    eel.expose(onSystemStatus);
    eel.expose(onError);
} else {
    console.error('Eel is not available');
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Page loaded, initializing...');

    if (typeof eel !== 'undefined') {
        loadSystemStatus();
        loadDeviceList();
    } else {
        let attempts = 0;
        const checkEel = setInterval(() => {
            attempts++;
            if (typeof eel !== 'undefined') {
                clearInterval(checkEel);
                loadSystemStatus();
                loadDeviceList();
            } else if (attempts > 50) {
                console.error('Eel failed to load after 5 seconds');
                clearInterval(checkEel);
            }
        }, 100);
    }

    ['translateToggle', 'ttsToggle', 'sourceLangSelect', 'targetLangSelect'].forEach((id) => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', updateRuntimeSettings);
        }
    });
});

async function startCapture() {
    console.log('Starting capture...');
    try {
        if (!modelsReady) {
            showError(modelsLoading ? 'Модели еще загружаются. Дождитесь готовности.' : 'Модели не готовы к запуску');
            await loadSystemStatus();
            return;
        }

        const device = document.getElementById('deviceSelect').value;
        const deviceIdx = device ? parseInt(device, 10) : null;
        const translationEnabled = document.getElementById('translateToggle').checked;
        const ttsEnabled = document.getElementById('ttsToggle').checked;
        const recognitionLanguage = document.getElementById('sourceLangSelect').value;
        const targetLanguage = document.getElementById('targetLangSelect').value;

        if (deviceIdx === null || Number.isNaN(deviceIdx)) {
            document.getElementById('settingsPanel').classList.remove('hidden');
            showError('Выберите аудиоустройство в настройках перед запуском');
            return;
        }

        if (typeof eel !== 'undefined') {
            const started = await eel.start_capture(
                deviceIdx,
                translationEnabled,
                ttsEnabled,
                recognitionLanguage,
                targetLanguage
            )();
            if (!started) {
                await loadSystemStatus();
                showError(modelsLoading ? 'Модели загружаются. Запуск будет доступен после готовности.' : 'Не удалось запустить захват аудио');
                return;
            }
        } else {
            console.error('Eel not available for start capture');
        }

        systemRunning = true;
        updateUI();
    } catch (error) {
        console.error('Error starting capture:', error);
        showError('Ошибка при запуске захвата: ' + error);
    }
}

async function stopCapture() {
    console.log('Stopping capture...');
    try {
        if (typeof eel !== 'undefined') {
            await eel.stop_capture()();
        } else {
            console.error('Eel not available for stop capture');
        }

        systemRunning = false;
        updateUI();
    } catch (error) {
        console.error('Error stopping capture:', error);
        showError('Ошибка при остановке захвата: ' + error);
    }
}

function toggleSettings() {
    const panel = document.getElementById('settingsPanel');
    panel.classList.toggle('hidden');
}

async function updateRuntimeSettings() {
    if (typeof eel === 'undefined') {
        return;
    }

    try {
        await eel.update_runtime_settings(
            document.getElementById('translateToggle').checked,
            document.getElementById('ttsToggle').checked,
            document.getElementById('sourceLangSelect').value,
            document.getElementById('targetLangSelect').value
        )();
        await loadSystemStatus();
    } catch (error) {
        console.error('Error updating runtime settings:', error);
        showError('Ошибка при применении настроек: ' + error);
    }
}

async function loadSystemStatus() {
    if (typeof eel !== 'undefined') {
        try {
            const status = await eel.get_system_status()();
            onSystemStatus(status);
        } catch (error) {
            console.error('Error loading status:', error);
        }
    }
}

async function loadDeviceList() {
    console.log('Loading device list...');
    if (typeof eel !== 'undefined') {
        try {
            const devices = await eel.get_audio_devices()();
            const select = document.getElementById('deviceSelect');
            select.innerHTML = '<option value="">Выбрать устройство...</option>';

            devices.forEach((device) => {
                const option = document.createElement('option');
                if (typeof device === 'object') {
                    option.value = device.id;
                    option.textContent = device.label;
                } else {
                    const match = String(device).match(/^(\d+):/);
                    option.value = match ? match[1] : '';
                    option.textContent = device;
                }
                select.appendChild(option);
            });

            if (select.options.length === 2) {
                select.selectedIndex = 1;
            }
        } catch (error) {
            console.error('Error loading devices:', error);
            showError('Не удалось загрузить список аудиоустройств');
        }
    } else {
        console.error('Eel not available for device loading');
    }
}

function updateUI() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusIndicator = document.getElementById('statusIndicator');

    if (modelsLoading) {
        startBtn.disabled = true;
        stopBtn.disabled = true;
        statusIndicator.className = 'status-indicator processing';
        statusIndicator.textContent = '🟡 Загрузка моделей...';
        return;
    }

    if (!modelsReady) {
        startBtn.disabled = true;
        stopBtn.disabled = true;
        statusIndicator.className = 'status-indicator stopped';
        statusIndicator.textContent = '⚫ Модели не готовы';
        return;
    }

    if (systemRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusIndicator.className = 'status-indicator running';
        statusIndicator.textContent = '🟢 Работает';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusIndicator.className = 'status-indicator stopped';
        statusIndicator.textContent = '⚫ Остановлена';
    }
}

function onTextRecognized(data) {
    console.log('Text recognized:', data);

    const text = data.text || '';
    const inferTime = (data.infer_time || 0).toFixed(2);

    document.getElementById('recognizedText').innerHTML = `<p>${escapeHtml(text)}</p>`;
    document.getElementById('asrTime').textContent = `${inferTime}s`;
    document.getElementById('statusIndicator').className = 'status-indicator processing';
    document.getElementById('statusIndicator').textContent = '🟡 Обработка...';
}

function onTextTranslated(data) {
    console.log('Text translated:', data);

    const originalText = data.original_text || '';
    const translatedText = data.translated_text || '';
    const inferTime = (data.infer_time || 0).toFixed(2);
    const sourceLanguage = data.source_language || getLanguageLabel(document.getElementById('sourceLangSelect').value);
    const targetLanguage = data.target_language || document.getElementById('targetLangSelect').value;

    document.getElementById('translatedText').innerHTML = `<p>${escapeHtml(translatedText)}</p>`;
    document.getElementById('translationTime').textContent = `${inferTime}s`;
    addToHistory(originalText, translatedText, sourceLanguage, targetLanguage);

    if (systemRunning) {
        document.getElementById('statusIndicator').className = 'status-indicator running';
        document.getElementById('statusIndicator').textContent = '🟢 Работает';
    }
}

function onSystemStatus(status) {
    console.log('System status:', status);
    modelsReady = status.models_ready !== false;
    modelsLoading = Boolean(status.models_loading);

    document.getElementById('statusIndicator').textContent =
        status.running ? '🟢 Работает' : '⚫ Остановлена';
    document.getElementById('asrModel').textContent = status.asr_model || '-';
    document.getElementById('recognitionLanguageStatus').textContent =
        status.recognition_language_name || getLanguageLabel(status.recognition_language || '');
    document.getElementById('targetLanguageStatus').textContent =
        getLanguageLabel(status.target_language || document.getElementById('targetLangSelect').value);
    const modelStatus = status.models_loading ? ' (загрузка)' : (status.models_error ? ' (ошибка)' : '');
    document.getElementById('translationModel').textContent =
        status.translation_enabled ? `${status.translation_model || 'Включена'}${modelStatus}` : 'Отключена';

    if (status.models_error) {
        showError(status.models_error);
    }

    setSelectValue('sourceLangSelect', status.recognition_language || '');
    setSelectValue('targetLangSelect', status.target_language || 'English');

    systemRunning = status.running;
    updateUI();
}

function onError(data) {
    console.error('System error:', data);
    showError(`Ошибка: ${data.error} (${data.stage})`);
}

function addToHistory(original, translated, sourceLanguage, targetLanguage) {
    const timestamp = new Date().toLocaleTimeString('ru-RU');
    const item = {
        timestamp,
        original,
        translated,
        sourceLanguage,
        targetLanguage,
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
            (item) =>
                `
        <div class="history-item">
            <span class="timestamp">${item.timestamp}</span>
            <div class="original"><strong>${escapeHtml(getLanguageLabel(item.sourceLanguage))}:</strong> ${escapeHtml(item.original)}</div>
            <div class="translated"><strong>${escapeHtml(getLanguageLabel(item.targetLanguage))}:</strong> ${escapeHtml(item.translated)}</div>
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
    return String(text).replace(/[&<>"']/g, (m) => map[m]);
}

function getLanguageLabel(language) {
    return LANGUAGE_LABELS[language] || language || 'Автоопределение';
}

function setSelectValue(id, value) {
    const select = document.getElementById(id);
    if (select && Array.from(select.options).some((option) => option.value === value)) {
        select.value = value;
    }
}

setInterval(loadSystemStatus, 5000);
