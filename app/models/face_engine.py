from __future__ import annotations

import json
import logging
import os
import pickle
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import faiss
import numpy as np

try:
    faiss.omp_set_num_threads(1)
except Exception:
    logger = logging.getLogger(__name__)
    logger.warning("FAISS thread limit set nahi ho paya.", exc_info=True)


logger = logging.getLogger(__name__)


def _decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    import cv2

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Image decode nahi hui. JPG, PNG ya WEBP image bhejo.")
    return image


class FaceEngine:
    """Face model + FAISS index only. Is file me MongoDB/FastAPI logic nahi hai."""

    def __init__(
        self,
        index_dir: str = "./data/face_index",
        threshold: float = 0.45,
        gpu_id: int = -1,
        det_size: int = 320,
        isolate_inference: bool | None = None,
    ) -> None:
        self.dimension = 512
        self.threshold = threshold
        self.gpu_id = gpu_id
        self.det_size = det_size
        self.isolate_inference = sys.platform == "darwin" if isolate_inference is None else isolate_inference
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / "employee_faces.faiss"
        self.map_path = self.index_dir / "employee_id_map.pkl"

        self._lock = threading.RLock()
        self._model: Any | None = None
        self._ready = False

        self.index = self._load_or_create_index()
        self.id_map = self._load_id_map()
        self.next_faiss_id = max(self.id_map.keys(), default=-1) + 1

    @property
    def is_ready(self) -> bool:
        return self._ready

    def initialize(self) -> None:
        with self._lock:
            if self._ready:
                return

            if self.isolate_inference:
                self._ready = True
                return

            from insightface.app import FaceAnalysis

            providers = ["CPUExecutionProvider"]
            if self.gpu_id >= 0:
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

            self._model = FaceAnalysis(name="buffalo_l", providers=providers)
            self._model.prepare(ctx_id=self.gpu_id, det_size=(self.det_size, self.det_size))
            self._ready = True

    def close(self) -> None:
        with self._lock:
            self._model = None
            self._ready = False

    def _load_or_create_index(self) -> faiss.IndexIDMap2:
        if self.index_path.exists():
            index = faiss.read_index(str(self.index_path))
            if index.d != self.dimension:
                raise RuntimeError("FAISS index dimension mismatch. Old index delete/rebuild karo.")
            return index
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dimension))

    def _load_id_map(self) -> dict[int, str]:
        if not self.map_path.exists():
            return {}
        with self.map_path.open("rb") as file:
            data = pickle.load(file)
        return {int(k): str(v) for k, v in data.items()}

    def _save_index(self) -> None:
        temp_index = self.index_path.with_suffix(".tmp.faiss")
        temp_map = self.map_path.with_suffix(".tmp.pkl")

        faiss.write_index(self.index, str(temp_index))
        with temp_map.open("wb") as file:
            pickle.dump(self.id_map, file)

        os.replace(temp_index, self.index_path)
        os.replace(temp_map, self.map_path)

    def _decode_image(self, image_bytes: bytes) -> np.ndarray:
        return _decode_image_bytes(image_bytes)

    def extract_embedding(self, image_bytes: bytes) -> np.ndarray | None:
        if not self._ready or self._model is None:
            if not self._ready or not self.isolate_inference:
                raise RuntimeError("FaceEngine initialize nahi hua.")
            return self._extract_embedding_subprocess(image_bytes)

        image = self._decode_image(image_bytes)
        faces = self._model.get(image)
        if not faces:
            return None

        largest_face = max(
            faces,
            key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])),
        )

        embedding = largest_face.embedding.astype("float32")
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return None
        return embedding / norm

    def _extract_embedding_subprocess(self, image_bytes: bytes) -> np.ndarray | None:
        self._decode_image(image_bytes)

        worker_path = Path(__file__).resolve().parents[1] / "tools" / "face_embedding_worker.py"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="face-", suffix=".img", delete=False) as file:
                file.write(image_bytes)
                temp_path = file.name

            completed = subprocess.run(
                [sys.executable, str(worker_path), temp_path, str(self.gpu_id), str(self.det_size)],
                capture_output=True,
                check=False,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Face model timeout hua. Dobara try karo.") from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.warning("Temporary face image delete nahi hui: %s", temp_path)

        if completed.returncode != 0:
            logger.error("Face subprocess failed: %s", completed.stderr[-2000:])
            raise RuntimeError("Face model crash hua. Server zinda hai; dobara try karo.")

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            logger.error("Face subprocess returned invalid JSON: %s", completed.stdout[-2000:])
            raise RuntimeError("Face model ne invalid response diya. Dobara try karo.") from exc

        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))

        result = payload.get("embedding")
        if result is None:
            return None
        return np.array(result, dtype="float32")

    def add_employee_face(self, employee_id: str, image_bytes: bytes) -> dict[str, Any]:
        embedding = self.extract_embedding(image_bytes)
        if embedding is None:
            return {"success": False, "message": "Image me face detect nahi hua."}

        with self._lock:
            vector = embedding.reshape(1, -1).astype("float32")
            faiss.normalize_L2(vector)

            faiss_id = self.next_faiss_id
            self.index.add_with_ids(vector, np.array([faiss_id], dtype="int64"))
            self.id_map[faiss_id] = employee_id
            self.next_faiss_id += 1
            self._save_index()

        return {"success": True, "employee_id": employee_id, "faiss_id": faiss_id}

    def search_employee(self, image_bytes: bytes) -> dict[str, Any]:
        if self.index.ntotal == 0:
            return {"found": False, "message": "Face index empty hai."}

        embedding = self.extract_embedding(image_bytes)
        if embedding is None:
            return {"found": False, "message": "Image me face detect nahi hua."}

        with self._lock:
            query = embedding.reshape(1, -1).astype("float32")
            faiss.normalize_L2(query)
            scores, ids = self.index.search(query, 1)

        faiss_id = int(ids[0][0])
        score = float(scores[0][0])
        confidence = round(score * 100, 2)
        employee_id = self.id_map.get(faiss_id)

        if faiss_id == -1 or not employee_id:
            return {"found": False, "message": "Match nahi mila."}

        if score < self.threshold:
            return {
                "found": False,
                "employee_id": employee_id,
                "confidence": confidence,
                "message": "Reliable match nahi mila.",
            }

        return {
            "found": True,
            "employee_id": employee_id,
            "faiss_id": faiss_id,
            "score": score,
            "confidence": confidence,
            "message": "Employee matched.",
        }

    def total_faces(self) -> int:
        return int(self.index.ntotal)
