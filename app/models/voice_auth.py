from datetime import datetime

from mongoengine import (
    BooleanField,
    DateTimeField,
    Document,
    FloatField,
    IntField,
    ListField,
    ReferenceField,
    StringField,
)

from app.models.branch import Branch
from app.models.employee import Employee


class EmployeeVoiceProfile(Document):
    employee_id = ReferenceField(Employee, required=True, unique=True)
    employee_code = StringField(required=True)
    embedding = ListField(FloatField(), required=True)
    sample_count = IntField(required=True)
    minimum_pair_score = FloatField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "employee_voice_profiles",
        "indexes": ["employee_code", "employee_id"],
    }


class FaceVoiceChallenge(Document):
    challenge_id = StringField(required=True, unique=True)
    employee_id = ReferenceField(Employee, required=True)
    employee_code = StringField(required=True)
    branch_id = ReferenceField(Branch, required=True)
    punch_type = StringField(required=True, choices=("punch_in", "punch_out"))
    digits = StringField(required=True)
    face_confidence = FloatField(required=True)
    liveness_challenge = StringField(required=True)
    liveness_motion_score = FloatField(required=True)
    used = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.utcnow)
    expires_at = DateTimeField(required=True)
    used_at = DateTimeField()

    meta = {
        "collection": "face_voice_challenges",
        "indexes": [
            "challenge_id",
            "employee_id",
            "branch_id",
            "used",
            {"fields": ["expires_at"], "expireAfterSeconds": 0},
        ],
    }
