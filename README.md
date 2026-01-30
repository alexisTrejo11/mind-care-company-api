<div align="center">

# 🧠 MindCare Hub API

### _Modern Mental Healthcare Management Platform_

[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.15-ff1709?style=for-the-badge&logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<p align="center">
  <strong>A comprehensive, HIPAA-compliant RESTful API for mental healthcare facilities</strong><br>
  <em>Empowering healthcare providers with modern technology</em>
</p>

[Features](#-features) •
[Architecture](#-architecture) •
[Quick Start](#-quick-start) •
[API Documentation](#-api-documentation) •
[Deployment](#-deployment) •
[Contributing](#-contributing)

---

</div>

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [API Documentation](#-api-documentation)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Security](#-security)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**MindCare Hub API** is a robust, enterprise-grade backend solution designed specifically for mental healthcare facilities. Built with Django REST Framework, this API provides a comprehensive suite of features for managing patients, specialists, appointments, medical records, billing, and notifications.

### Why MindCare Hub?

- 🏥 **Purpose-Built for Mental Health**: Tailored features for psychology, psychiatry, and therapy practices
- 🔒 **Security-First Approach**: HIPAA-compliant architecture with encryption at rest and in transit
- ⚡ **High Performance**: Async task processing, caching, and optimized database queries
- 📱 **Multi-Channel Ready**: Support for web, mobile, and third-party integrations
- 🔄 **Real-Time Capabilities**: WebSocket support for live notifications and updates

---

## ✨ Features

### 👥 User Management

- **Multi-Role Authentication**: Support for patients, specialists, staff, and administrators
- **Email-Based Authentication**: Secure JWT authentication with refresh token rotation
- **Account Activation**: Email verification workflow for new registrations
- **Password Management**: Secure password reset with token-based recovery
- **Profile Management**: Comprehensive user profiles with healthcare-specific fields

### 👨‍⚕️ Specialist Management

- **Professional Profiles**: Detailed specialist profiles with credentials and specializations
- **Specialization Categories**:
  - 🧠 Psychologists
  - 💊 Psychiatrists
  - 🗣️ Therapists
  - 🤝 Counselors
  - 🏥 General Physicians
  - 🥗 Nutritionists
  - 💪 Physiotherapists
  - 🧬 Neurologists
- **Availability Management**: Flexible scheduling with recurring availability patterns
- **Service Catalog**: Customizable services with pricing and duration
- **Rating System**: Patient feedback and specialist ratings

### 📅 Appointment System

- **Smart Scheduling**: Conflict detection and availability validation
- **Appointment Types**:
  - 📋 Initial Consultations
  - 🔄 Follow-up Sessions
  - 💭 Therapy Sessions
  - 🚨 Emergency Appointments
- **Status Tracking**: Complete lifecycle management (scheduled → confirmed → in-progress → completed)
- **Virtual Appointments**: Integrated video conferencing support
- **Automatic Reminders**: Multi-channel appointment notifications

### 📁 Medical Records

- **Confidential Records**: Multi-level confidentiality (Standard, Sensitive, Highly Sensitive)
- **Consultation Notes**: Comprehensive documentation for each appointment
- **Diagnosis & Prescriptions**: Structured medical information storage
- **Treatment Recommendations**: Follow-up scheduling and care plans
- **Audit Trail**: Complete history of record access and modifications

### 💳 Billing & Payments

- **Automated Invoicing**: Automatic bill generation from appointments
- **Stripe Integration**: Secure payment processing with Payment Intents
- **Payment Methods**:
  - 💳 Credit/Debit Cards
  - 🏦 Bank Transfers
  - 💰 Digital Wallets
  - 🏥 Insurance Claims
- **Insurance Processing**: Claim submission and tracking
- **Payment Plans**: Support for partial payments and installments
- **Refund Management**: Automated refund processing

### 🔔 Notification System

- **Multi-Channel Delivery**:
  - 📧 Email (via SendGrid/Mailgun)
  - 📱 SMS (via Twilio)
  - 🔔 Push Notifications
  - 💬 In-App Notifications
- **Template Engine**: Customizable notification templates
- **Smart Scheduling**: Scheduled and triggered notifications
- **Priority Levels**: Urgent, High, Medium, Low
- **Delivery Tracking**: Read receipts and delivery status
- **User Preferences**: Customizable notification settings per user

### 🛡️ Security Features

- **JWT Authentication**: Secure token-based authentication with refresh tokens
- **Rate Limiting**: Configurable rate limits per endpoint
- **Encryption**: Field-level encryption for sensitive data
- **Audit Logging**: Comprehensive activity logging
- **CORS Protection**: Configurable cross-origin policies
- **Input Validation**: Strict validation on all inputs

---

## 🛠️ Technology Stack

### Core Framework

| Technology                | Version | Purpose              |
| ------------------------- | ------- | -------------------- |
| **Django**                | 6.0.1   | Web Framework        |
| **Django REST Framework** | 3.15+   | API Development      |
| **Python**                | 3.13    | Programming Language |

### Database & Caching

| Technology       | Purpose                  |
| ---------------- | ------------------------ |
| **PostgreSQL**   | Primary Database         |
| **Redis**        | Caching & Message Broker |
| **django-redis** | Redis Cache Backend      |

### Authentication & Security

| Technology                        | Purpose                  |
| --------------------------------- | ------------------------ |
| **SimpleJWT**                     | JWT Token Authentication |
| **django-guardian**               | Object-Level Permissions |
| **django-axes**                   | Brute Force Protection   |
| **django-encrypted-model-fields** | Field Encryption         |
| **django-ratelimit**              | Rate Limiting            |

### Task Processing

| Technology                | Purpose             |
| ------------------------- | ------------------- |
| **Celery**                | Async Task Queue    |
| **Celery Beat**           | Periodic Tasks      |
| **django-celery-results** | Task Result Backend |

### Communication

| Technology          | Purpose           |
| ------------------- | ----------------- |
| **Django Channels** | WebSockets        |
| **Twilio**          | SMS Notifications |
| **django-anymail**  | Email Delivery    |

### Payments

| Technology | Purpose            |
| ---------- | ------------------ |
| **Stripe** | Payment Processing |

### Documentation & Quality

| Technology              | Purpose                       |
| ----------------------- | ----------------------------- |
| **drf-spectacular**     | OpenAPI/Swagger Documentation |
| **Sentry**              | Error Monitoring              |
| **django-health-check** | Health Monitoring             |
| **django-auditlog**     | Audit Trail                   |

### Production

| Technology     | Purpose          |
| -------------- | ---------------- |
| **Gunicorn**   | WSGI Server      |
| **Daphne**     | ASGI Server      |
| **WhiteNoise** | Static Files     |
| **Docker**     | Containerization |

---

## 🏗️ Architecture

### Design Patterns

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MindCare Hub Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Client    │───▶│   Nginx     │───▶│   Django    │───▶│  PostgreSQL │  │
│  │  (Web/App)  │    │  (Reverse   │    │   (DRF)     │    │  (Database) │  │
│  └─────────────┘    │   Proxy)    │    └──────┬──────┘    └─────────────┘  │
│                     └─────────────┘           │                             │
│                                               │                             │
│                     ┌─────────────┐    ┌──────▼──────┐    ┌─────────────┐  │
│                     │   Stripe    │◀───│   Celery    │───▶│    Redis    │  │
│                     │  (Payments) │    │  (Workers)  │    │   (Cache)   │  │
│                     └─────────────┘    └──────┬──────┘    └─────────────┘  │
│                                               │                             │
│                     ┌─────────────┐    ┌──────▼──────┐                      │
│                     │   Twilio    │◀───│   Celery    │                      │
│                     │    (SMS)    │    │   (Beat)    │                      │
│                     └─────────────┘    └─────────────┘                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Presentation Layer                         │
│         (Views, Serializers, API Endpoints)                     │
├────────────────────────────────────────────────────────────────┤
│                       Service Layer                             │
│     (Business Logic, Validations, External Integrations)        │
├────────────────────────────────────────────────────────────────┤
│                         Core Layer                              │
│    (Exceptions, Responses, Decorators, Shared Utilities)        │
├────────────────────────────────────────────────────────────────┤
│                         Data Layer                              │
│          (Models, Migrations, Database Queries)                 │
└────────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

| Pattern                | Implementation                      | Purpose                    |
| ---------------------- | ----------------------------------- | -------------------------- |
| **Service Layer**      | `apps/*/services/`                  | Encapsulate business logic |
| **Repository Pattern** | Django ORM + Custom Managers        | Data access abstraction    |
| **Factory Pattern**    | Notification factories              | Object creation            |
| **Decorator Pattern**  | `@api_error_handler`, `@rate_limit` | Cross-cutting concerns     |
| **Strategy Pattern**   | Payment processors                  | Interchangeable algorithms |
| **Observer Pattern**   | Django signals + Celery             | Event-driven architecture  |
| **Singleton Pattern**  | Service classes                     | Single instance services   |

---

## 📁 Project Structure

```
mind_care_hub_api/
│
├── 📂 apps/                          # Application modules
│   ├── 📂 users/                     # User management
│   │   ├── 📂 views/
│   │   │   ├── auth_views.py         # Login, Logout
│   │   │   ├── registration_views.py # User registration
│   │   │   ├── activation_views.py   # Email activation
│   │   │   ├── password_views.py     # Password reset
│   │   │   └── profile_views.py      # Profile management
│   │   ├── 📂 services/
│   │   │   └── user_service.py       # User business logic
│   │   ├── models.py                 # User model
│   │   ├── serializers.py            # API serializers
│   │   └── tasks.py                  # Celery tasks
│   │
│   ├── 📂 specialists/               # Healthcare specialists
│   │   ├── 📂 views/
│   │   │   ├── specialist_profile_views.py
│   │   │   ├── specialists_views.py
│   │   │   ├── clinic_services_views.py
│   │   │   └── specialists_disponibility_views.py
│   │   ├── 📂 services/
│   │   ├── models.py                 # Specialist, Service, Availability
│   │   ├── serializers.py
│   │   └── validators.py
│   │
│   ├── 📂 appointments/              # Appointment scheduling
│   │   ├── 📂 services/
│   │   │   ├── appointment_service.py
│   │   │   └── availability_checker.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   └── validators.py
│   │
│   ├── 📂 medical/                   # Medical records
│   │   ├── 📂 services/
│   │   ├── models.py                 # MedicalRecord
│   │   ├── serializers.py
│   │   └── validators.py
│   │
│   ├── 📂 billing/                   # Billing & payments
│   │   ├── 📂 services/
│   │   │   ├── billing_service.py
│   │   │   └── stripe_service.py     # Stripe integration
│   │   ├── models.py                 # Bill, Payment, Refund
│   │   ├── serializers.py
│   │   └── tasks.py                  # Payment processing tasks
│   │
│   └── 📂 notification/              # Notification system
│       ├── 📂 services/
│       ├── 📂 templates/
│       │   ├── 📂 email/             # Email templates
│       │   └── 📂 sms/               # SMS templates
│       ├── models.py                 # Notification, Template, Preferences
│       ├── serializers.py
│       ├── tasks.py                  # Async notification delivery
│       └── utils.py
│
├── 📂 config/                        # Project configuration
│   ├── settings.py                   # Django settings
│   ├── urls.py                       # Root URL configuration
│   ├── wsgi.py                       # WSGI config
│   └── asgi.py                       # ASGI config (WebSockets)
│
├── 📂 core/                          # Shared utilities
│   ├── 📂 decorators/
│   │   ├── error_handler.py          # @api_error_handler
│   │   ├── permissions.py            # Custom permission decorators
│   │   └── rate_limit.py             # @rate_limit
│   ├── 📂 exceptions/
│   │   ├── base_exceptions.py        # Custom exception classes
│   │   ├── error_codes.py            # Error code constants
│   │   └── handlers.py               # Global exception handler
│   ├── 📂 responses/
│   │   └── api_response.py           # Standardized API responses
│   └── shared.py                     # Utility functions
│
├── 📂 logs/                          # Application logs
│   ├── errors.log                    # Error logs
│   └── audit.log                     # Audit trail
│
├── 📜 manage.py                      # Django CLI
├── 📜 requirements.txt               # Python dependencies
├── 🐳 Dockerfile                     # Docker image
├── 🐳 docker-compose.yml             # Docker orchestration
└── 📜 README.md                      # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional)

### Option 1: Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/mind_care_hub_api.git
cd mind_care_hub_api

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Option 2: Docker Deployment

```bash
# Clone the repository
git clone https://github.com/yourusername/mind_care_hub_api.git
cd mind_care_hub_api

# Build and start containers
docker-compose up -d --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f
```

---

## ⚙️ Environment Variables

Create a `.env` file in the project root:

```env
# =============================================================================
# DJANGO SETTINGS
# =============================================================================
DEBUG=False
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL=postgres://user:password@localhost:5432/mindcare_db
DB_NAME=mindcare_db
DB_USER=mindcare_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# =============================================================================
# REDIS & CELERY
# =============================================================================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# =============================================================================
# JWT AUTHENTICATION
# =============================================================================
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_LIFETIME=15  # minutes
JWT_REFRESH_TOKEN_LIFETIME=7  # days

# =============================================================================
# EMAIL SERVICE
# =============================================================================
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@mindcarehub.com

# =============================================================================
# TWILIO (SMS)
# =============================================================================
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# =============================================================================
# STRIPE (PAYMENTS)
# =============================================================================
STRIPE_PUBLIC_KEY=pk_live_xxxxxxxxxxxx
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# =============================================================================
# AWS S3 (FILE STORAGE)
# =============================================================================
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=mindcare-files
AWS_S3_REGION_NAME=us-east-1

# =============================================================================
# SENTRY (ERROR MONITORING)
# =============================================================================
SENTRY_DSN=https://xxxx@sentry.io/xxxx

# =============================================================================
# ENCRYPTION
# =============================================================================
FIELD_ENCRYPTION_KEY=your-field-encryption-key
```

---

## 📚 API Documentation

### Base URL

```
https://api.mindcarehub.com/api/v1/
```

### Authentication

All protected endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Response Format

All API responses follow a consistent format:

#### Success Response

```json
{
  "status": "success",
  "message": "Operation successful",
  "timestamp": "2026-01-30T10:00:00Z",
  "data": { ... },
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

#### Error Response

```json
{
  "status": "error",
  "message": "Validation failed",
  "timestamp": "2026-01-30T10:00:00Z",
  "code": "validation_error",
  "errors": [
    {
      "field": "email",
      "message": "This field is required"
    }
  ]
}
```

### API Endpoints Overview

#### 🔐 Authentication

| Method | Endpoint                      | Description                |
| ------ | ----------------------------- | -------------------------- |
| `POST` | `/api/auth/register/`         | Register new user          |
| `POST` | `/api/auth/login/`            | Login and get tokens       |
| `POST` | `/api/auth/logout/`           | Logout and blacklist token |
| `POST` | `/api/auth/refresh/`          | Refresh access token       |
| `POST` | `/api/auth/activate/`         | Activate account           |
| `POST` | `/api/auth/password/reset/`   | Request password reset     |
| `POST` | `/api/auth/password/confirm/` | Confirm password reset     |

#### 👤 Users

| Method  | Endpoint           | Description                 |
| ------- | ------------------ | --------------------------- |
| `GET`   | `/api/users/me/`   | Get current user profile    |
| `PATCH` | `/api/users/me/`   | Update current user profile |
| `GET`   | `/api/users/{id}/` | Get user by ID (admin)      |

#### 👨‍⚕️ Specialists

| Method | Endpoint                              | Description                 |
| ------ | ------------------------------------- | --------------------------- |
| `GET`  | `/api/specialists/`                   | List all specialists        |
| `GET`  | `/api/specialists/{id}/`              | Get specialist details      |
| `GET`  | `/api/specialists/{id}/availability/` | Get specialist availability |
| `GET`  | `/api/specialists/{id}/services/`     | Get specialist services     |
| `POST` | `/api/specialists/{id}/reviews/`      | Submit review               |

#### 📅 Appointments

| Method  | Endpoint                          | Description             |
| ------- | --------------------------------- | ----------------------- |
| `GET`   | `/api/appointments/`              | List user appointments  |
| `POST`  | `/api/appointments/`              | Create new appointment  |
| `GET`   | `/api/appointments/{id}/`         | Get appointment details |
| `PATCH` | `/api/appointments/{id}/`         | Update appointment      |
| `POST`  | `/api/appointments/{id}/cancel/`  | Cancel appointment      |
| `POST`  | `/api/appointments/{id}/confirm/` | Confirm appointment     |

#### 📁 Medical Records

| Method  | Endpoint                     | Description           |
| ------- | ---------------------------- | --------------------- |
| `GET`   | `/api/medical/records/`      | List medical records  |
| `POST`  | `/api/medical/records/`      | Create medical record |
| `GET`   | `/api/medical/records/{id}/` | Get record details    |
| `PATCH` | `/api/medical/records/{id}/` | Update record         |

#### 💳 Billing

| Method | Endpoint                             | Description      |
| ------ | ------------------------------------ | ---------------- |
| `GET`  | `/api/billing/bills/`                | List user bills  |
| `GET`  | `/api/billing/bills/{id}/`           | Get bill details |
| `POST` | `/api/billing/bills/{id}/pay/`       | Process payment  |
| `GET`  | `/api/billing/payments/`             | List payments    |
| `POST` | `/api/billing/payments/{id}/refund/` | Request refund   |

#### 🔔 Notifications

| Method  | Endpoint                          | Description        |
| ------- | --------------------------------- | ------------------ |
| `GET`   | `/api/notifications/`             | List notifications |
| `PATCH` | `/api/notifications/{id}/read/`   | Mark as read       |
| `GET`   | `/api/notifications/preferences/` | Get preferences    |
| `PATCH` | `/api/notifications/preferences/` | Update preferences |

### Interactive Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: `https://api.mindcarehub.com/api/docs/`
- **ReDoc**: `https://api.mindcarehub.com/api/redoc/`
- **OpenAPI Schema**: `https://api.mindcarehub.com/api/schema/`

---

## 🐳 Deployment

### Docker Production Deployment

#### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "config.wsgi:application"]
```

#### Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  web:
    build: .
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - DATABASE_URL=postgres://mindcare:password@db:5432/mindcare_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/mediafiles

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      - POSTGRES_DB=mindcare_db
      - POSTGRES_USER=mindcare
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data

  celery:
    build: .
    restart: always
    command: celery -A config worker -l info
    environment:
      - DATABASE_URL=postgres://mindcare:password@db:5432/mindcare_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    restart: always
    command: celery -A config beat -l info
    environment:
      - DATABASE_URL=postgres://mindcare:password@db:5432/mindcare_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/staticfiles:ro
      - media_volume:/app/mediafiles:ro
    depends_on:
      - web

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

### Cloud Deployment Options

| Platform                      | Status       | Notes                      |
| ----------------------------- | ------------ | -------------------------- |
| **AWS ECS**                   | ✅ Supported | Recommended for production |
| **Google Cloud Run**          | ✅ Supported | Auto-scaling               |
| **Azure Container Apps**      | ✅ Supported | Easy Azure integration     |
| **Heroku**                    | ✅ Supported | Quick deployment           |
| **DigitalOcean App Platform** | ✅ Supported | Cost-effective             |
| **Kubernetes**                | ✅ Supported | Enterprise scale           |

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific app tests
pytest apps/users/tests.py -v

# Run with parallel execution
pytest -n auto

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Test Structure

```
tests/
├── conftest.py                 # Pytest fixtures
├── factories/                  # Model factories
│   ├── user_factory.py
│   ├── specialist_factory.py
│   └── appointment_factory.py
├── unit/                       # Unit tests
│   ├── test_services/
│   ├── test_validators/
│   └── test_models/
└── integration/                # Integration tests
    ├── test_api/
    └── test_workflows/
```

### Test Coverage Goals

| Module      | Target Coverage |
| ----------- | --------------- |
| Core        | 90%+            |
| Services    | 85%+            |
| Views       | 80%+            |
| Models      | 95%+            |
| **Overall** | **85%+**        |

---

## 🔒 Security

### Security Measures

| Feature              | Implementation                        |
| -------------------- | ------------------------------------- |
| **Authentication**   | JWT with refresh token rotation       |
| **Authorization**    | Role-based + Object-level permissions |
| **Encryption**       | AES-256 for sensitive fields          |
| **Rate Limiting**    | Per-endpoint configurable limits      |
| **Input Validation** | Strict serializer validation          |
| **SQL Injection**    | Django ORM parameterized queries      |
| **XSS Protection**   | Django auto-escaping                  |
| **CSRF Protection**  | Django CSRF middleware                |
| **Brute Force**      | django-axes lockout                   |
| **Audit Logging**    | All sensitive operations logged       |

### HIPAA Compliance

This API is designed with HIPAA compliance in mind:

- ✅ Access controls and authentication
- ✅ Audit controls and logging
- ✅ Transmission security (TLS/SSL)
- ✅ Encryption at rest
- ✅ Automatic logoff
- ✅ Unique user identification

### Reporting Security Issues

If you discover a security vulnerability, please send an email to security@mindcarehub.com instead of using the issue tracker.

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Style

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Lint with flake8
flake8 .
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Django](https://www.djangoproject.com/) - The web framework for perfectionists
- [Django REST Framework](https://www.django-rest-framework.org/) - Powerful API toolkit
- [Stripe](https://stripe.com/) - Payment processing
- [Twilio](https://www.twilio.com/) - Communication APIs
- All our amazing contributors!

---

<div align="center">

**Made with ❤️ for Mental Healthcare**

[⬆ Back to Top](#-mindcare-hub-api)

</div>
]]>
