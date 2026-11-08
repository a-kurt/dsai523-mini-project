"""Create the Movie Court app and configure its database and browser security."""
import os
import secrets
import sqlite3
import click
from flask import Flask, jsonify, render_template
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db


@event.listens_for(Engine, 'connect')
def sqlite_foreign_keys(connection, _):
    if isinstance(connection, sqlite3.Connection):
        connection.execute('PRAGMA foreign_keys=ON')


def create_app(config=None):
    app = Flask(__name__)
    production = os.environ.get('APP_ENV') == 'production'
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url and database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY') or (None if production else secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=database_url or (None if production else 'sqlite:///movie_court.sqlite'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={'pool_pre_ping': True},
        TMDB_READ_TOKEN=os.environ.get('TMDB_READ_TOKEN', ''),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=production, MAX_CONTENT_LENGTH=32 * 1024,
        INVITE_TTL_SECONDS=int(os.environ.get('INVITE_TTL_SECONDS', '3600')), PERMANENT_SESSION_LIFETIME=28800,
    )
    if config:
        app.config.update(config)
    if not 1 <= app.config['INVITE_TTL_SECONDS'] <= 604800:
        raise RuntimeError('INVITE_TTL_SECONDS must be between 1 and 604800.')
    if not app.config['SECRET_KEY'] or not app.config['SQLALCHEMY_DATABASE_URI']:
        raise RuntimeError('Set SECRET_KEY and DATABASE_URL before starting production.')
    if production and len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Use a random SECRET_KEY of at least 32 characters.')
    if os.environ.get('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1)
    db.init_app(app)
    from .api import api
    app.register_blueprint(api)

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/health')
    @app.get('/healthz')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(status='unavailable'), 503
        return jsonify(status='ok')

    @app.cli.command('init-db')
    def init_db():
        """Create missing tables for the initial schema. Never drop existing data."""
        db.create_all()
        click.echo('Database tables are ready. Existing data was kept.')

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = jsonify(error=error.description)
        response.status_code = error.code
        for key, value in error.get_headers():
            if key.lower() in ('retry-after', 'allow', 'www-authenticate'):
                response.headers[key] = value
        return response

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error='This action conflicts with an existing record. Refresh and try again.'), 409

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error('Database operation failed (%s).', type(error).__name__)
        return jsonify(error='The database is unavailable. Please try again later.'), 503

    @app.after_request
    def browser_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' https://image.tmdb.org data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if response.mimetype == 'application/json':
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app
