# Production Deployment Guide

## 1. Server Setup

Provision an Ubuntu server with Docker, Docker Compose, and a firewall that allows ports `80`, `443`, and SSH. Create a deployment user, clone this repository, and copy `.env.example` to `.env`.

## 2. Environment

Set a strong `SECRET_KEY`, production MongoDB URI if using a managed database, Redis URL, MinIO credentials, SMTP settings, and WhatsApp provider credentials. Keep `.env` out of source control.

## 3. Start Services

```bash
docker compose up -d --build
docker compose exec app python scripts/seed.py
```

The API is available at `/docs`, and the admin UI is available at `/`.

## 4. SSL

Use Certbot on the host or terminate TLS at a load balancer. If terminating in Nginx, mount certificates under `nginx/certs`, update `nginx/default.conf` to listen on `443 ssl`, and redirect port `80` to HTTPS.

## 5. Multi-Tenant Operation

All tenant-scoped collections include `tenant_id`, `company_id`, `created_by`, `created_at`, `updated_at`, and `is_active`. API requests are scoped by JWT claims or `X-Tenant-ID` and `X-Company-ID` headers. Super admins can manage companies and subscriptions across the platform.

## 6. Scaling Notes

Run multiple `app` and `worker` replicas behind Nginx or a cloud load balancer. Add MongoDB indexes before importing large data sets, use managed MongoDB with replica sets, and isolate high-volume reporting into scheduled exports when attendance volume grows beyond interactive query thresholds.

## 7. Backups

Schedule MongoDB dumps, MinIO bucket replication, and encrypted offsite storage. Test restore procedures before launch.

## 8. Monitoring

Ship application logs, Nginx logs, MongoDB metrics, Redis metrics, and Celery worker events to your monitoring platform. Alert on expired subscriptions, high attendance rejection rates, and failed notification tasks.
