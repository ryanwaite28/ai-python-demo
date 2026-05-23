"""
Custom Prometheus metrics for business-level observability.

HTTP request counts and latency are handled automatically by
PrometheusMetrics (prometheus-flask-exporter) and exposed at /metrics.
The counters here track domain events that HTTP metrics alone cannot capture.
"""
from prometheus_client import Counter, Gauge

# ── Auth ──────────────────────────────────────────────────────────────────────

user_signups_total = Counter(
    'app_user_signups_total',
    'Total successful user registrations',
)

user_logins_total = Counter(
    'app_user_logins_total',
    'Total successful user logins',
    ['remember_me'],  # label: 'true' | 'false'
)

login_failures_total = Counter(
    'app_login_failures_total',
    'Failed login attempts',
    ['reason'],  # label: 'missing_fields' | 'invalid_credentials'
)

# ── Posts ─────────────────────────────────────────────────────────────────────

posts_created_total = Counter(
    'app_posts_created_total',
    'Total posts created',
    ['status'],  # label: 'published' | 'draft'
)

posts_updated_total = Counter(
    'app_posts_updated_total',
    'Total posts updated',
)

posts_deleted_total = Counter(
    'app_posts_deleted_total',
    'Total posts deleted',
)

post_saves_total = Counter(
    'app_post_saves_total',
    'Total times a post was saved to a user library',
)

replies_created_total = Counter(
    'app_replies_created_total',
    'Total replies created',
    ['is_nested'],  # label: 'true' (reply to reply) | 'false' (top-level)
)

# ── Social ────────────────────────────────────────────────────────────────────

user_follows_total = Counter(
    'app_user_follows_total',
    'Total follow actions',
)

user_unfollows_total = Counter(
    'app_user_unfollows_total',
    'Total unfollow actions',
)

# ── Messages ──────────────────────────────────────────────────────────────────

messages_sent_total = Counter(
    'app_messages_sent_total',
    'Total direct messages sent',
)

messages_read_total = Counter(
    'app_messages_read_total',
    'Total messages marked as read',
)

# ── Tags ──────────────────────────────────────────────────────────────────────

tag_favorites_total = Counter(
    'app_tag_favorites_total',
    'Total tag favorite actions',
)

tag_unfavorites_total = Counter(
    'app_tag_unfavorites_total',
    'Total tag unfavorite actions',
)

tags_created_total = Counter(
    'app_tags_created_total',
    'Total new tags auto-created when attaching to a post',
)
