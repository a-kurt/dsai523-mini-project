"""JSON API for accounts, private movie cases, arguments and secret jury ballots."""
from datetime import timedelta
from functools import wraps
import hashlib
import re
import secrets
import time
from collections import OrderedDict, deque
from threading import Lock
from flask import Blueprint, current_app, g, jsonify, request, session
from sqlalchemy import select, update, delete
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, Unauthorized
from werkzeug.security import check_password_hash, generate_password_hash
from .models import db, User, Case, Membership, Invite, Argument, Vote, now
from . import tmdb

api = Blueprint('api', __name__, url_prefix='/api')
# This small per-worker guard supplements, but does not replace, a managed edge rate limit.
_attempts = OrderedDict()
_attempt_lock = Lock()
_dummy_hash = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest('Send a JSON object.')
    return data


def string(data, key, minimum=1, maximum=1000):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise BadRequest(f'{key.replace("_", " ").capitalize()} must be {minimum} to {maximum} characters.')
    return value.strip()


def password_value(data, minimum):
    value = data.get('password')
    if not isinstance(value, str) or not minimum <= len(value) <= 128 or not value.strip():
        raise BadRequest(f'Password must be {minimum} to 128 characters.')
    # Passwords are exact secrets: do not silently remove spaces.
    return value


def account(user):
    return {'id': user.id, 'username': user.username}


def timestamp(value):
    # SQLite drops timezone information; stored timestamps are always UTC.
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc).isoformat()


def case_data(case):
    return {'id': case.id, 'title': case.title, 'charge': case.charge, 'phase': case.phase,
            'movie': case.movie, 'created_at': timestamp(case.created_at)}


def argument_data(argument):
    user = db.session.get(User, argument.user_id)
    member = db.session.scalar(select(Membership).filter_by(case_id=argument.case_id, user_id=argument.user_id))
    return {'id': argument.id, 'user_id': user.id, 'username': user.username, 'role': member.role,
            'body': argument.body, 'created_at': timestamp(argument.created_at)}


@api.before_request
def protect_request():
    session.setdefault('csrf_token', secrets.token_urlsafe(32))
    g.user = db.session.get(User, session['user_id']) if session.get('user_id') else None
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        token = request.headers.get('X-CSRF-Token', '')
        if not secrets.compare_digest(token.encode(), session['csrf_token'].encode()):
            raise Forbidden('Your security token is missing or expired. Refresh the page and try again.')


@api.before_request
def throttle_sensitive_actions():
    """Limit common brute-force targets. Counters are local to this worker."""
    if not current_app.config.get('RATE_LIMIT_ENABLED', True):
        return
    if request.endpoint not in ('api.login', 'api.register', 'api.redeem_invite'):
        return
    key = (request.remote_addr, request.endpoint)
    instant = time.monotonic()
    with _attempt_lock:
        hits = _attempts.setdefault(key, deque())
        while hits and hits[0] <= instant - 60:
            hits.popleft()
        if len(hits) >= 20:
            from werkzeug.exceptions import TooManyRequests
            raise TooManyRequests('Too many attempts. Wait a minute and try again.', retry_after=60)
        hits.append(instant)
        _attempts.move_to_end(key)
        while len(_attempts) > 10000:
            _attempts.popitem(last=False)


def authenticated(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not g.user:
            raise Unauthorized('Please sign in first.')
        return function(*args, **kwargs)
    return wrapped


def member_case(case_id, lock=False):
    query = select(Case).where(Case.id == case_id)
    if lock:
        query = query.with_for_update()
    case = db.session.scalar(query)
    if not case:
        raise NotFound('Case not found.')
    member = db.session.scalar(select(Membership).filter_by(case_id=case_id, user_id=g.user.id))
    if not member:
        # Private cases should not reveal their existence.
        raise NotFound('Case not found.')
    return case, member


def judge(member):
    if member.role != 'judge':
        raise Forbidden('Only the judge can do this.')


def debate(case):
    if case.phase != 'debate':
        raise Conflict('This case is no longer in the debate phase.')


def sign_in(user):
    session.clear()
    session['user_id'] = user.id
    session['csrf_token'] = secrets.token_urlsafe(32)
    session.permanent = True


@api.get('/auth/me')
def me():
    return jsonify(user=account(g.user) if g.user else None, csrf_token=session['csrf_token'])


@api.post('/auth/register')
def register():
    data = body()
    username = string(data, 'username', 3, 32).lower()
    if not re.fullmatch(r'[a-z0-9_]+', username):
        raise BadRequest('Username can contain only letters, numbers and underscores.')
    password = password_value(data, 12)
    if db.session.scalar(select(User).filter_by(username=username)):
        raise Conflict('That username is already taken.')
    user = User(username=username, password_hash=generate_password_hash(password, method='scrypt'))
    db.session.add(user)
    db.session.commit()
    sign_in(user)
    return jsonify(user=account(user)), 201


@api.post('/auth/login')
def login():
    data = body()
    username = string(data, 'username', 3, 32).lower()
    password = password_value(data, 1)
    user = db.session.scalar(select(User).filter_by(username=username))
    # A fixed valid scrypt hash keeps unknown users on the password-check path.
    stored_hash = user.password_hash if user else _dummy_hash
    valid = check_password_hash(stored_hash, password)
    if not user or not valid:
        raise Unauthorized('Username or password is incorrect.')
    sign_in(user)
    return jsonify(user=account(user))


@api.post('/auth/logout')
@authenticated
def logout():
    session.clear()
    return '', 204


@api.get('/movies/search')
@authenticated
def search():
    query = string(request.args, 'q', 2, 100)
    return jsonify(movies=tmdb.search_movies(query))


@api.get('/cases')
@authenticated
def list_cases():
    cases = db.session.scalars(select(Case).join(Membership).where(Membership.user_id == g.user.id).order_by(Case.id.desc())).all()
    return jsonify(cases=[case_data(case) for case in cases])


@api.post('/cases')
@authenticated
def create_case():
    data = body()
    title, charge = string(data, 'title', 1, 120), string(data, 'charge', 1, 1000)
    movie_id = data.get('movie_id')
    if type(movie_id) is not int or movie_id < 1 or movie_id > 2147483647:
        raise BadRequest('Choose a valid movie.')
    movie = tmdb.get_movie(movie_id)
    case = Case(title=title, charge=charge, movie=movie)
    db.session.add(case)
    db.session.flush()
    db.session.add(Membership(case_id=case.id, user_id=g.user.id, role='judge', slot='judge'))
    db.session.commit()
    return jsonify(case=case_data(case)), 201


@api.get('/cases/<int:case_id>')
@authenticated
def get_case(case_id):
    case, member = member_case(case_id)
    members = db.session.scalars(select(Membership).filter_by(case_id=case.id).order_by(Membership.id)).all()
    arguments = db.session.scalars(select(Argument).filter_by(case_id=case.id).order_by(Argument.id)).all()
    my_vote = db.session.scalar(select(Vote).filter_by(case_id=case.id, user_id=g.user.id))
    verdict = None
    if case.phase == 'closed':
        choices = db.session.scalars(select(Vote.choice).filter_by(case_id=case.id)).all()
        guilty, not_guilty = choices.count('guilty'), choices.count('not_guilty')
        result = 'no_votes' if not choices else 'tie' if guilty == not_guilty else 'guilty' if guilty > not_guilty else 'not_guilty'
        verdict = {'guilty': guilty, 'not_guilty': not_guilty, 'total': len(choices), 'result': result}
    return jsonify(case=case_data(case), members=[{'user_id': m.user_id, 'username': db.session.get(User, m.user_id).username, 'role': m.role} for m in members],
                   arguments=[argument_data(a) for a in arguments], verdict=verdict,
                   my_role=member.role, my_vote=my_vote.choice if my_vote else None)


@api.patch('/cases/<int:case_id>')
@authenticated
def edit_case(case_id):
    case, member = member_case(case_id, lock=True)
    judge(member)
    debate(case)
    data = body()
    if not any(k in data for k in ('title', 'charge')):
        raise BadRequest('Provide a title or charge to update.')
    if 'title' in data:
        case.title = string(data, 'title', 1, 120)
    if 'charge' in data:
        case.charge = string(data, 'charge', 1, 1000)
    db.session.commit()
    return jsonify(case=case_data(case))


@api.delete('/cases/<int:case_id>')
@authenticated
def delete_case(case_id):
    case, member = member_case(case_id, lock=True)
    judge(member)
    db.session.delete(case)
    db.session.commit()
    return '', 204


@api.post('/cases/<int:case_id>/invites')
@authenticated
def create_invite(case_id):
    case, member = member_case(case_id, lock=True)
    judge(member)
    debate(case)
    role = body().get('role')
    if role not in ('prosecutor', 'defender', 'juror'):
        raise BadRequest('Choose prosecutor, defender or juror.')
    if role != 'juror' and db.session.scalar(select(Membership).filter_by(case_id=case_id, role=role)):
        raise Conflict('That role is already filled.')
    token = secrets.token_urlsafe(32)
    expires = now() + timedelta(seconds=current_app.config['INVITE_TTL_SECONDS'])
    db.session.add(Invite(case_id=case_id, role=role, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=expires))
    db.session.commit()
    return jsonify(token=token, expires_at=timestamp(expires)), 201


@api.delete('/cases/<int:case_id>/invites')
@authenticated
def revoke_invites(case_id):
    case, member = member_case(case_id, lock=True)
    judge(member)
    db.session.execute(update(Invite).where(Invite.case_id == case_id, Invite.used_at.is_(None)).values(revoked=True))
    db.session.commit()
    return '', 204


@api.post('/invites/redeem')
@authenticated
def redeem_invite():
    token = string(body(), 'token', 20, 200)
    digest = hashlib.sha256(token.encode()).hexdigest()
    invitation = db.session.scalar(select(Invite).filter_by(token_hash=digest))
    if not invitation:
        raise BadRequest('This invitation is invalid, expired or already used.')
    # Lock the case before changing any membership, just like phase transitions.
    case = db.session.scalar(select(Case).where(Case.id == invitation.case_id).with_for_update())
    if not case:
        raise BadRequest('This invitation is invalid, expired or already used.')
    debate(case)
    if db.session.scalar(select(Membership).filter_by(case_id=case.id, user_id=g.user.id)):
        raise Conflict('You already belong to this case.')
    if invitation.role != 'juror' and db.session.scalar(select(Membership).filter_by(case_id=case.id, role=invitation.role)):
        raise Conflict('That role is already filled.')
    # Conditional update means a token cannot be redeemed twice, including races.
    consumed = db.session.execute(update(Invite).where(
        Invite.id == invitation.id, Invite.used_at.is_(None), Invite.revoked.is_(False), Invite.expires_at > now(),
    ).values(used_at=now()).execution_options(synchronize_session=False))
    if consumed.rowcount != 1:
        raise BadRequest('This invitation is invalid, expired or already used.')
    db.session.add(Membership(case_id=case.id, user_id=g.user.id, role=invitation.role,
                              slot=invitation.role if invitation.role != 'juror' else None))
    db.session.commit()
    return jsonify(case_id=case.id, role=invitation.role), 201


def advocate(case, member):
    debate(case)
    if member.role not in ('prosecutor', 'defender'):
        raise Forbidden('Only the prosecutor and defender can post arguments.')


@api.post('/cases/<int:case_id>/arguments')
@authenticated
def add_argument(case_id):
    case, member = member_case(case_id, lock=True)
    advocate(case, member)
    argument = Argument(case_id=case.id, user_id=g.user.id, body=string(body(), 'body', 1, 4000))
    db.session.add(argument)
    db.session.commit()
    return jsonify(argument=argument_data(argument)), 201


def own_argument(case_id, argument_id):
    case, member = member_case(case_id, lock=True)
    advocate(case, member)
    argument = db.session.scalar(select(Argument).filter_by(id=argument_id, case_id=case_id))
    if not argument:
        raise NotFound('Argument not found.')
    if argument.user_id != g.user.id:
        raise Forbidden('You can only change your own arguments.')
    return argument


@api.patch('/cases/<int:case_id>/arguments/<int:argument_id>')
@authenticated
def edit_argument(case_id, argument_id):
    argument = own_argument(case_id, argument_id)
    argument.body = string(body(), 'body', 1, 4000)
    db.session.commit()
    return jsonify(argument=argument_data(argument))


@api.delete('/cases/<int:case_id>/arguments/<int:argument_id>')
@authenticated
def delete_argument(case_id, argument_id):
    db.session.delete(own_argument(case_id, argument_id))
    db.session.commit()
    return '', 204


@api.post('/cases/<int:case_id>/phase')
@authenticated
def change_phase(case_id):
    case, member = member_case(case_id, lock=True)
    judge(member)
    target = body().get('phase')
    if case.phase == 'debate' and target == 'voting':
        roles = set(db.session.scalars(select(Membership.role).filter_by(case_id=case_id)).all())
        if not {'prosecutor', 'defender', 'juror'} <= roles:
            raise Conflict('Add a prosecutor, defender and at least one juror before voting.')
    elif case.phase == 'voting' and target == 'closed':
        if not db.session.scalar(select(Vote.id).filter_by(case_id=case_id).limit(1)):
            raise Conflict('At least one juror must vote before closing the case.')
    else:
        raise Conflict('Cases move from debate to voting, then to closed.')
    case.phase = target
    db.session.commit()
    return jsonify(case=case_data(case))


@api.post('/cases/<int:case_id>/votes')
@authenticated
def cast_vote(case_id):
    case, member = member_case(case_id, lock=True)
    if member.role != 'juror':
        raise Forbidden('Only assigned jurors can vote.')
    if case.phase != 'voting':
        raise Conflict('Voting is not open.')
    choice = body().get('choice')
    if choice not in ('guilty', 'not_guilty'):
        raise BadRequest('Choose guilty or not_guilty.')
    if db.session.scalar(select(Vote).filter_by(case_id=case_id, user_id=g.user.id)):
        raise Conflict('You have already voted. Votes cannot be changed.')
    db.session.add(Vote(case_id=case_id, user_id=g.user.id, choice=choice))
    db.session.commit()
    return jsonify(message='Your secret ballot was recorded.'), 201
