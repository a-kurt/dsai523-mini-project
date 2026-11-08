"""Isolated app and users; TEST_DATABASE_URL enables the same tests on PostgreSQL."""
import os
import pytest
from movie_court import create_app
from movie_court.models import db


@pytest.fixture()
def app(tmp_path, monkeypatch):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-key-is-not-a-production-secret',
        'SQLALCHEMY_DATABASE_URI': os.environ.get('TEST_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'test.sqlite')),
        'SESSION_COOKIE_SECURE': False, 'RATE_LIMIT_ENABLED': False})
    with app.app_context():
        db.drop_all()
        db.create_all()
    monkeypatch.setattr('movie_court.tmdb.get_movie', lambda movie_id: {
        'id': movie_id, 'title': 'Shrek 2', 'release_date': '2004-05-19',
        'overview': 'An ogre visits his in-laws.', 'poster_path': None})
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


class Actor:
    def __init__(self, app, username):
        self.client = app.test_client()
        self.token = self.client.get('/api/auth/me').json['csrf_token']
        response = self.send('post', '/api/auth/register', {'username': username, 'password': 'correct horse battery'})
        assert response.status_code == 201, response.json
        self.id = response.json['user']['id']
        self.refresh()

    def refresh(self):
        self.token = self.client.get('/api/auth/me').json['csrf_token']

    def send(self, method, path, data=None):
        return getattr(self.client, method)(path, json=data, headers={'X-CSRF-Token': self.token})

    def get(self, path):
        return self.client.get(path)


@pytest.fixture()
def actors(app):
    return {name: Actor(app, name) for name in ('judge', 'prosecutor', 'defender', 'juror', 'outsider')}


@pytest.fixture()
def courtroom(actors):
    judge = actors['judge']
    response = judge.send('post', '/api/cases', {'movie_id': 809, 'title': 'Shrek on trial', 'charge': 'The best sequel ever?'})
    assert response.status_code == 201
    case_id = response.json['case']['id']
    for role in ('prosecutor', 'defender', 'juror'):
        token = judge.send('post', f'/api/cases/{case_id}/invites', {'role': role}).json['token']
        assert actors[role].send('post', '/api/invites/redeem', {'token': token}).status_code == 201
    return case_id, actors
