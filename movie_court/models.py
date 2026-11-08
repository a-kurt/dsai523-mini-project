"""Database records. Constraints protect membership and one-person-one-vote rules."""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    charge = db.Column(db.String(1000), nullable=False)
    phase = db.Column(db.String(16), nullable=False, default='debate')
    movie = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (CheckConstraint("phase IN ('debate','voting','closed')"),)


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    # Only one judge, prosecutor and defender; jurors have a NULL slot.
    slot = db.Column(db.String(16), nullable=True)
    __table_args__ = (
        UniqueConstraint('case_id', 'user_id'), UniqueConstraint('case_id', 'slot'),
        CheckConstraint("role IN ('judge','prosecutor','defender','juror')"),
        CheckConstraint("(role = 'juror' AND slot IS NULL) OR (role <> 'juror' AND slot = role)"),
    )


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    role = db.Column(db.String(16), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked = db.Column(db.Boolean, nullable=False, default=False)


class Argument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(4000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    choice = db.Column(db.String(16), nullable=False)
    __table_args__ = (UniqueConstraint('case_id', 'user_id'), CheckConstraint("choice IN ('guilty','not_guilty')"))
