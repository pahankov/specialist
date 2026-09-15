# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Messenger Channels                        │
│            (Telegram, VK, MAX - WebView)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (PWA)                             │
│     React + TypeScript + Responsive Design                  │
│  - Service Selection                                        │
│  - Calendar & Slot Booking                                  │
│  - Client Data Form                                         │
│  - Appointment Status                                       │
│  - Review Submission                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           │   REST API (FastAPI)      │
           │   OpenAPI Documentation   │
           │   CORS Enabled            │
           └─────────────┬─────────────┘
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
     ▼                   ▼                   ▼
┌─────────┐         ┌─────────┐         ┌─────────┐
│ Masters │         │Services │         │Appointm.│
│ Routes  │         │ Routes  │         │ Routes  │
└────┬────┘         └────┬────┘         └────┬────┘
     │                   │                   │
     └───────────────────┼───────────────────┘
                         │
                         ▼
       ┌─────────────────────────────────┐
       │   Business Logic Layer          │
       │  - Slot Availability Check      │
       │  - Appointment Validation       │
       │  - Notification Scheduling      │
       │  - Review Management            │
       └─────────────────────────────────┘
                         │
                         ▼
       ┌─────────────────────────────────┐
       │    Data Access Layer (ORM)      │
       │    SQLAlchemy (Async)           │
       └─────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
   ┌─────────────┐              ┌──────────────┐
   │ PostgreSQL  │              │   Redis      │
   │  (Relational)              │  (Cache/Q)   │
   │             │              │              │
   │ - Masters   │              │ - Sessions   │
   │ - Services  │              │ - Queued     │
   │ - Appt.     │              │   Tasks      │
   │ - Reviews   │              │ - Notif.     │
   │ - Hours     │              │   Buffer     │
   │ - Blocks    │              │              │
   └─────────────┘              └──────────────┘
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.115
- **ORM**: SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)
- **Validation**: Pydantic 2.0

### Frontend
- **Library**: React 18.3
- **Language**: TypeScript 5.7
- **Build Tool**: Vite 6
- **HTTP Client**: Axios 1.7
- **Routing**: React Router 6.28
- **Date Handling**: date-fns 4.1

### DevOps
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Web Server**: Uvicorn (backend), Vite (frontend dev)

## Data Models

### Core Entities

```
Master (id, name, phone, email, ...)
  ├─ 1:N ──> Service (id, master_id, name, duration, price)
  │           └─ 1:N ──> Appointment
  │                       └─ 1:1 ──> Review
  │                       └─ 1:N ──> ChatMessage
  ├─ 1:N ──> Appointment (id, master_id, service_id, client_name, ...)
  ├─ 1:N ──> WorkingHour (id, master_id, day_of_week, start_time, end_time)
  ├─ 1:N ──> BlockedSlot (id, master_id, start_dt, end_dt, reason)
  └─ 1:N ──> Review (via appointment)
```

## API Versioning

- Current: `/api/v1/`
- All endpoints use REST conventions
- All responses include proper HTTP status codes
- Error responses use consistent format

## Security Considerations

1. **Database**: Parameterized queries (SQLAlchemy ORM)
2. **Input Validation**: Pydantic schemas with type checking
3. **CORS**: Configured in FastAPI (modify for production)
4. **Password**: Bcrypt hashing with salt
5. **Authentication**: JWT tokens for future master login
6. **Rate Limiting**: To be added (Redis-based)
7. **SQL Injection**: Protected by ORM

## Scalability Path

### Phase 1 (Current MVP)
- Single master
- PostgreSQL + Redis
- Docker deployment

### Phase 2 (Multi-Master)
- Add master authentication
- Admin dashboard
- Multi-tenant support
- Stripe/Yandex.Kassa integration

### Phase 3 (Advanced)
- Microservices (if needed)
- Message queue (Celery + RabbitMQ)
- Analytics service
- Mobile native apps
- SMS/Push notifications

## Performance Optimizations

1. **Async/Await**: All DB operations are non-blocking
2. **Connection Pooling**: Built into asyncpg
3. **Caching**: Redis for session & frequent queries
4. **Indexes**: PostgreSQL indexes on foreign keys
5. **Pagination**: Implement for large datasets (future)

## Monitoring & Logging

- FastAPI logs all requests
- PostgreSQL query logging (when debug=true)
- Error tracking (to be added: Sentry)
- Health check endpoint: `/health`
