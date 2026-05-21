-- Database initialization script
-- This script runs automatically when the PostgreSQL container is first created

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set default timezone
SET timezone = 'UTC';

-- Create schema for the blog application
CREATE SCHEMA IF NOT EXISTS blog;

-- Grant schema permissions to the blog user
GRANT ALL ON SCHEMA blog TO blog_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA blog TO blog_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA blog TO blog_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA blog GRANT ALL ON TABLES TO blog_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA blog GRANT ALL ON SEQUENCES TO blog_user;

-- Set search path to include blog schema
ALTER DATABASE blog_db SET search_path TO blog, public;

-- Create tables within the blog schema
-- Note: Flask-Migrate will also create these, but we define them here for initial setup

CREATE TABLE IF NOT EXISTS blog.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blog.posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'published',
    author_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blog.replies (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
    parent_reply_id INTEGER REFERENCES blog.replies(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blog.tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blog.messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    recipient_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    subject VARCHAR(255),
    content TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many relationship tables
CREATE TABLE IF NOT EXISTS blog.post_tags (
    post_id INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES blog.tags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

CREATE TABLE IF NOT EXISTS blog.saved_posts (
    user_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
    saved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, post_id)
);

CREATE TABLE IF NOT EXISTS blog.favorite_tags (
    user_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES blog.tags(id) ON DELETE CASCADE,
    favorited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, tag_id)
);

CREATE TABLE IF NOT EXISTS blog.follows (
    follower_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    following_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
    followed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON blog.users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON blog.users(email);
CREATE INDEX IF NOT EXISTS idx_posts_author_id ON blog.posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON blog.posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_status ON blog.posts(status);
CREATE INDEX IF NOT EXISTS idx_replies_post_id ON blog.replies(post_id);
CREATE INDEX IF NOT EXISTS idx_replies_author_id ON blog.replies(author_id);
CREATE INDEX IF NOT EXISTS idx_replies_parent_reply_id ON blog.replies(parent_reply_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON blog.tags(name);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON blog.messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON blog.messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON blog.messages(created_at DESC);

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database schema "blog" and tables initialized successfully at %', NOW();
END $$;
