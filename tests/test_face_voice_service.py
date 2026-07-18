from app.services.face_voice_service import FaceVoiceService


def test_random_digits_only_uses_one_to_six():
    for _ in range(100):
        digits = FaceVoiceService._random_digits()
        assert len(digits) == 6
        assert set(digits) <= set("123456")
        assert len(set(digits)) >= 3
