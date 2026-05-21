# Demo Blog Site

A full-featured blog platform built with Python Flask backend and AngularJS frontend.

## Quick Start with Docker

1. Clone the repository and set up environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. Build and start containers:
```bash
docker-compose up --build
```

3. Initialize database (first time only):
```bash
docker-compose exec web flask db init
docker-compose exec web flask db migrate -m "Initial migration"
docker-compose exec web flask db upgrade
```

4. Access the application:
- Web app: http://localhost:8080
- PostgreSQL: localhost:5432

## Features

- User authentication (signup, login)
- Post management (create, view, edit, delete)
- Threaded comment system
- Tag system with search
- User following
- Direct messaging
- Saved posts
- Favorite tags
- Personalized feed

## Technology Stack

- **Backend**: Flask, SQLAlchemy, PostgreSQL
- **Frontend**: AngularJS, Jinja2
- **Containerization**: Docker, Docker Compose

## API Documentation

See `PROJECT.md` for complete API documentation and project specifications.

## Development

Stop containers:
```bash
docker-compose down
```

Reset database:
```bash
docker-compose down -v
```

View logs:
```bash
docker-compose logs -f web
```

## License

MIT
