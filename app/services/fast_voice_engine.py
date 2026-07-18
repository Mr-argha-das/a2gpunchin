from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import threading
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Sequence

import numpy as np


ENGLISH_MODEL = "vosk-model-small-en-in-0.4"
HINDI_MODEL = "vosk-model-small-hi-0.22"

ENGLISH_GRAMMAR = [
    "zero", "oh", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "[unk]",
]
HINDI_GRAMMAR = [
    "शून्य", "जीरो", "एक", "दो", "तीन", "चार", "पांच", "पाँच",
    "छह", "छः", "सात", "आठ", "नौ", "[unk]",
]

WORD_TO_DIGIT = {
    "zero": "0", "oh": "0", "jiro": "0", "jeero": "0", "shunya": "0",
    "शून्य": "0", "जीरो": "0",
    "one": "1", "won": "1", "ek": "1", "एक": "1",
    "two": "2", "to": "2", "too": "2", "do": "2", "दो": "2",
    "three": "3", "teen": "3", "तीन": "3",
    "four": "4", "for": "4", "char": "4", "chaar": "4", "चार": "4",
    "five": "5", "panch": "5", "paanch": "5", "पांच": "5", "पाँच": "5",
    "six": "6", "che": "6", "chhe": "6", "chhah": "6", "छह": "6", "छः": "6",
    "seven": "7", "saat": "7", "सात": "7",
    "eight": "8", "ate": "8", "aath": "8", "आठ": "8",
    "nine": "9", "nau": "9", "नौ": "9",
}


def _load_voice_dependencies():
    try:
        import torch
        from speechbrain.inference.classifiers import EncoderClassifier
        from vosk import KaldiRecognizer, Model, SetLogLevel
    except ImportError as exc:
        package = getattr(exc, "name", None) or str(exc)
        raise RuntimeError(
            f"Voice dependency missing: {package}. Run `pip install -r requirements.txt` in the same Python environment."
        ) from exc
    return torch, EncoderClassifier, KaldiRecognizer, Model, SetLogLevel


def _safe_download_model(root: Path, model_name: str) -> Path:
    model_dir = root / model_name

    if model_dir.is_dir():
        return model_dir

    root.mkdir(parents=True, exist_ok=True)

    archive = root / f"{model_name}.zip"
    temporary = root / f".{model_name}-extracting"

    model_url = (
        "https://huggingface.co/localstack/vosk-models/resolve/"
        "134b459c770227b318e258e933bca437c107b198/"
        f"{model_name}.zip?download=true"
    )

    urllib.request.urlretrieve(model_url, archive)

    if temporary.exists():
        shutil.rmtree(temporary)

    temporary.mkdir(parents=True)

    try:
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                destination = (temporary / member.filename).resolve()

                if not destination.is_relative_to(temporary.resolve()):
                    raise RuntimeError("Unsafe Vosk ZIP path")

            package.extractall(temporary)

        extracted = temporary / model_name

        if not extracted.is_dir():
            raise RuntimeError(
                f"Vosk model folder missing: {model_name}"
            )

        extracted.replace(model_dir)

    finally:
        archive.unlink(missing_ok=True)

        if temporary.exists():
            shutil.rmtree(temporary)

    return model_dir

class FastVoiceEngine:
    def __init__(
        self,
        data_dir: str = "./data/voice",
        speaker_threshold: float = 0.35,
        device: str = "cpu",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.speaker_threshold = speaker_threshold
        self.device = device
        self.sample_rate = 16_000
        self._speaker_model: Any | None = None
        self._english_model: Any | None = None
        self._hindi_model: Any | None = None
        self._torch: Any | None = None
        self._kaldi_recognizer: Any | None = None
        self._ffmpeg_path: str | None = None
        self._inference_lock = threading.RLock()
        self._recognizer_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="voice-verify")
        self.is_ready = False
        self.last_error: str | None = None

    def initialize(self) -> None:
        if self.is_ready:
            return
        torch, EncoderClassifier, KaldiRecognizer, Model, SetLogLevel = _load_voice_dependencies()
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("Voice dependency missing: ffmpeg. Install ffmpeg and restart backend.")
        SetLogLevel(-1)
        model_root = self.data_dir / "vosk_models"
        english_path = _safe_download_model(model_root, ENGLISH_MODEL)
        hindi_path = _safe_download_model(model_root, HINDI_MODEL)
        self._torch = torch
        self._ffmpeg_path = ffmpeg_path
        self._kaldi_recognizer = KaldiRecognizer
        self._english_model = Model(str(english_path))
        self._hindi_model = Model(str(hindi_path))
        self._speaker_model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.device},
        )
        self.last_error = None
        self.is_ready = True

    @staticmethod
    def _normalise(value: np.ndarray) -> np.ndarray:
        value = np.asarray(value, dtype="float32").reshape(-1)
        norm = float(np.linalg.norm(value))
        if norm <= 1e-8:
            raise ValueError("Voice embedding empty hai")
        return value / norm

    def decode_audio(self, audio_bytes: bytes):
        if not audio_bytes or len(audio_bytes) > 8 * 1024 * 1024:
            raise ValueError("Audio empty hai ya 8MB se badi hai")
        if not self.is_ready or self._torch is None or self._ffmpeg_path is None:
            raise RuntimeError(self.last_error or "FastVoiceEngine initialize nahi hua")
        try:
            result = subprocess.run(
                [
                    self._ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-f",
                    "s16le",
                    "-acodec",
                    "pcm_s16le",
                    "-ac",
                    "1",
                    "-ar",
                    str(self.sample_rate),
                    "pipe:1",
                ],
                input=audio_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=12,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Audio decode timeout hua; chhoti recording bhejo") from exc
        if result.returncode != 0:
            raise ValueError("Audio decode nahi hui; WAV, WebM, OGG ya M4A bhejo")
        if not result.stdout:
            raise ValueError("Audio samples nahi mile")
        samples = np.frombuffer(result.stdout, dtype=np.int16).astype("float32") / 32768.0
        duration = len(samples) / self.sample_rate
        if not 1.0 <= duration <= 8.0:
            raise ValueError("Recording 1 se 8 seconds ke beech honi chahiye")
        rms = float(np.sqrt(np.mean(np.square(samples)) + 1e-12))
        clipping = float(np.mean(np.abs(samples) >= 0.995))
        active = float(np.mean(np.abs(samples) >= max(0.008, rms * 0.35)))
        if rms < 0.008:
            raise ValueError("Audio silent ya bahut halki hai")
        if clipping > 0.02:
            raise ValueError("Audio distorted/clipped hai")
        if active < 0.10:
            raise ValueError("Recording mein enough speech nahi hai")
        samples /= max(float(np.max(np.abs(samples))), 1e-6)
        waveform = self._torch.from_numpy(samples).unsqueeze(0)
        return waveform, {
            "duration_seconds": round(duration, 3),
            "rms": round(rms, 6),
            "active_ratio": round(active, 6),
        }

    def embedding(self, waveform: torch.Tensor) -> np.ndarray:
        if not self.is_ready or self._speaker_model is None or self._torch is None:
            raise RuntimeError(self.last_error or "FastVoiceEngine initialize nahi hua")
        with self._inference_lock, self._torch.inference_mode():
            result = self._speaker_model.encode_batch(waveform.to(self.device))
        return self._normalise(result.squeeze().cpu().numpy())

    def enroll(self, recordings: Sequence[bytes]) -> dict[str, Any]:
        if not 5 <= len(recordings) <= 8:
            raise ValueError("Enrollment ke liye 5 se 8 recordings required hain")
        embeddings: list[np.ndarray] = []
        qualities: list[dict[str, float]] = []
        for recording in recordings:
            waveform, quality = self.decode_audio(recording)
            embeddings.append(self.embedding(waveform))
            qualities.append(quality)
        pair_scores = [
            float(np.dot(embeddings[i], embeddings[j]))
            for i in range(len(embeddings))
            for j in range(i + 1, len(embeddings))
        ]
        minimum_pair_score = min(pair_scores)
        if minimum_pair_score < 0.25:
            raise ValueError(
                f"Enrollment samples same speaker jaise nahi hain; minimum score={minimum_pair_score:.4f}"
            )
        profile = self._normalise(np.mean(np.stack(embeddings), axis=0))
        return {
            "embedding": profile.tolist(),
            "sample_count": len(recordings),
            "minimum_pair_score": round(minimum_pair_score, 4),
            "quality": qualities,
        }

    @staticmethod
    def _recognize(recognizer_class, model, grammar: list[str], samples: np.ndarray) -> str:
        recognizer = recognizer_class(model, 16_000, json.dumps(grammar, ensure_ascii=False))
        recognizer.AcceptWaveform((np.clip(samples, -1, 1) * 32767).astype("int16").tobytes())
        return str(json.loads(recognizer.FinalResult()).get("text", "")).strip()

    @staticmethod
    def _parse_digits(text: str) -> str:
        devanagari = {ord("०") + index: str(index) for index in range(10)}
        translated = text.translate(devanagari)
        direct = "".join(character for character in translated if character.isdigit())
        if len(direct) == 6:
            return direct
        return "".join(WORD_TO_DIGIT.get(token.lower(), "") for token in translated.split())

    def verify(self, stored_embedding: Sequence[float], expected_digits: str, audio_bytes: bytes) -> dict[str, Any]:
        if not self.is_ready or self._english_model is None or self._hindi_model is None or self._kaldi_recognizer is None:
            raise RuntimeError(self.last_error or "FastVoiceEngine initialize nahi hua")
        waveform, quality = self.decode_audio(audio_bytes)
        samples = waveform.squeeze(0).numpy()
        candidate_future = self._recognizer_pool.submit(self.embedding, waveform)
        english_future = self._recognizer_pool.submit(
            self._recognize,
            self._kaldi_recognizer,
            self._english_model,
            ENGLISH_GRAMMAR,
            samples,
        )
        hindi_future = self._recognizer_pool.submit(
            self._recognize,
            self._kaldi_recognizer,
            self._hindi_model,
            HINDI_GRAMMAR,
            samples,
        )
        english_text = english_future.result()
        hindi_text = hindi_future.result()
        parsed = [self._parse_digits(english_text), self._parse_digits(hindi_text)]
        digits_match = any(secrets.compare_digest(value, expected_digits) for value in parsed)
        if not digits_match:
            return {
                "verified": False,
                "reason": "spoken_digits_do_not_match",
                "quality": quality,
            }
        candidate = candidate_future.result()
        reference = self._normalise(np.asarray(stored_embedding, dtype="float32"))
        speaker_score = float(np.dot(reference, candidate))
        verified = speaker_score >= self.speaker_threshold
        return {
            "verified": verified,
            "reason": "matched" if verified else "speaker_mismatch",
            "speaker_score": round(speaker_score, 4),
            "quality": quality,
        }
