import logging
import sounddevice as sd
import numpy as np
import queue
import threading
import time


class SoundCapturer:
    def __init__(
        self,
        logger: logging.Logger,
        asr=None,
        sample_rate: int = 16000,
        block_size: int = 1024,
        chunk_seconds: float = 2.0,
        chunk_overlap_seconds: float = 0.5,
    ):
        self.audio_queue = queue.Queue()
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.chunk_seconds = chunk_seconds
        self.chunk_overlap_seconds = chunk_overlap_seconds

        self.asr = asr
        self.l = logger
        self.channels = 1
        self.running = False

        self._buffer = np.zeros((0,), dtype=np.float32)

        self._infer_lock = threading.Lock()

        self.l.info("SoundCapturer initialized")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.l.debug("SoundCapturer status: %s", status)
        self.audio_queue.put(indata.copy())

    def capture(self, device_idx: int = None):
        if device_idx is None:
            self.l.warning("No device id specified, requesting manually...")
            self.list_devices()
            device_idx = self.manual_choose_device()

        self.l.info("SoundCapturer starting capture on device %s", device_idx)
        self.running = True

        # поток обработки очереди
        threading.Thread(target=self._process_loop, daemon=True).start()

        try:
            with sd.InputStream(
                device=device_idx,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._audio_callback,
            ):
                self.l.info("InputStream started")
                while self.running:
                    time.sleep(0.1)
        except Exception as e:
            self.l.exception("SoundCapturer error: %s", e)
        finally:
            self.l.info("SoundCapturer stopped")

    def stop_capture(self):
        self.running = False

    def _process_loop(self):
        chunk_len = int(self.chunk_seconds * self.sample_rate)
        overlap_len = int(self.chunk_overlap_seconds * self.sample_rate)

        while self.running:
            try:
                block = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            mono = block[:, 0].astype(np.float32, copy=False)
            self._buffer = np.concatenate([self._buffer, mono], axis=0)

            # Если накопили чанк — запускаем инференс
            if self._buffer.shape[0] >= chunk_len:
                audio_chunk = self._buffer[:chunk_len].copy()

                keep_from = max(0, chunk_len - overlap_len)
                self._buffer = self._buffer[keep_from:]

                if self.asr is not None and not self._infer_lock.locked():
                    threading.Thread(
                        target=self._run_asr,
                        args=(audio_chunk,),
                        daemon=True
                    ).start()

    def _run_asr(self, audio_chunk: np.ndarray):
        with self._infer_lock:
            t0 = time.perf_counter()

            # инференс
            text, infer_s = self.asr.transcribe(audio_chunk)

            total_s = time.perf_counter() - t0
            rtf = infer_s / (len(audio_chunk) / self.sample_rate)

            if text:
                self.l.info("ASR: %s", text)

            self.l.info("ASR metrics: infer=%.3fs total=%.3fs RTF=%.3f", infer_s, total_s, rtf)

    @staticmethod
    def list_devices() -> dict:
        devices = sd.query_devices()
        real_mics = {}
        for idx, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if dev["max_input_channels"] > 0:
                if any(skip in name_lower for skip in ["stereo", "mix", "output", "input (steam,", "input"]):
                    continue
                if name_lower not in real_mics:
                    real_mics[name_lower] = idx

        print("Микрофоны:")
        for name, idx in real_mics.items():
            print(f"{idx}: {name}")

        return real_mics

    @staticmethod
    def manual_choose_device() -> int:
        device_idx = input("\n\nНомер устройства для перехвата звука: ")
        if device_idx.isdigit():
            device_idx = int(device_idx)
        return device_idx
