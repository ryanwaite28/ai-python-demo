import json


def _post(client, url, data):
    return client.post(url, data=json.dumps(data), content_type='application/json')


class TestSignup:
    def test_empty_body_returns_400(self, client):
        r = _post(client, '/api/auth/signup', {})
        assert r.status_code == 400

    def test_missing_password_returns_400(self, client):
        r = _post(client, '/api/auth/signup', {'username': 'u', 'email': 'u@test.com'})
        assert r.status_code == 400

    def test_missing_email_returns_400(self, client):
        r = _post(client, '/api/auth/signup', {'username': 'u', 'password': 'pass'})
        assert r.status_code == 400

    def test_success_returns_201_with_user(self, client):
        r = _post(client, '/api/auth/signup', {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'password123',
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data['success'] is True
        assert data['user']['username'] == 'newuser'
        assert 'password' not in data['user']
        assert 'password_hash' not in data['user']

    def test_duplicate_username_returns_400(self, client, test_user):
        r = _post(client, '/api/auth/signup', {
            'username': 'testuser',
            'email': 'other@test.com',
            'password': 'password123',
        })
        assert r.status_code == 400
        assert 'Username already exists' in r.get_json()['error']

    def test_duplicate_email_returns_400(self, client, test_user):
        r = _post(client, '/api/auth/signup', {
            'username': 'otheruser',
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert r.status_code == 400
        assert 'Email already exists' in r.get_json()['error']


class TestLogin:
    def test_empty_body_returns_400(self, client):
        r = _post(client, '/api/auth/login', {})
        assert r.status_code == 400

    def test_missing_password_returns_400(self, client):
        r = _post(client, '/api/auth/login', {'email_or_username': 'u'})
        assert r.status_code == 400

    def test_wrong_password_returns_401(self, client, test_user):
        r = _post(client, '/api/auth/login', {
            'email_or_username': 'testuser',
            'password': 'wrongpassword',
        })
        assert r.status_code == 401

    def test_nonexistent_user_returns_401(self, client):
        r = _post(client, '/api/auth/login', {
            'email_or_username': 'nobody',
            'password': 'password123',
        })
        assert r.status_code == 401

    def test_login_by_username(self, client, test_user):
        r = _post(client, '/api/auth/login', {
            'email_or_username': 'testuser',
            'password': 'password123',
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['success'] is True
        assert data['user']['username'] == 'testuser'

    def test_login_by_email(self, client, test_user):
        r = _post(client, '/api/auth/login', {
            'email_or_username': 'test@example.com',
            'password': 'password123',
        })
        assert r.status_code == 200


class TestLogout:
    def test_logout_returns_200(self, client):
        r = _post(client, '/api/auth/logout', {})
        assert r.status_code == 200
        assert r.get_json()['success'] is True


class TestCurrentUser:
    def test_unauthenticated_returns_401(self, client):
        r = client.get('/api/auth/me')
        assert r.status_code == 401

    def test_authenticated_returns_200_with_user(self, client, test_user):
        _post(client, '/api/auth/login', {
            'email_or_username': 'testuser',
            'password': 'password123',
        })
        r = client.get('/api/auth/me')
        assert r.status_code == 200
        assert r.get_json()['user']['username'] == 'testuser'

    def test_after_logout_returns_401(self, client, test_user):
        _post(client, '/api/auth/login', {
            'email_or_username': 'testuser',
            'password': 'password123',
        })
        _post(client, '/api/auth/logout', {})
        r = client.get('/api/auth/me')
        assert r.status_code == 401
