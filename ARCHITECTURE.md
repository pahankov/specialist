# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React + Vite)                    │
│     React 18 + TypeScript + Responsive Design               │
│  - Master & Service listing                                 │
│  - Booking form (client name, phone, date, service)         │
└────────────────────────┬────────────────────────────────────┘
                          │ REST API (axios)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│   Async ORM (SQLAlchemy) + Pydantic validation              │
│   SQLite (dev) / PostgreSQL (production)                    │
└────────────────────────┬────────────────────────────────────┘
                          │
      ┌───────────────────┼───────────────────┐
      │                   │                   │
      ▼                   ▼                   ▼
┌─────────┐         ┌─────────┐         ┌─────────┐
│ Masters │         │Services │         │Appointm.│
│ Clients │         │         │         │WorkingHrs│
└─────────┘         └─────────┘         └─────────┘
      │                   │                   │
      └───────────────────┼───────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │    Data Access Layer (ORM)      │
        │    SQLAlchemy 2.0 (async)       │
        └─────────────────────────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │  SQLite     │
                    │ (dev/prod)  │
                    └─────────────┘
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.115
- **ORM**: SQLAlchemy 2.0 (async, aiosqlite)
- **Database**: SQLite (development), PostgreSQL 16 (production via Docker)
- **Authentication**: JWT (python-jose + bcrypt)
- **Validation**: Pydantic 2.0
- **Testing**: pytest + pytest-asyncio + httpx

### Frontend
- **Library**: React 18.3
- **Language**: TypeScript 5.7
- **Build Tool**: Vite 6
- **HTTP Client**: Axios 1.7
- **Routing**: React Router 6.28
- **Date Handling**: date-fns 4.1

### DevOps
- **Containerization**: Docker + Docker Compose
- **Web Server**: Uvicorn (backend), Vite (frontend dev)

## Data Models

### Core Entities

```
Master (id, name, email, phone, telegram_username, hashed_password, ...)
  ├─ 1:N ──> Service (id, master_id, name, description, duration_minutes, price)
  │           └─ 1:N ──> Appointment
  ├─ 1:N ──> Appointment (id, master_id, service_id, client_id, appointment_date, status, notes)
  ├─ 1:N ──> WorkingHour (id, master_id, day_of_week, start_time, end_time)
  └─ 1:N ──> Client (via appointment)

Client (id, name, phone, email, created_at)
  └─ 1:N ──> Appointment
```

### Appointment Statuses
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

## API Versioning

- Current: `/api/v1/`
- All endpoints use REST conventions
- All responses include proper HTTP status codes
- Error responses use consistent format

## Security

1. **Password**: Bcrypt hashing (passlib)
2. **Authentication**: JWT tokens (python-jose, HS256)
3. **Input Validation**: Pydantic schemas with type checking
4. **CORS**: Configured in FastAPI (currently permissive for dev)
5. **SQL Injection**: Protected by SQLAlchemy ORM

## Scalability Path

### Phase 1 (Current MVP)
- Single master
- SQLite database
- Web-based booking

### Phase 2 (Multi-Master)
- Master authentication (already implemented)
- Admin dashboard for each master
- PostgreSQL migration
- Alembic migrations

### Phase 3 (Advanced)
- Messenger integration (Telegram Bot, VK Mini App)
- Notification system (email, push)
- Analytics & reporting
- Payment integration

## Performance

1. **Async/Await**: All DB operations are non-blocking
2. **Connection Pooling**: Built into aiosqlite / asyncpg
3. **Indexes**: On foreign keys and frequently queried fields
4. **Pagination**: To be implemented for large datasets

## Monitoring

- FastAPI logs all requests
- Health check endpoint: `/health`
- Swagger UI auto-generated docs: `/docs`
