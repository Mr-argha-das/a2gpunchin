# Attendance Kiosk Flutter App

This app runs on one branch phone controlled by the TL/security desk. Employees do not need their own phones.

## Flow

1. Admin creates branch and sets `kiosk_pin`.
2. Admin creates employees under that branch.
3. Admin enrolls each employee face embedding through `POST /api/employees/{employee_id}/face`.
4. TL opens this app before shift time.
5. TL enters backend URL, branch code, and kiosk PIN.
6. Employee taps `Punch In` or `Punch Out`.
7. App captures face, creates embedding, sends it to `/api/kiosk/face-punch`.
8. Backend matches face against employees of that branch and records attendance.

## Face Model

`lib/face_embedding_service.dart` currently contains a deterministic placeholder for API wiring. For production, place a MobileFaceNet/FaceNet TFLite model under `assets/models/` and replace `embeddingFromImageBytes` with real inference. Use the same embedding model for enrollment and punch.

## Run

```bash
flutter pub get
flutter run
```
