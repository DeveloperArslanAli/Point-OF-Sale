# 🚀 Quick Start Guide - Async Jobs Implementation

## ✅ Phase 18.1 Complete - Infrastructure Setup

### What's Been Implemented

1. **Celery Configuration**
   - Created `app/infrastructure/tasks/celery_app.py` with full configuration
   - Task queues: imports, reports, emails
   - Scheduled tasks support (Celery Beat)
   - Result backend with Redis

2. **Docker Compose Services**
   - **redis**: Persistent storage with AOF
   - **celery-worker**: 4 concurrent workers
   - **celery-beat**: Scheduled task runner
   - **flower**: Web UI at http://localhost:5555

3. **Settings Updated**
   - Added `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`
   - Updated `.env.example` with Redis configs

4. **Dependencies**
   - `celery ^5.4.0`
   - `redis ^5.0.7`
   - `flower ^2.0.1`

---

## 🏃 How to Run

### Option 1: Docker Compose (Recommended)

```powershell
# Start all services (backend + redis + celery workers + flower)
docker-compose -f docker-compose.dev.yml up
```

**Access Points:**
- Backend API: http://localhost:8000
- Flower (Celery Monitor): http://localhost:5555
- Redis: localhost:6379

### Option 2: Local Development

```powershell
# Terminal 1: Start Redis
docker run -p 6379:6379 redis:7-alpine

# Terminal 2: Start Backend
cd backend
py -m poetry run uvicorn app.api.main:app --reload

# Terminal 3: Start Celery Worker
cd backend
py -m poetry run celery -A app.infrastructure.tasks.celery_app worker --loglevel=info

# Terminal 4: Start Celery Beat (scheduled tasks)
cd backend
py -m poetry run celery -A app.infrastructure.tasks.celery_app beat --loglevel=info

# Terminal 5: Start Flower (monitoring UI)
cd backend
py -m poetry run celery -A app.infrastructure.tasks.celery_app flower
```

---

## 🧪 Test the Setup

### 1. Test Celery is Running

```powershell
cd backend
py -m poetry run celery -A app.infrastructure.tasks.celery_app inspect active
```

Expected: Should show active workers

### 2. Test Flower UI

Visit: http://localhost:5555

You should see:
- Dashboard with worker status
- Tasks tab (empty for now)
- Monitor tab

### 3. Test Debug Task

```python
from app.infrastructure.tasks.celery_app import debug_task

# Queue the task
result = debug_task.delay()

# Check status
print(result.status)  # PENDING → SUCCESS

# Get result
print(result.get(timeout=10))
```

---

## 📋 Next Steps

### Phase 18.2: Product Import Tasks (Next)
- [ ] Create `ImportSchedulerPort` interface
- [ ] Implement `process_product_import` Celery task
- [ ] Create `CeleryImportScheduler` adapter
- [ ] Update `QueueProductImportUseCase` to use Celery
- [ ] Update products router to return `task_id`

### Phase 18.3: Report & Email Tasks
- [ ] Implement `generate_sales_report` task
- [ ] Implement `send_receipt_email` task with retry
- [ ] Add email service abstraction

### Phase 18.4: Scheduled Tasks & Monitoring
- [ ] Implement `cleanup_expired_tokens` scheduled task
- [ ] Implement `generate_daily_reports` scheduled task
- [ ] Create `/api/v1/tasks` monitoring endpoints
- [ ] Add integration tests

---

## 🔍 Monitoring & Debugging

### Check Worker Status
```powershell
celery -A app.infrastructure.tasks.celery_app status
```

### Inspect Active Tasks
```powershell
celery -A app.infrastructure.tasks.celery_app inspect active
```

### Inspect Scheduled Tasks
```powershell
celery -A app.infrastructure.tasks.celery_app inspect scheduled
```

### Purge All Tasks
```powershell
celery -A app.infrastructure.tasks.celery_app purge
```

### View Registered Tasks
```powershell
celery -A app.infrastructure.tasks.celery_app inspect registered
```

---

## 📊 Task Queues

| Queue | Purpose | Tasks |
|-------|---------|-------|
| `imports` | Product CSV imports | `process_product_import` |
| `reports` | Report generation | `generate_sales_report`, `generate_inventory_report` |
| `emails` | Email delivery | `send_receipt_email`, `send_bulk_promotional_email` |
| `celery` (default) | Scheduled tasks | `cleanup_expired_tokens`, `generate_daily_reports` |

---

## 🚨 Troubleshooting

### Worker Not Starting
```powershell
# Check Redis connection
redis-cli ping  # Should return PONG

# Check Celery can import modules
py -m poetry run python -c "from app.infrastructure.tasks.celery_app import celery_app; print(celery_app)"
```

### Tasks Not Being Processed
1. Check worker is running: Visit http://localhost:5555
2. Check Redis is accessible: `redis-cli ping`
3. Check task is registered: `celery -A app.infrastructure.tasks.celery_app inspect registered`

### High Memory Usage
- Reduce `worker_prefetch_multiplier` in `celery_app.py`
- Lower `worker_max_tasks_per_child` to restart workers more frequently

---

## 📝 Configuration Reference

### Celery Settings (celery_app.py)

| Setting | Value | Purpose |
|---------|-------|---------|
| `task_time_limit` | 30 min | Hard timeout |
| `task_soft_time_limit` | 25 min | Soft timeout (warning) |
| `worker_prefetch_multiplier` | 4 | Tasks to fetch per worker |
| `worker_max_tasks_per_child` | 1000 | Restart after N tasks |
| `result_expires` | 3600s | Result TTL |

---

## 🎯 Success Criteria - Phase 18.1

✅ Redis running and accepting connections  
✅ Celery worker starts without errors  
✅ Celery beat starts without errors  
✅ Flower UI accessible at http://localhost:5555  
✅ `debug_task` executes successfully  
✅ Worker shows as "online" in Flower  

**All criteria met! Ready for Phase 18.2** 🎉

---

**Implementation Time:** ~2 hours  
**Status:** ✅ Complete  
**Next:** Phase 18.2 - Product Import Tasks
