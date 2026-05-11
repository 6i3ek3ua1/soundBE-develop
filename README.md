# 🎤 SoundBE - Real-time Speech Recognition & Translation System

Локальная система распознавания речи, перевода и озвучки на другом языке. Работает полностью локально без использования интернета и внешних API.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.9+-brightgreen)
![Status](https://img.shields.io/badge/status-Active-success)

## 🌟 Особенности

- 🎙️ **Захват аудио в реальном времени** - работает с любым подключенным микрофоном
- 🗣️ **Распознавание речи (ASR)** - OpenAI Whisper с поддержкой 99 языков
- 🌐 **Перевод текста** - Qwen2-4B-Instruct + vLLM (локально!)
- 🔊 **Озвучка (TTS)** - pyttsx3 для синтеза речи
- 💻 **Веб-интерфейс** - красивый UI на Eel с историей переводов
- 📱 **Адаптивный дизайн** - работает на ПК и мобильных
- ⚡ **Полностью локальная работа** - не требует интернета
- 🔒 **Приватная** - все данные остаются на компьютере

## 🏗️ Архитектура

```
Микрофон
   ↓
SoundCapturer (sounddevice)
   ↓
Whisper ASR (распознавание)
   ↓
Qwen2 Translation (перевод через vLLM)
   ↓
pyttsx3 TTS (озвучка)
   ↓
Динамики / Веб-интерфейс
```

## 📋 Требования

- **Python** 3.9 или выше
- **RAM** минимум 8GB
- **VRAM** минимум 6GB (рекомендуется GPU)
- **Свободное место** ~6-8GB для моделей
- **ОС** Windows, Linux или macOS

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонируем репозиторий
git clone <repo-url>
cd soundBE-develop

# Создаём виртуальное окружение
python -m venv venv

# Активируем (Windows)
venv\Scripts\activate
# или для Linux/Mac:
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2. Конфигурация (опционально)

```bash
# Копируем пример конфига
cp .init.example .init

# Редактируем под свои нужды
# Основные параметры:
# - WHISPER_MODEL: base (рекомендуется), tiny, small, medium, large
# - TRANSLATION_MODEL: Qwen/Qwen2-4B-Instruct
# - TARGET_LANGUAGE: English, Russian, Spanish и т.д.
```

### 3. Запуск

```bash
# Запуск с веб-интерфейсом
python main.py

# Или без интерфейса (консоль)
python main.py --no-ui

# С определённым устройством
python main.py --device 1

# С кастомным портом
python main.py --ui-port 8080
```

При первом запуске загружаются модели (~3-4GB):
- OpenAI Whisper (base - 74MB)
- Qwen2-4B-Instruct (~9GB)

После загрузки откроется веб-интерфейс на `http://localhost:8000`

## 💡 Использование

### Веб-интерфейс

1. **Запуск захвата** - кнопка "▶ Начать"
2. **Выбор микрофона** - в разделе "⚙ Настройки"
3. **Переключение функций** - включение/отключение перевода и озвучки
4. **Просмотр результатов** - отображаются в реальном времени
5. **История** - сохраняются последние 50 переводов

### Командная строка

```bash
# Просмотр доступных устройств
python main.py --no-ui
# Система спросит номер устройства

# Просмотр всех параметров
python main.py --help
```

## ⚙️ Конфигурация

Параметры в файле `.init`:

```ini
# ASR (Automatic Speech Recognition)
WHISPER_MODEL=base              # tiny/base/small/medium/large
WHISPER_LANGUAGE=en             # Язык распознавания
WHISPER_FP16=0                  # Использовать FP16

# Перевод
TRANSLATION_ENABLED=1           # Включить/отключить
TRANSLATION_MODEL=Qwen/Qwen2-4B-Instruct
TARGET_LANGUAGE=English

# TTS (Text-to-Speech)
TTS_ENABLED=1                   # Включить/отключить
TTS_LANGUAGE=en

# Логирование
LOG_LEVEL=INFO                  # DEBUG/INFO/WARNING/ERROR
LOG_FILE=soundbe.log

# UI
UI_PORT=8000
```

## 📊 Производительность

Тестировано на RTX 3060 (12GB VRAM):

| Компонент | Модель | Время |
|-----------|--------|-------|
| ASR | Whisper base | ~500ms (2 сек аудио) |
| Translation | Qwen2-4B | ~150ms |
| TTS | pyttsx3 | ~100ms |
| **Общий латенси** | **Все вместе** | **~1-2 сек** |

## 🔧 Решение проблем

### "CUDA not available" или "Out of memory"

```bash
# Использовать CPU (медленнее)
export CUDA_VISIBLE_DEVICES=""
python main.py

# Или использовать меньшую модель
# В .init файле установить: WHISPER_MODEL=tiny
```

### Микрофон не работает

```bash
# Просмотреть доступные устройства
python main.py --no-ui

# Выбрать правильный номер
python main.py --device <номер>
```

### Низкая скорость на CPU

Система оптимизирована для GPU. Для CPU:
1. Используйте меньшие модели (WHISPER_MODEL=tiny)
2. Отключите перевод (TRANSLATION_ENABLED=0)
3. Увеличьте chunk_seconds в SoundCapturer

### Проблемы с TTS

Если озвучка не работает:
```bash
# Переустановить pyttsx3
pip install --upgrade pyttsx3

# Проверить доступные голоса
python -c "import pyttsx3; e=pyttsx3.init(); print([v.name for v in e.getProperty('voices')])"
```

## 📚 Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) - полная архитектура системы
- [Конфигурация](.init.example) - все параметры
- Логи - сохраняются в `soundbe.log`

## 🤝 Участие в разработке

Приглашаем к улучшению проекта!

Возможные улучшения:
- [ ] Поддержка других TTS (Glow-TTS, Tacotron2)
- [ ] Виртуальные микрофоны (VB-Cable)
- [ ] Кэширование переводов
- [ ] Экспорт в различные форматы
- [ ] Многосессионная работа
- [ ] REST API

## 📄 Лицензия

MIT License - свободно используйте в коммерческих и личных целях

## 🙏 Спасибо

- OpenAI за Whisper
- Alibaba за Qwen2
- vLLM команде за отличный инференс движок
- Eel разработчикам за мост между Python и JS

## 📞 Контакты

- 🐛 Баги - GitHub Issues
- 💬 Обсуждение - GitHub Discussions
- 📧 Вопросы - создайте Issue

---

**Версия:** 1.0.0  
**Статус:** Активная разработка  
**Последнее обновление:** 2024  

⭐ Если проект полезен, не забудьте star!
