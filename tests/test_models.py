from models.tag import Tag
from models.user import User


class TestTagNormalization:
    def test_lowercase(self):
        assert Tag.normalize_name('Python') == 'python'

    def test_strips_whitespace(self):
        assert Tag.normalize_name('  flask  ') == 'flask'

    def test_lowercase_and_strip(self):
        assert Tag.normalize_name('  Django  ') == 'django'

    def test_already_normalized(self):
        assert Tag.normalize_name('react') == 'react'

    def test_empty_string(self):
        assert Tag.normalize_name('') == ''


class TestUserPassword:
    def test_set_password_does_not_store_plaintext(self):
        user = User(username='u', email='u@test.com')
        user.set_password('s3cret')
        assert user.password_hash != 's3cret'

    def test_set_password_produces_hash(self):
        user = User(username='u', email='u@test.com')
        user.set_password('s3cret')
        assert user.password_hash is not None
        assert len(user.password_hash) > 20

    def test_check_password_correct(self):
        user = User(username='u', email='u@test.com')
        user.set_password('s3cret')
        assert user.check_password('s3cret') is True

    def test_check_password_wrong(self):
        user = User(username='u', email='u@test.com')
        user.set_password('s3cret')
        assert user.check_password('wrong') is False

    def test_check_password_empty(self):
        user = User(username='u', email='u@test.com')
        user.set_password('s3cret')
        assert user.check_password('') is False

    def test_different_passwords_produce_different_hashes(self):
        u1 = User(username='a', email='a@test.com')
        u2 = User(username='b', email='b@test.com')
        u1.set_password('pass1')
        u2.set_password('pass2')
        assert u1.password_hash != u2.password_hash


class TestUserToDict:
    def test_expected_keys_present(self, test_user):
        d = test_user.to_dict()
        for key in ('id', 'username', 'email', 'bio', 'avatar_url', 'created_at', 'updated_at'):
            assert key in d

    def test_password_not_exposed(self, test_user):
        d = test_user.to_dict()
        assert 'password_hash' not in d
        assert 'password' not in d

    def test_values_match(self, test_user):
        d = test_user.to_dict()
        assert d['username'] == 'testuser'
        assert d['email'] == 'test@example.com'

    def test_timestamps_are_iso_strings(self, test_user):
        d = test_user.to_dict()
        assert 'T' in d['created_at']
        assert 'T' in d['updated_at']
