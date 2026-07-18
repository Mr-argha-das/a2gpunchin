# Multi-Tenant SaaS GPS Attendance Management System

Production-oriented FastAPI, MongoEngine, Jinja2, Bootstrap, Redis, Celery, MinIO, and Docker implementation for tenant-isolated GPS attendance.

## Features

- Tenant-aware MongoEngine models with soft delete, audit fields, indexes, and automatic visible-query scoping.
- JWT login, refresh token creation, password reset entry point, password change, and RBAC permission checks.
- Super admin-ready company, subscription, branch, department, employee, attendance, leave, and report APIs.
- GPS attendance with browser geolocation, device metadata, browser fingerprint, IP capture, Haversine distance calculation, and geofence rejection.
- Bootstrap admin pages for dashboard, companies, branches, departments, employees, attendance, leave, reports, and settings.
- CSV, Excel, and PDF attendance exports.
- Redis/Celery notification task skeleton, MinIO-ready upload configuration, Docker Compose, and Nginx reverse proxy.

## Run Locally

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app python scripts/seed.py
```

Open:

- Admin UI: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- MinIO Console: `http://localhost:9001`

Seed login:

- Email: `superadmin@example.com`
- Password: `SuperAdmin123!`

## API Pattern

Every primary module supports create, update, delete, detail, list, search, pagination, sorting, and tenant filtering. Use the JWT returned by `/api/auth/login` as a bearer token.

## Project Structure

```text
app/
  api/            FastAPI routers
  core/           config, security, database, dependencies
  middleware/     tenant context and audit logging
  models/         MongoEngine documents
  repositories/   repository pattern
  schemas/        Pydantic request schemas
  services/       business logic
  templates/      Jinja2 Bootstrap pages
  static/         CSS and JavaScript
  utils/          geo, reports, serializers
  tasks/          Celery app and async jobs
```
# a2gpunchin
