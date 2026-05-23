"""Initial migration — create all tables

Revision ID: c62f9aee6afc
Revises:
Create Date: 2026-03-26 19:08:02.503424

Uses CREATE TABLE IF NOT EXISTS so this is safe to run against a database
that was pre-populated by docker/init.sql (local dev) as well as a fresh
database (production / Kubernetes).
"""
from alembic import op


revision = 'c62f9aee6afc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS blog;

        CREATE TABLE IF NOT EXISTS blog.users (
            id          SERIAL PRIMARY KEY,
            username    VARCHAR(80)  UNIQUE NOT NULL,
            email       VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            bio         TEXT,
            avatar_url  VARCHAR(255),
            created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blog.tags (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(50) UNIQUE NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blog.posts (
            id         SERIAL PRIMARY KEY,
            title      VARCHAR(255) NOT NULL,
            content    TEXT NOT NULL,
            status     VARCHAR(20)  NOT NULL DEFAULT 'published',
            author_id  INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blog.replies (
            id              SERIAL PRIMARY KEY,
            content         TEXT NOT NULL,
            author_id       INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            post_id         INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
            parent_reply_id INTEGER REFERENCES blog.replies(id) ON DELETE CASCADE,
            created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blog.messages (
            id           SERIAL PRIMARY KEY,
            sender_id    INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            subject      VARCHAR(255),
            content      TEXT NOT NULL,
            is_read      BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blog.post_tags (
            post_id INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES blog.tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (post_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS blog.saved_posts (
            user_id  INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            post_id  INTEGER NOT NULL REFERENCES blog.posts(id) ON DELETE CASCADE,
            saved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, post_id)
        );

        CREATE TABLE IF NOT EXISTS blog.favorite_tags (
            user_id      INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            tag_id       INTEGER NOT NULL REFERENCES blog.tags(id)  ON DELETE CASCADE,
            favorited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS blog.follows (
            follower_id  INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            following_id INTEGER NOT NULL REFERENCES blog.users(id) ON DELETE CASCADE,
            followed_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (follower_id, following_id)
        );

        CREATE INDEX IF NOT EXISTS ix_blog_users_username     ON blog.users(username);
        CREATE INDEX IF NOT EXISTS ix_blog_users_email        ON blog.users(email);
        CREATE INDEX IF NOT EXISTS ix_blog_posts_author_id    ON blog.posts(author_id);
        CREATE INDEX IF NOT EXISTS ix_blog_posts_created_at   ON blog.posts(created_at);
        CREATE INDEX IF NOT EXISTS ix_blog_replies_post_id          ON blog.replies(post_id);
        CREATE INDEX IF NOT EXISTS ix_blog_replies_author_id        ON blog.replies(author_id);
        CREATE INDEX IF NOT EXISTS ix_blog_replies_parent_reply_id  ON blog.replies(parent_reply_id);
        CREATE INDEX IF NOT EXISTS ix_blog_tags_name          ON blog.tags(name);
        CREATE INDEX IF NOT EXISTS ix_blog_messages_sender_id    ON blog.messages(sender_id);
        CREATE INDEX IF NOT EXISTS ix_blog_messages_recipient_id ON blog.messages(recipient_id);
        CREATE INDEX IF NOT EXISTS ix_blog_messages_created_at   ON blog.messages(created_at);
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS blog.follows        CASCADE;
        DROP TABLE IF EXISTS blog.favorite_tags  CASCADE;
        DROP TABLE IF EXISTS blog.saved_posts    CASCADE;
        DROP TABLE IF EXISTS blog.post_tags      CASCADE;
        DROP TABLE IF EXISTS blog.messages       CASCADE;
        DROP TABLE IF EXISTS blog.replies        CASCADE;
        DROP TABLE IF EXISTS blog.posts          CASCADE;
        DROP TABLE IF EXISTS blog.tags           CASCADE;
        DROP TABLE IF EXISTS blog.users          CASCADE;
    """)
