import logging
import os
import time
from flask import Flask, g, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from prometheus_flask_exporter import PrometheusMetrics
from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    from logging_config import configure_logging
    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Prometheus — auto-instruments all routes and exposes /metrics.
    # Excludes /metrics itself from being tracked to avoid noise.
    PrometheusMetrics(app, excluded_paths=['^/metrics$'])

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.posts import posts_bp
    from routes.users import users_bp
    from routes.messages import messages_bp
    from routes.tags import tags_bp
    from routes.feed import feed_bp
    from routes.views import views_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(posts_bp, url_prefix='/api/posts')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    app.register_blueprint(tags_bp, url_prefix='/api/tags')
    app.register_blueprint(feed_bp, url_prefix='/api/feed')

    @app.before_request
    def before_request():
        g.start_time = time.monotonic()
        user_id = current_user.id if current_user.is_authenticated else None
        logger.info(
            'Request started | method=%s path=%s ip=%s user_id=%s',
            request.method,
            request.path,
            request.remote_addr,
            user_id,
        )

    @app.after_request
    def after_request(response):
        duration_ms = round((time.monotonic() - g.start_time) * 1000, 2)
        user_id = current_user.id if current_user.is_authenticated else None
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            level,
            'Request finished | method=%s path=%s status=%s duration_ms=%s user_id=%s',
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_id,
        )
        return response

    @app.errorhandler(404)
    def not_found(error):
        logger.warning(
            '404 Not Found | method=%s path=%s ip=%s',
            request.method,
            request.path,
            request.remote_addr,
        )
        return {'error': 'Resource not found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logger.error(
            '500 Internal Server Error | method=%s path=%s ip=%s',
            request.method,
            request.path,
            request.remote_addr,
            exc_info=error,
        )
        return {'error': 'Internal server error'}, 500

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
