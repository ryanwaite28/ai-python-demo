# Demo Blog Site - Project Documentation

## Project Overview

A full-featured blog platform built with Python Flask backend and static HTML frontend, enabling users to create, share, and discover content through posts, tags, and social interactions.

## Technology Stack

### Backend
- **Framework**: Flask
- **ORM**: SQLAlchemy
- **Database**: PostgreSQL (via Docker container)
- **Authentication**: Flask-Login
- **Password Hashing**: Werkzeug Security
- **Migrations**: Flask-Migrate
- **Environment Management**: python-dotenv
- **Containerization**: Docker & Docker Compose

### Frontend
- **Templates**: Jinja2 (Flask templating for initial page load)
- **Framework**: AngularJS (1.x) - Loaded from Google CDN (v1.8.2)
- **Styling**: CSS (static files)
- **API Communication**: Fetch API and AJAX (no traditional form submissions)
- **Data Format**: JSON for all API requests/responses

**Important**: AngularJS and Jinja2 both use `{{` and `}}` for interpolation. Configure AngularJS to use `((` and `))` instead to avoid conflicts:
```javascript
angular.module('blogApp', []).config(function($interpolateProvider) {
  $interpolateProvider.startSymbol('((');
  $interpolateProvider.endSymbol('))');
});
```

**Architecture**: The application follows a clear separation:
- **View Routes**: Serve HTML templates (e.g., `/`, `/posts`, `/login`)
- **API Routes**: Handle data operations via JSON (prefixed with `/api`)
- **Frontend**: Uses fetch API/AJAX to communicate with API endpoints

### Navigation & View Access

**Public Views** (accessible without authentication):
- `/` - Welcome/landing page
- `/posts` - Browse all posts
- `/posts/<id>` - View individual post and replies
- `/users/<username>` - View user profile
- `/tags` - Browse tags
- `/search` - Search posts by tags
- `/login` - Login page
- `/signup` - Signup page

**Private Views** (require authentication):
- `/home/<user_id>` - User's personalized home/dashboard (displays user ID, validates user_id matches authenticated user)
- `/feed` - Personalized feed based on favorited tags
- `/messages` - User's inbox
- `/messages/compose` - Compose new message
- `/posts/create` - Create new post
- `/posts/<id>/edit` - Edit own post
- `/settings` - User settings/profile management

**Navigation Bar**:
- **When Logged Out**: Shows "Home", "Posts", "Tags", "Search", "Login", "Sign Up" buttons
- **When Logged In**: Shows "Home", "Feed", "Posts", "Tags", "Messages", "Create Post", user avatar/dropdown with "Settings" and "Logout" options

## Core Features

### 1. User Authentication & Management
- **User Sign Up**
  - Email and password registration
  - Password strength validation
  - Email uniqueness validation
  - Profile creation (username, bio, avatar)

- **User Login**
  - Email/username and password authentication
  - Session management with Flask-Login
  - Remember me functionality
  - Logout capability

### 2. Post Management
- **Creating Posts**
  - Title and content fields
  - Rich text support
  - Tag assignment (multiple tags per post)
  - Draft and publish states
  - Timestamp tracking (created_at, updated_at)

- **Viewing Posts**
  - Individual post view
  - Author information display
  - Tag display
  - Reply count and favorite count

### 3. Post Interactions
- **Replying to Posts**
  - Threaded comment system
  - Reply to post or reply to another reply
  - Nested reply display
  - Reply count tracking

- **Saving Posts**
  - Bookmark posts for later reading
  - Saved posts collection per user
  - Quick access to saved content

### 4. Tag System
- **Post Tags**
  - Multiple tags per post
  - Tag creation on-the-fly
  - Tag normalization (lowercase, trimmed)

- **Tag Search**
  - Search posts by single or multiple tags
  - Tag-based filtering
  - Popular tags display

- **Favorite Tags**
  - Users can favorite/follow tags
  - Personalized tag preferences
  - Feed generation based on favorited tags

### 5. Social Features
- **Following Users**
  - Follow/unfollow other users
  - Follower and following counts
  - Following list view

- **User Messaging**
  - Direct messages between users
  - Inbox and sent messages
  - Message threads/conversations
  - Unread message indicators
  - Message timestamps

- **Personalized Feed**
  - Posts from favorited tags
  - Posts from followed users (optional enhancement)
  - Chronological or relevance-based sorting
  - Pagination support

### 6. Search & Discovery
- **Tag-based Search**
  - Search posts by tags
  - Multiple tag filtering (AND/OR logic)
  - Search results with pagination

- **User Discovery**
  - Browse users
  - Search users by username
  - View user profiles with their posts

## Database Schema

**Schema Name**: `blog`

All tables are organized within the `blog` schema for better organization and namespace management. The schema is automatically created during database initialization.

### Schema Configuration
- **Search Path**: `blog, public`
- **Permissions**: Full access granted to `blog_user`
- **Indexes**: Performance indexes on frequently queried columns

### Users Table
**Table**: `blog.users`
- `id` (Primary Key)
- `username` (Unique, Not Null)
- `email` (Unique, Not Null)
- `password_hash` (Not Null)
- `bio` (Text, Optional)
- `avatar_url` (String, Optional)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

### Posts Table
**Table**: `blog.posts`
- `id` (Primary Key)
- `title` (String, Not Null)
- `content` (Text, Not Null)
- `author_id` (Foreign Key -> blog.users)
- `status` (Enum: draft, published)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

### Replies Table
**Table**: `blog.replies`
- `id` (Primary Key)
- `content` (Text, Not Null)
- `author_id` (Foreign Key -> blog.users)
- `post_id` (Foreign Key -> blog.posts)
- `parent_reply_id` (Foreign Key -> blog.replies, Optional for threading)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

### Tags Table
**Table**: `blog.tags`
- `id` (Primary Key)
- `name` (String, Unique, Not Null)
- `created_at` (Timestamp)

### PostTags Table (Many-to-Many)
**Table**: `blog.post_tags`
- `post_id` (Foreign Key -> blog.posts)
- `tag_id` (Foreign Key -> blog.tags)
- Primary Key: (post_id, tag_id)

### SavedPosts Table (Many-to-Many)
**Table**: `blog.saved_posts`
- `user_id` (Foreign Key -> blog.users)
- `post_id` (Foreign Key -> blog.posts)
- `saved_at` (Timestamp)
- Primary Key: (user_id, post_id)

### FavoriteTags Table (Many-to-Many)
**Table**: `blog.favorite_tags`
- `user_id` (Foreign Key -> blog.users)
- `tag_id` (Foreign Key -> blog.tags)
- `favorited_at` (Timestamp)
- Primary Key: (user_id, tag_id)

### Follows Table (Many-to-Many)
**Table**: `blog.follows`
- `follower_id` (Foreign Key -> blog.users)
- `following_id` (Foreign Key -> blog.users)
- `followed_at` (Timestamp)
- Primary Key: (follower_id, following_id)

### Messages Table
**Table**: `blog.messages`
- `id` (Primary Key)
- `sender_id` (Foreign Key -> blog.users)
- `recipient_id` (Foreign Key -> blog.users)
- `subject` (String, Optional)
- `content` (Text, Not Null)
- `is_read` (Boolean, Default: False)
- `created_at` (Timestamp)

## Application Structure

```
ai-python-demo/
├── app.py                      # Main application entry point
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Docker Compose configuration
├── .env                        # Environment variables (not in git)
├── .env.example                # Example environment variables template
├── .dockerignore               # Files to exclude from Docker build
├── .flaskenv                   # Flask-specific env vars
├── docker/
│   └── init.sql                # Database initialization script
├── models/
│   ├── __init__.py
│   ├── user.py                 # User model
│   ├── post.py                 # Post model
│   ├── reply.py                # Reply model
│   ├── tag.py                  # Tag model
│   ├── message.py              # Message model
│   └── associations.py         # Many-to-many relationships
├── routes/
│   ├── __init__.py
│   ├── auth.py                 # Authentication routes
│   ├── posts.py                # Post CRUD routes
│   ├── users.py                # User profile routes
│   ├── messages.py             # Messaging routes
│   ├── tags.py                 # Tag and search routes
│   └── feed.py                 # Feed generation routes
├── forms/
│   ├── __init__.py
│   ├── auth_forms.py           # Login/signup forms
│   ├── post_forms.py           # Post creation/edit forms
│   └── message_forms.py        # Message forms
├── templates/
│   ├── base.html               # Base template
│   ├── auth/
│   │   ├── login.html
│   │   └── signup.html
│   ├── posts/
│   │   ├── index.html          # All posts
│   │   ├── view.html           # Single post view
│   │   ├── create.html
│   │   └── edit.html
│   ├── users/
│   │   ├── profile.html
│   │   └── following.html
│   ├── messages/
│   │   ├── inbox.html
│   │   └── compose.html
│   ├── feed/
│   │   └── index.html          # Personalized feed
│   └── search/
│       └── results.html
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js              # AngularJS app config (with interpolation settings)
│   │   ├── controllers/
│   │   │   ├── auth.controller.js
│   │   │   ├── posts.controller.js
│   │   │   ├── feed.controller.js
│   │   │   └── messages.controller.js
│   │   └── services/
│   │       └── api.service.js
│   ├── lib/
│   │   └── angular.min.js      # AngularJS library
│   └── images/
├── migrations/                  # Database migrations
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_posts.py
    ├── test_messages.py
    └── test_tags.py
```

## Routes

### View Routes (HTML Templates)
These routes serve HTML pages. AngularJS handles interactivity and communicates with API endpoints.

- `GET /` - Homepage
- `GET /login` - Login page
- `GET /signup` - Signup page
- `GET /posts` - All posts page
- `GET /posts/<id>` - Single post view page
- `GET /posts/create` - Create post page
- `GET /posts/<id>/edit` - Edit post page
- `GET /users/<username>` - User profile page
- `GET /messages` - Messages inbox page
- `GET /messages/compose` - Compose message page
- `GET /feed` - Personalized feed page
- `GET /search` - Search page
- `GET /tags` - Tags page

### API Routes (JSON Responses)
All API routes are prefixed with `/api` and return JSON. Frontend uses fetch API/AJAX to interact with these endpoints.

#### Authentication API
- `POST /api/auth/signup` - Create new user account
  - Request: `{username, email, password, bio?, avatar_url?}`
  - Response: `{success, user, token}` or `{error}`
- `POST /api/auth/login` - Authenticate user
  - Request: `{email_or_username, password, remember_me?}`
  - Response: `{success, user, token}` or `{error}`
- `POST /api/auth/logout` - Logout current user
  - Response: `{success}`
- `GET /api/auth/me` - Get current authenticated user
  - Response: `{user}` or `{error}`

#### Posts API
- `GET /api/posts` - Get all posts (paginated)
  - Query params: `?page=1&limit=20&sort=recent`
  - Response: `{posts: [], total, page, pages}`
- `GET /api/posts/<id>` - Get single post with replies
  - Response: `{post, replies: []}`
- `POST /api/posts` - Create new post
  - Request: `{title, content, tags: [], status: 'draft'|'published'}`
  - Response: `{success, post}` or `{error}`
- `PUT /api/posts/<id>` - Update post
  - Request: `{title?, content?, tags?, status?}`
  - Response: `{success, post}` or `{error}`
- `DELETE /api/posts/<id>` - Delete post
  - Response: `{success}` or `{error}`
- `POST /api/posts/<id>/save` - Save/bookmark post
  - Response: `{success, saved: true|false}`
- `DELETE /api/posts/<id>/save` - Unsave post
  - Response: `{success}`
- `POST /api/posts/<id>/replies` - Add reply to post
  - Request: `{content, parent_reply_id?}`
  - Response: `{success, reply}` or `{error}`

#### Users API
- `GET /api/users/<username>` - Get user profile
  - Response: `{user, stats: {posts_count, followers_count, following_count}}`
- `GET /api/users/<username>/posts` - Get user's posts
  - Query params: `?page=1&limit=20`
  - Response: `{posts: [], total, page, pages}`
- `POST /api/users/<username>/follow` - Follow user
  - Response: `{success, following: true}`
- `DELETE /api/users/<username>/follow` - Unfollow user
  - Response: `{success, following: false}`
- `GET /api/users/<username>/followers` - Get user's followers
  - Response: `{followers: []}`
- `GET /api/users/<username>/following` - Get users being followed
  - Response: `{following: []}`
- `GET /api/users/me/saved` - Get current user's saved posts
  - Response: `{posts: []}`

#### Messages API
- `GET /api/messages` - Get inbox messages
  - Query params: `?page=1&limit=20`
  - Response: `{messages: [], total, unread_count}`
- `GET /api/messages/sent` - Get sent messages
  - Response: `{messages: []}`
- `GET /api/messages/<id>` - Get single message
  - Response: `{message}`
- `POST /api/messages` - Send new message
  - Request: `{recipient_id, subject?, content}`
  - Response: `{success, message}` or `{error}`
- `DELETE /api/messages/<id>` - Delete message
  - Response: `{success}`
- `PUT /api/messages/<id>/read` - Mark message as read
  - Response: `{success}`

#### Tags API
- `GET /api/tags` - Get all tags
  - Query params: `?popular=true&limit=50`
  - Response: `{tags: [{id, name, post_count}]}`
- `GET /api/tags/<tag_name>/posts` - Get posts with specific tag
  - Query params: `?page=1&limit=20`
  - Response: `{posts: [], tag, total}`
- `POST /api/tags/<tag_id>/favorite` - Favorite tag
  - Response: `{success, favorited: true}`
- `DELETE /api/tags/<tag_id>/favorite` - Unfavorite tag
  - Response: `{success, favorited: false}`
- `GET /api/tags/favorites` - Get user's favorited tags
  - Response: `{tags: []}`

#### Search API
- `GET /api/search` - Search posts by tags
  - Query params: `?tags=tag1,tag2&page=1&limit=20&match=all|any`
  - Response: `{posts: [], total, tags_searched: []}`

#### Feed API
- `GET /api/feed` - Get personalized feed
  - Query params: `?page=1&limit=20`
  - Response: `{posts: [], total, based_on_tags: []}`

## Docker Configuration

### Dockerfile
The application runs in a Docker container with configurable PORT:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set default port (can be overridden via environment variable)
ENV PORT=8080
EXPOSE ${PORT}

# Run the application with configurable port
CMD gunicorn -w 4 -b 0.0.0.0:${PORT} app:app
```

### docker-compose.yml
Orchestrates the Flask app and PostgreSQL database with automatic initialization:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: blog_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-blog_db}
      POSTGRES_USER: ${POSTGRES_USER:-blog_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-blog_password}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-blog_user}"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build: .
    container_name: blog_app
    environment:
      FLASK_APP: app.py
      FLASK_ENV: ${FLASK_ENV:-production}
      SECRET_KEY: ${SECRET_KEY}
      DATABASE_URL: postgresql://${POSTGRES_USER:-blog_user}:${POSTGRES_PASSWORD:-blog_password}@db:5432/${POSTGRES_DB:-blog_db}
      PORT: ${PORT:-8080}
      PYTHONUNBUFFERED: 1
    volumes:
      - .:/app
      - /app/__pycache__
    ports:
      - "${PORT:-8080}:${PORT:-8080}"
    depends_on:
      db:
        condition: service_healthy
    command: >
      sh -c "flask db upgrade && 
             gunicorn -w 4 -b 0.0.0.0:${PORT:-8080} --reload app:app"

volumes:
  postgres_data:
```

**Note**: The `./docker/init.sql` file is mounted to `/docker-entrypoint-initdb.d/init.sql`. PostgreSQL automatically executes scripts in this directory on first initialization.

### .env.example
Template for environment variables:

```bash
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-change-this-in-production
PORT=8080

# Database Configuration
POSTGRES_DB=blog_db
POSTGRES_USER=blog_user
POSTGRES_PASSWORD=blog_password
DATABASE_URL=postgresql://blog_user:blog_password@db:5432/blog_db

# Application Settings
DEBUG=True
TESTING=False
```

**Note**: The `PORT` variable allows you to run the application on a different port if 8080 is already in use. Simply change it in your `.env` file (e.g., `PORT=8080`).

### .dockerignore
```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
venv/
env/
.env
.git
.gitignore
*.md
.DS_Store
migrations/versions/*.pyc
*.log
.pytest_cache
.coverage
htmlcov/
```

### docker/init.sql
SQL script for automatic database initialization. This runs only on first container creation:

```sql
-- Database initialization script
-- This script runs automatically when the PostgreSQL container is first created

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: Tables will be created by Flask-Migrate (Alembic)
-- This script is for any additional database setup needed

-- Create indexes for performance (optional, can also be done in migrations)
-- Example:
-- CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_posts_author_id ON posts(author_id);

-- Set default timezone
SET timezone = 'UTC';

-- Grant necessary permissions (if needed)
-- GRANT ALL PRIVILEGES ON DATABASE blog_db TO blog_user;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully at %', NOW();
END $$;
```

**Important Notes**:
- This script runs **only once** when the PostgreSQL container is first created
- If the volume `postgres_data` already exists, the script will NOT run again
- To re-run initialization: `docker-compose down -v` (removes volumes)
- Flask-Migrate handles table creation via migrations
- Use this script for extensions, custom functions, or initial data

## Development Workflow

### Local Development with Docker

1. **Clone repository and set up environment**
   ```bash
   git clone <repository>
   cd ai-python-demo
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Build and start containers**
   ```bash
   docker-compose up --build
   ```
   
   The database will be automatically initialized using `docker/init.sql` on first run.

3. **Run migrations (first time only)**
   ```bash
   docker-compose exec web flask db init
   docker-compose exec web flask db migrate -m "Initial migration"
   docker-compose exec web flask db upgrade
   ```
   
   **Note**: After the first setup, migrations run automatically on container start (see docker-compose.yml command).

4. **Access the application**
   - Web app: http://localhost:8080 (or your configured PORT)
   - PostgreSQL: localhost:5432
   
   **Note**: If you changed the PORT in your `.env` file, access the app at `http://localhost:YOUR_PORT`

5. **View logs**
   ```bash
   docker-compose logs -f web
   docker-compose logs -f db
   ```

6. **Stop containers**
   ```bash
   docker-compose down
   ```

7. **Stop and remove volumes (reset database)**
   ```bash
   docker-compose down -v
   ```
   
   After removing volumes, the `init.sql` script will run again on next startup.

### Common Docker Commands

- **Rebuild containers**: `docker-compose up --build`
- **Run Flask shell**: `docker-compose exec web flask shell`
- **Create migration**: `docker-compose exec web flask db migrate -m "description"`
- **Apply migrations**: `docker-compose exec web flask db upgrade`
- **Rollback migration**: `docker-compose exec web flask db downgrade`
- **Access PostgreSQL**: `docker-compose exec db psql -U blog_user -d blog_db`
- **View database logs**: `docker-compose logs db | grep -i error`

### Development Without Docker (Optional)

1. Set up virtual environment and install dependencies
2. Configure PostgreSQL connection in `.env`
3. Create database models
4. Initialize database migrations
5. Run Flask development server

### Feature Implementation Order

1. Create database models (User, Post, Reply, Tag, Message)
2. Implement API authentication routes (`/api/auth/*`)
3. Build API endpoints for posts, users, messages, tags, feed
4. Create view routes that serve HTML templates
5. Develop AngularJS controllers and services for API communication
6. Implement fetch API/AJAX calls in frontend
7. Design and style templates with AngularJS directives
8. Add error handling and loading states in frontend
9. Write tests for all API endpoints and frontend interactions
10. Optimize Docker configuration for production

## Configuration Management

The application is designed to be **container-first** and uses environment variables for all configuration:

### config.py Structure
```python
import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    FLASK_ENV = 'development'
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    FLASK_ENV = 'production'
    # Additional production settings

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://test_user:test_pass@localhost:5432/test_db'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

### Required Environment Variables

- `FLASK_APP` - Application entry point (app.py)
- `FLASK_ENV` - Environment (development/production)
- `SECRET_KEY` - Flask secret key for sessions
- `DATABASE_URL` - PostgreSQL connection string
- `PORT` - Application port (default: 8080)
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password

## Security Considerations

- Password hashing with Werkzeug
- CSRF protection for API endpoints (use tokens in headers)
- SQL injection prevention via SQLAlchemy ORM
- Session security with secure cookies or JWT tokens
- Input validation and sanitization on both frontend and backend
- Rate limiting for API endpoints
- CORS configuration for API routes
- Content-Type validation (ensure JSON for API requests)
- Authentication required for protected API endpoints
- Authorization checks (users can only modify their own content)
- **Docker security**: Non-root user in container, minimal base image
- **Environment variables**: Never commit `.env` to version control
- **Database**: PostgreSQL runs in isolated container with health checks

## Future Enhancements

- Image uploads for posts and avatars
- Rich text editor for post content
- Email notifications
- Post likes/reactions
- Trending posts algorithm
- Admin dashboard
- API endpoints for mobile app
- Real-time messaging with WebSockets
- Post categories in addition to tags
