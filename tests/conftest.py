import pytest
from sqlalchemy import event
from app import create_app, db as _db


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    ctx = app.app_context()
    ctx.push()

    # SQLite doesn't have native schemas; ATTACH ':memory:' AS blog creates a
    # second in-memory database that acts as the 'blog' schema. StaticPool
    # (the default for sqlite:///:memory:) keeps a single connection alive for
    # the engine's lifetime so the ATTACH persists across the test session.
    @event.listens_for(_db.engine, 'connect')
    def attach_blog_schema(dbapi_connection, _connection_record):
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS blog")

    _db.create_all()
    yield app
    _db.drop_all()
    ctx.pop()


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()


@pytest.fixture(scope='function', autouse=True)
def clean_db():
    yield
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


@pytest.fixture
def test_user(app):
    from models.user import User
    user = User(username='testuser', email='test@example.com')
    user.set_password('password123')
    _db.session.add(user)
    _db.session.commit()
    return user
