import json


def _post(client, url, data):
    return client.post(url, data=json.dumps(data), content_type='application/json')


def _login(client):
    return _post(client, '/api/auth/login', {
        'email_or_username': 'testuser',
        'password': 'password123',
    })


class TestGetPosts:
    def test_returns_200(self, client):
        r = client.get('/api/posts')
        assert r.status_code == 200

    def test_empty_list_when_no_posts(self, client):
        data = client.get('/api/posts').get_json()
        assert data['posts'] == []

    def test_pagination_fields_present(self, client):
        data = client.get('/api/posts').get_json()
        for key in ('posts', 'total', 'page', 'pages'):
            assert key in data

    def test_default_page_is_1(self, client):
        data = client.get('/api/posts').get_json()
        assert data['page'] == 1


class TestCreatePost:
    def test_unauthenticated_is_rejected(self, client):
        r = _post(client, '/api/posts', {'title': 'Test', 'content': 'Body'})
        # Flask-Login redirects (302) or returns 401 depending on config
        assert r.status_code in (302, 401)

    def test_empty_body_returns_400(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {})
        assert r.status_code == 400

    def test_missing_content_returns_400(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {'title': 'No content'})
        assert r.status_code == 400

    def test_missing_title_returns_400(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {'content': 'No title'})
        assert r.status_code == 400

    def test_success_returns_201(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {'title': 'Hello', 'content': 'World'})
        assert r.status_code == 201
        data = r.get_json()
        assert data['success'] is True
        assert data['post']['title'] == 'Hello'
        assert data['post']['content'] == 'World'
        assert data['post']['status'] == 'published'

    def test_post_appears_in_listing(self, client, test_user):
        _login(client)
        _post(client, '/api/posts', {'title': 'Visible Post', 'content': 'Body'})
        listing = client.get('/api/posts').get_json()
        titles = [p['title'] for p in listing['posts']]
        assert 'Visible Post' in titles

    def test_tags_are_normalized(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {
            'title': 'Tagged',
            'content': 'Body',
            'tags': ['Python', '  Flask  '],
        })
        assert r.status_code == 201
        tag_names = [t['name'] for t in r.get_json()['post']['tags']]
        assert 'python' in tag_names
        assert 'flask' in tag_names

    def test_draft_status_stored(self, client, test_user):
        _login(client)
        r = _post(client, '/api/posts', {
            'title': 'Draft',
            'content': 'Not published',
            'status': 'draft',
        })
        assert r.status_code == 201
        assert r.get_json()['post']['status'] == 'draft'


class TestDeletePost:
    def test_owner_can_delete(self, client, test_user):
        _login(client)
        create_r = _post(client, '/api/posts', {'title': 'To Delete', 'content': 'Bye'})
        post_id = create_r.get_json()['post']['id']
        r = client.delete(f'/api/posts/{post_id}')
        assert r.status_code == 200

    def test_deleted_post_not_in_listing(self, client, test_user):
        _login(client)
        create_r = _post(client, '/api/posts', {'title': 'Gone', 'content': 'Poof'})
        post_id = create_r.get_json()['post']['id']
        client.delete(f'/api/posts/{post_id}')
        listing = client.get('/api/posts').get_json()
        titles = [p['title'] for p in listing['posts']]
        assert 'Gone' not in titles
