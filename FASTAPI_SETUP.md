# GoalServe Sports Betting Platform - FastAPI Edition

This is the **FastAPI + Docker Compose** version of the platform, designed to run both **locally** and **on Fly.io** without code forks.

## 🚀 Quick Start

### 1. Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ (for local development without Docker)

### 2. Start Local Development Environment
```bash
# Copy environment file
cp env.example .env

# Start all services (PostgreSQL, Redis, Backend, Worker)
./scripts/dev.sh
```

This will start:
- **Backend API** at `http://127.0.0.1:8000`
- **PostgreSQL** at `localhost:5432`
- **Redis** at `localhost:6379`
- **Settlement Worker** in background

### 3. Access the Application
- **Main App**: http://127.00.1:8000
- **Login**: http://127.0.0.1:8000/login
- **Register Sportsbook**: http://127.0.0.1:8000/register-sportsbook
- **Admin**: http://127.0.0.1:8000/admin-login

## 🔧 Configuration

### Environment Variables
The `.env` file controls all configuration:

```bash
# Server
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sportsbook

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS & Socket.IO
CORS_ORIGINS=["http://localhost:5000","http://127.0.0.1:8000"]
SOCKET_ALLOWED_ORIGINS=["http://localhost:5000","http://127.0.0.1:8000"]

# Goalserve API
GOALSERVE_API_KEY=your-api-key
USE_MOCK_FEED=false  # Set to true for local development without API calls
```

### Frontend Configuration
If your frontend runs on a different port (e.g., Vite on :5000), update these environment variables:

```bash
# In your frontend .env
VITE_API_BASE=http://127.0.0.1:8000
VITE_SOCKET_URL=ws://127.0.0.1:8000/socket.io/
```

## 🐳 Docker Commands

### Start Services
```bash
docker compose up -d
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f worker
```

### Stop Services
```bash
docker compose down
```

### Rebuild and Restart
```bash
docker compose up --build -d
```

## 🚀 Deployment to Fly.io

### 1. Update fly.toml
```toml
app = "your-app-name"
primary_region = "iad"  # Change to your preferred region
```

### 2. Set Secrets
```bash
fly secrets set DATABASE_URL="your-postgres-url"
fly secrets set REDIS_URL="your-redis-url"
fly secrets set GOALSERVE_API_KEY="your-api-key"
fly secrets set CORS_ORIGINS='["https://your-frontend.example","https://yourapp.fly.dev"]'
```

### 3. Deploy
```bash
fly deploy
```

## 📁 Project Structure

```
├── src/
│   ├── main_fastapi.py      # FastAPI main application
│   ├── settings.py          # Pydantic settings
│   ├── worker.py            # Settlement worker
│   ├── routes/              # API routes
│   ├── models/              # Database models
│   └── static/              # Static files
├── docker-compose.yml       # Local development stack
├── Dockerfile.local         # Local development Dockerfile
├── fly.toml                 # Fly.io configuration
├── env.example              # Environment template
├── requirements.txt         # Python dependencies
└── scripts/
    ├── dev.sh              # Start local environment
    └── migrate.sh          # Run database migrations
```

## 🔄 Database Migrations

### Local Development
```bash
# Start services first
./scripts/dev.sh

# Run migrations
./scripts/migrate.sh
```

### Production (Fly.io)
```bash
# Run migrations on Fly.io
fly ssh console -C "python -m alembic upgrade head"
```

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest
```

### Mock Feeds
For local development without hitting the Goalserve API:

1. Set `USE_MOCK_FEED=true` in `.env`
2. Place mock JSON/XML files in `mock_feeds/` directory
3. Files should match the expected Goalserve API response format

## 🐛 Troubleshooting

### Common Issues

**Port 8000 already in use:**
```bash
# Change port in .env
PORT=8001
```

**Database connection failed:**
```bash
# Check if PostgreSQL is running
docker compose ps postgres

# View database logs
docker compose logs postgres
```

**WebSocket connection failed:**
- Ensure CORS origins are correctly configured
- Check if the backend service is healthy: `curl http://127.0.0.1:8000/health`

### Health Checks
- **Backend**: http://127.0.0.1:8000/health
- **WebSocket**: http://127.0.0.1:8000/ws-health

## 🔮 Future Enhancements

- [ ] Add Redis caching for API responses
- [ ] Implement rate limiting
- [ ] Add monitoring and metrics
- [ ] Support for multiple database backends
- [ ] Automated testing pipeline

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Fly.io Documentation](https://fly.io/docs/)
- [Socket.IO Python Documentation](https://python-socketio.readthedocs.io/)

---

**Note**: This FastAPI version is designed to be a drop-in replacement for the Flask version, with improved performance, better async support, and easier deployment to modern platforms.
