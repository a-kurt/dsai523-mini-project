"""Real PostgreSQL race checks. SQLite cannot verify row-level locking."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
import pytest
from sqlalchemy import select
from conftest import Actor
from movie_court.models import db, Invite, Membership, Vote

pytestmark = pytest.mark.skipif(
    not os.environ.get('TEST_DATABASE_URL', '').startswith(('postgresql', 'postgres:')),
    reason='Set TEST_DATABASE_URL to a disposable PostgreSQL database to test row locks.',
)


def race(first, second):
    """Release two independent HTTP clients at once and collect both responses."""
    barrier = Barrier(2)
    def invoke(action):
        barrier.wait(timeout=10)
        return action()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(invoke, action) for action in (first, second)]
        return [future.result(timeout=20) for future in futures]


def test_invite_can_only_be_consumed_once_under_race(app, courtroom):
    cid, users = courtroom
    other = Actor(app, 'second_candidate')
    token = users['judge'].send('post', f'/api/cases/{cid}/invites', {'role': 'juror'}).json['token']
    responses = race(
        lambda: users['outsider'].send('post', '/api/invites/redeem', {'token': token}),
        lambda: other.send('post', '/api/invites/redeem', {'token': token}),
    )
    assert sorted(response.status_code for response in responses) == [201, 400]
    with app.app_context():
        candidate_ids = (users['outsider'].id, other.id)
        joined = db.session.scalars(select(Membership).where(
            Membership.case_id == cid, Membership.user_id.in_(candidate_ids))).all()
        assert len(joined) == 1
        invitation = db.session.scalar(select(Invite).order_by(Invite.id.desc()))
        assert invitation.used_at is not None


def test_juror_can_only_vote_once_under_race(app, courtroom):
    cid, users = courtroom
    # A separate browser session for the same user, not a shared test client.
    second_browser = Actor.__new__(Actor)
    second_browser.client = app.test_client()
    second_browser.token = second_browser.client.get('/api/auth/me').json['csrf_token']
    login = second_browser.send('post', '/api/auth/login', {'username': 'juror', 'password': 'correct horse battery'})
    assert login.status_code == 200
    second_browser.refresh()
    path = f'/api/cases/{cid}'
    assert users['judge'].send('post', path + '/phase', {'phase': 'voting'}).status_code == 200
    responses = race(
        lambda: users['juror'].send('post', path + '/votes', {'choice': 'guilty'}),
        lambda: second_browser.send('post', path + '/votes', {'choice': 'not_guilty'}),
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    with app.app_context():
        votes = db.session.scalars(select(Vote).filter_by(case_id=cid)).all()
        assert len(votes) == 1
    assert users['judge'].get(path).json['verdict'] is None
