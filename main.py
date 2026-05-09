from logging_tools import logging_tools
from config import load_config
from services import sound_capture
from services.asr_whisper import WhisperASR
import pyfiglet


def main():
    config = load_config()
    logger = logging_tools.get_logger("", level=config.LOG_LEVEL, file=config.LOG_FILE)

    whisper_model = getattr(config, "WHISPER_MODEL", "base")
    whisper_lang = getattr(config, "WHISPER_LANGUAGE", "en")
    whisper_fp16 = str(getattr(config, "WHISPER_FP16", "0")) in ("1", "true", "True")

    asr = WhisperASR(model_name=whisper_model, language=whisper_lang, fp16=whisper_fp16)

    sound_capturer = sound_capture.SoundCapturer(logger=logger, asr=asr)
    sound_capturer.capture()


if __name__ == "__main__":
    print(pyfiglet.figlet_format("SoundBe"))
    main()
