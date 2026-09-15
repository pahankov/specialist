# Changelog

## [0.3.0] - 2026-09-15

### ✨ Added

#### Testing
- **pytest test suite** — 18 passing tests
  - 8 auth tests: register success/missing/duplicate, login success/wrong password/nonexistent
  - 10 masters tests: CRUD (GET list, GET by ID, POST, PATCH, DELETE)
- **Test infrastructure**
  - In-memory SQLite for isolated test database
  - pytest-asyncio for async test support
  - httpx ASGITransport for FastAPI test client
  - Fixtures: `client`, `session`, `engine`, `auth_token`, `test_master_data`
  - `pyproject.toml` with pytest and coverage configuration

#### Backend
- **Masters CRUD endpoints** (PATCH, DELETE added)
  - `PATCH /api/v1/masters/{id}` — update master
  - `DELETE /api/v1/masters/{id}` — delete master
- **Schema fixes**
  - `ServiceResponse.price` changed to `Decimal` for correct Numeric mapping
  - Added `description` column to `services` table

### 🔄 Changed

- **Documentation updated** — all markdown files refreshed to match current state
  - Removed references to non-existent features (reviews, blocked_slots, notifications)
  - Updated tech stack (SQLite for dev, not just PostgreSQL)
  - Added test section to README and QUICK_START
  - Accurate file counts and code statistics
- **`.gitignore` updated** — added `venv/`, `sugar_booking.db`, test artifacts

### 📚 Documentation
- `README.md` — complete rewrite with accurate structure, API table, test commands
- `QUICK_START.md` — updated with real API examples, test commands, troubleshooting
- `ARCHITECTURE.md` — simplified diagram matching actual implementation
- `SETUP.md` — removed Docker-only instructions, added local setup
- `PROJECT_STATUS.md` — accurate status with test results
- `API_EXAMPLES.md` — added auth, masters CRUD, updated all examples
- `CHANGELOG.md` — this file

---

## [0.2.0] - 2026-09-09

### ✨ Added
- Master registration and authentication (JWT)
- Client management (automatic creation on booking)
- Slot availability calculation (available-days, available-slots)
- Public booking endpoint (no auth required)
- Appointment statuses: pending, confirmed, cancelled, completed
- Telegram/VK/MAX API tokens in config (placeholders)

### 🔄 Changed
- SQLite for local development (replaced PostgreSQL-only)
- All routes use async sessions

---

## [0.1.0] - 2026-09-09 (Initial)

### ✨ Added
- Full project architecture (backend + frontend)
- 5 core data models (Master, Service, Appointment, Client, WorkingHour)
- 6 API routers
- React + TypeScript frontend with Vite
- Docker Compose configuration
- Project documentation

---

## 🚀 Next: v0.4.0 — Admin Panel

1. Master login UI on frontend
2. Admin dashboard (appointments, stats)
3. Appointment management (confirm, cancel, edit)
4. Service management UI
5. Schedule management UI

---

## 📊 Code Statistics

| Component | Lines | Files |
|-----------|-------|-------|
| Backend models | ~200 | 5 |
| Backend schemas | ~200 | 5 |
| Backend routes | ~500 | 6 |
| Frontend pages | ~400 | 4 |
| Frontend API | ~80 | 2 |
| Frontend styles | ~250 | 4 |
| Tests | ~300 | 3 |
| **Total** | **~1930** | **~65** |
