"""Exercise real account, case, invitation, argument and voting workflows."""
from datetime import timedelta
from sqlalchemy import select
from movie_court.models import db, Invite, User, now


def test_full_courtroom_workflow(courtroom):
    cid, users = courtroom
    path = f'/api/cases/{cid}'
    judge, prosecution, defense, juror = [users[x] for x in ('judge', 'prosecutor', 'defender', 'juror')]
    assert judge.send('patch', path, {'title': 'A very serious case'}).status_code == 200
    response = prosecution.send('post', path + '/arguments', {'body': 'The soundtrack proves it.'})
    assert response.status_code == 201
    aid = response.json['argument']['id']
    assert defense.send('patch', path + f'/arguments/{aid}', {'body': 'tamper'}).status_code == 403
    assert prosecution.send('patch', path + f'/arguments/{aid}', {'body': 'Exhibit A: the soundtrack.'}).status_code == 200
    assert prosecution.send('delete', path + f'/arguments/{aid}').status_code == 204
    assert prosecution.send('post', path + '/arguments', {'body': 'Another argument.'}).status_code == 201
    assert judge.send('post', path + '/phase', {'phase': 'voting'}).status_code == 200
    assert prosecution.send('post', path + '/arguments', {'body': 'Too late'}).status_code == 409
    assert judge.send('patch', path, {'charge': 'Change the question'}).status_code == 409
    assert judge.send('post', path + '/phase', {'phase': 'closed'}).status_code == 409
    assert judge.send('post', path + '/votes', {'choice': 'guilty'}).status_code == 403
    assert juror.send('post', path + '/votes', {'choice': 'guilty'}).status_code == 201
    assert juror.send('post', path + '/votes', {'choice': 'not_guilty'}).status_code == 409
    for name in ('judge', 'prosecutor', 'defender'):
        data = users[name].get(path).json
        assert data['verdict'] is None
        assert data['my_vote'] is None
        assert 'votes' not in data
    assert juror.get(path).json['my_vote'] == 'guilty'
    assert judge.send('post', path + '/phase', {'phase': 'closed'}).status_code == 200
    assert judge.get(path).json['verdict'] == {'guilty': 1, 'not_guilty': 0, 'total': 1, 'result': 'guilty'}
    assert juror.send('post', path + '/votes', {'choice': 'guilty'}).status_code == 409
    assert judge.send('delete', path).status_code == 204
    assert judge.get(path).status_code == 404


def test_private_cases_and_permissions(courtroom):
    cid, users = courtroom
    path = f'/api/cases/{cid}'
    outsider = users['outsider']
    assert outsider.get('/api/cases').json == {'cases': []}
    for method, suffix, data in [('get', '', None), ('patch', '', {'title': 'steal'}),
        ('delete', '', None), ('post', '/votes', {'choice': 'guilty'}),
        ('post', '/invites', {'role': 'juror'}), ('post', '/arguments', {'body': 'spam'})]:
        assert outsider.send(method, path + suffix, data).status_code == 404
    assert users['juror'].send('post', path + '/invites', {'role': 'juror'}).status_code == 403
    assert users['juror'].send('post', path + '/phase', {'phase': 'voting'}).status_code == 403
    assert users['juror'].send('post', path + '/arguments', {'body': 'spam'}).status_code == 403
    assert users['prosecutor'].send('delete', path).status_code == 403


def test_invite_hash_expiry_revocation_reuse(app, courtroom):
    cid, users = courtroom
    path = f'/api/cases/{cid}/invites'
    judge, outsider = users['judge'], users['outsider']
    token = judge.send('post', path, {'role': 'juror'}).json['token']
    with app.app_context():
        invitation = db.session.scalar(select(Invite).order_by(Invite.id.desc()))
        assert token not in invitation.token_hash
        assert len(invitation.token_hash) == 64
        invitation.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert outsider.send('post', '/api/invites/redeem', {'token': token}).status_code == 400
    token = judge.send('post', path, {'role': 'juror'}).json['token']
    assert judge.send('delete', path).status_code == 204
    assert outsider.send('post', '/api/invites/redeem', {'token': token}).status_code == 400
    token = judge.send('post', path, {'role': 'juror'}).json['token']
    assert outsider.send('post', '/api/invites/redeem', {'token': token}).status_code == 201
    assert users['defender'].send('post', '/api/invites/redeem', {'token': token}).status_code in (400, 409)
    assert judge.send('post', path, {'role': 'prosecutor'}).status_code == 409
    assert judge.send('post', path, {'role': 'judge'}).status_code == 400


def test_auth_csrf_and_headers(app):
    client = app.test_client()
    assert client.post('/api/auth/register', json={'username': 'newuser', 'password': 'long enough password'}).status_code == 403
    csrf = client.get('/api/auth/me').json['csrf_token']
    response = client.post('/api/auth/register', json={'username': 'newuser', 'password': 'long enough password'}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 201
    assert 'HttpOnly' in response.headers['Set-Cookie']
    assert 'SameSite=Lax' in response.headers['Set-Cookie']
    assert response.headers['Cache-Control'] == 'no-store'
    with app.app_context():
        assert db.session.scalar(select(User)).password_hash.startswith('scrypt:')
        assert 'long enough password' not in db.session.scalar(select(User)).password_hash
    assert client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf}).status_code == 403
    csrf = client.get('/api/auth/me').json['csrf_token']
    assert client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf}).status_code == 204
    assert client.get('/api/cases').status_code == 401
    csrf = client.get('/api/auth/me').json['csrf_token']
    assert client.post('/api/auth/login', json={'username': 'newuser', 'password': 'wrong'}, headers={'X-CSRF-Token': csrf}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'newuser', 'password': 'long enough password'}, headers={'X-CSRF-Token': csrf}).status_code == 200


def test_phase_requires_members_and_order(actors):
    judge = actors['judge']
    cid = judge.send('post', '/api/cases', {'movie_id': 809, 'title': 'Case', 'charge': 'A charge'}).json['case']['id']
    path = f'/api/cases/{cid}'
    assert judge.send('post', path + '/phase', {'phase': 'voting'}).status_code == 409
    assert judge.send('post', path + '/phase', {'phase': 'closed'}).status_code == 409
    assert judge.send('post', path + '/votes', {'choice': 'guilty'}).status_code == 403


def test_validation_and_movie_failure(actors, monkeypatch):
    judge = actors['judge']
    for movie_id in (True, -1, '809', None):
        assert judge.send('post', '/api/cases', {'movie_id': movie_id, 'title': 'Case', 'charge': 'Charge'}).status_code == 400
    assert judge.send('post', '/api/cases', {'movie_id': 809, 'title': 'x' * 121, 'charge': 'Charge'}).status_code == 400
    from werkzeug.exceptions import BadGateway
    def unavailable(movie_id):
        raise BadGateway('Movie service unavailable.')
    monkeypatch.setattr('movie_court.tmdb.get_movie', unavailable)
    assert judge.send('post', '/api/cases', {'movie_id': 809, 'title': 'Case', 'charge': 'Charge'}).status_code == 502
    assert judge.get('/api/cases').json == {'cases': []}


def test_data_persists_between_sessions(app, courtroom):
    cid, users = courtroom
    fresh_client = app.test_client()
    csrf = fresh_client.get('/api/auth/me').json['csrf_token']
    response = fresh_client.post('/api/auth/login', json={'username': 'judge', 'password': 'correct horse battery'}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    assert fresh_client.get(f'/api/cases/{cid}').json['case']['movie']['title'] == 'Shrek 2'


def test_password_spaces_are_not_silently_removed(app):
    client = app.test_client()
    def send(path, data):
        csrf = client.get('/api/auth/me').json['csrf_token']
        return client.post(path, json=data, headers={'X-CSRF-Token': csrf})
    assert send('/api/auth/register', {'username': 'spaces', 'password': ' exact secret phrase '}).status_code == 201
    assert send('/api/auth/logout', {}).status_code == 204
    assert send('/api/auth/login', {'username': 'spaces', 'password': 'exact secret phrase'}).status_code == 401
    assert send('/api/auth/login', {'username': 'spaces', 'password': ' exact secret phrase '}).status_code == 200
