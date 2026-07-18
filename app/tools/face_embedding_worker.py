from __future__ import annotations

import contextlib
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import cv2
import numpy as np
from insightface.app import FaceAnalysis


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print(json.dumps({"error": "Usage: face_embedding_worker.py <image_path> <gpu_id> [det_size]"}))
        return 2

    image_path = sys.argv[1]
    gpu_id = int(sys.argv[2])
    det_size = int(sys.argv[3]) if len(sys.argv) == 4 else 320

    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        print(json.dumps({"error": "Image decode nahi hui. JPG, PNG ya WEBP image bhejo."}))
        return 0

    providers = ["CPUExecutionProvider"]
    if gpu_id >= 0:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    with contextlib.redirect_stdout(sys.stderr):
        model = FaceAnalysis(name="buffalo_l", providers=providers)
        model.prepare(ctx_id=gpu_id, det_size=(det_size, det_size))
        faces = model.get(image)

    if not faces:
        print(json.dumps({"embedding": None}))
        return 0

    largest_face = max(
        faces,
        key=lambda face: float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])),
    )
    embedding = largest_face.embedding.astype("float32")
    norm = np.linalg.norm(embedding)
    if norm == 0:
        print(json.dumps({"embedding": None}))
        return 0

    print(json.dumps({"embedding": (embedding / norm).astype("float32").tolist()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
