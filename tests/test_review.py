"""Independent security and workflow regression checks from implementation review."""
from datetime import timedelta
import hashlib
import os
import pytest
from sqlalchemy import select
from movie_court import create_app
from movie_court.models import db, Invite, User, now


@pytest.fixture
def review_app(monkeypatch):
    monkeypatch.delenv('APP_ENV', raising=False)
    app = create_app({'TESTING': True, 'SECRET_KEY': 'review-key', 'SQLALCHEMY_DATABASE_URI': os.environ.get('TEST_DATABASE_URL', 'sqlite://'), 'RATE_LIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
    monkeypatch.setattr('movie_court.tmdb.get_movie', lambda movie_id: {
        'id': movie_id, 'title': 'Shrek 2', 'overview': 'A movie.', 'release_date': '2004-05-19', 'poster_path': None,
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def mutation(client, method, path, data=None):
    csrf = client.get('/api/auth/me').json['csrf_token']
    return client.open(path, method=method, json=data, headers={'X-CSRF-Token': csrf})


def actor(app, username):
    client = app.test_client()
    response = mutation(client, 'POST', '/api/auth/register', {'username': username, 'password': 'a long review password'})
    assert response.status_code == 201
    return client


def case_for(judge):
    response = mutation(judge, 'POST', '/api/cases', {'movie_id': 809, 'title': 'Sequel court', 'charge': 'Too good?'})
    assert response.status_code == 201
    return response.json['case']['id']


def join(judge, guest, case_id, role):
    invite = mutation(judge, 'POST', f'/api/cases/{case_id}/invites', {'role': role})
    assert invite.status_code == 201
    response = mutation(guest, 'POST', '/api/invites/redeem', {'token': invite.json['token']})
    assert response.status_code == 201
    return invite.json['token']


def test_non_ascii_csrf_is_rejected_without_server_error(review_app):
    client = review_app.test_client()
    client.get('/api/auth/me')
    response = client.post('/api/auth/login', json={'username': 'reviewer', 'password': 'anything'}, headers={'X-CSRF-Token': 'é'})
    assert response.status_code == 403


def test_session_rotates_csrf_at_sign_in_and_cache_is_private(review_app):
    client = review_app.test_client()
    before = client.get('/api/auth/me').json['csrf_token']
    response = client.post('/api/auth/register', json={'username': 'reviewer', 'password': 'a long review password'}, headers={'X-CSRF-Token': before})
    assert response.status_code == 201
    assert response.headers['Cache-Control'] == 'no-store'
    after = client.get('/api/auth/me').json['csrf_token']
    assert before != after
    assert client.post('/api/auth/logout', headers={'X-CSRF-Token': before}).status_code == 403


def test_case_privacy_and_argument_ownership(review_app):
    judge = actor(review_app, 'judge')
    outsider = actor(review_app, 'outsider')
    prosecutor = actor(review_app, 'prosecutor')
    defender = actor(review_app, 'defender')
    case_id = case_for(judge)
    assert outsider.get(f'/api/cases/{case_id}').status_code == 404
    assert outsider.get('/api/cases').json == {'cases': []}
    join(judge, prosecutor, case_id, 'prosecutor')
    join(judge, defender, case_id, 'defender')
    response = mutation(prosecutor, 'POST', f'/api/cases/{case_id}/arguments', {'body': 'A strong argument'})
    argument_id = response.json['argument']['id']
    assert mutation(defender, 'PATCH', f'/api/cases/{case_id}/arguments/{argument_id}', {'body': 'Changed'}).status_code == 403
    assert mutation(defender, 'DELETE', f'/api/cases/{case_id}/arguments/{argument_id}').status_code == 403
    assert mutation(prosecutor, 'PATCH', f'/api/cases/{case_id}', {'charge': 'Changed'}).status_code == 403
    assert mutation(outsider, 'DELETE', f'/api/cases/{case_id}').status_code == 404


def test_invites_are_hashed_expiring_revocable_and_single_use(review_app):
    judge = actor(review_app, 'judge')
    guest = actor(review_app, 'guest')
    other = actor(review_app, 'other')
    case_id = case_for(judge)
    token = join(judge, guest, case_id, 'juror')
    with review_app.app_context():
        invitation = db.session.scalar(select(Invite).where(Invite.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        assert invitation is not None
        assert token != invitation.token_hash
    assert mutation(other, 'POST', '/api/invites/redeem', {'token': token}).status_code == 400
    expired = mutation(judge, 'POST', f'/api/cases/{case_id}/invites', {'role': 'juror'}).json['token']
    with review_app.app_context():
        invitation = db.session.scalar(select(Invite).where(Invite.token_hash == hashlib.sha256(expired.encode()).hexdigest()))
        invitation.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert mutation(other, 'POST', '/api/invites/redeem', {'token': expired}).status_code == 400
    revoked = mutation(judge, 'POST', f'/api/cases/{case_id}/invites', {'role': 'juror'}).json['token']
    assert mutation(judge, 'DELETE', f'/api/cases/{case_id}/invites').status_code == 204
    assert mutation(other, 'POST', '/api/invites/redeem', {'token': revoked}).status_code == 400


def test_ballot_secrecy_freeze_and_final_verdict(review_app):
    judge = actor(review_app, 'judge')
    prosecutor = actor(review_app, 'prosecutor')
    defender = actor(review_app, 'defender')
    juror = actor(review_app, 'juror')
    late = actor(review_app, 'late')
    case_id = case_for(judge)
    for client, role in [(prosecutor, 'prosecutor'), (defender, 'defender'), (juror, 'juror')]:
        join(judge, client, case_id, role)
    late_token = mutation(judge, 'POST', f'/api/cases/{case_id}/invites', {'role': 'juror'}).json['token']
    assert mutation(juror, 'POST', f'/api/cases/{case_id}/votes', {'choice': 'guilty'}).status_code == 409
    assert mutation(judge, 'POST', f'/api/cases/{case_id}/phase', {'phase': 'voting'}).status_code == 200
    assert mutation(late, 'POST', '/api/invites/redeem', {'token': late_token}).status_code == 409
    assert mutation(prosecutor, 'POST', f'/api/cases/{case_id}/arguments', {'body': 'Too late'}).status_code == 409
    assert mutation(judge, 'POST', f'/api/cases/{case_id}/votes', {'choice': 'guilty'}).status_code == 403
    assert mutation(juror, 'POST', f'/api/cases/{case_id}/votes', {'choice': 'guilty'}).status_code == 201
    assert mutation(juror, 'POST', f'/api/cases/{case_id}/votes', {'choice': 'not_guilty'}).status_code == 409
    judge_view = judge.get(f'/api/cases/{case_id}').json
    assert judge_view['verdict'] is None
    assert judge_view['my_vote'] is None
    assert 'votes' not in judge_view
    assert juror.get(f'/api/cases/{case_id}').json['my_vote'] == 'guilty'
    assert mutation(judge, 'POST', f'/api/cases/{case_id}/phase', {'phase': 'closed'}).status_code == 200
    verdict = judge.get(f'/api/cases/{case_id}').json['verdict']
    assert verdict == {'guilty': 1, 'not_guilty': 0, 'total': 1, 'result': 'guilty'}
    assert mutation(judge, 'POST', f'/api/cases/{case_id}/phase', {'phase': 'voting'}).status_code == 409


def test_invalid_input_does_not_mutate_database(review_app):
    judge = actor(review_app, 'judge')
    for movie_id in [True, '809', -1, 2147483648, None]:
        assert mutation(judge, 'POST', '/api/cases', {'movie_id': movie_id, 'title': 'Title', 'charge': 'Charge'}).status_code == 400
    assert judge.get('/api/cases').json == {'cases': []}
    assert mutation(judge, 'POST', '/api/cases', ['not', 'an', 'object']).status_code == 400


def test_passwords_are_scrypt_hashes(review_app):
    actor(review_app, 'reviewer')
    with review_app.app_context():
        user = db.session.scalar(select(User).where(User.username == 'reviewer'))
        assert user.password_hash.startswith('scrypt:')
        assert 'a long review password' not in user.password_hash
