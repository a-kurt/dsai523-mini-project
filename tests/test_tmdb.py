"""TMDB failure handling uses mocked HTTP, not paid or flaky network requests."""
from unittest.mock import Mock
import pytest
import requests
from werkzeug.exceptions import BadGateway, ServiceUnavailable
from movie_court import tmdb


def test_missing_token(app):
    with app.app_context(), pytest.raises(ServiceUnavailable):
        tmdb.search_movies('Shrek')


def test_search_and_detail_use_bearer_and_timeout(app, monkeypatch):
    app.config['TMDB_READ_TOKEN'] = 'test-only-token'
    response = Mock()
    response.json.return_value = {'results': [{'id': 809, 'title': 'Shrek 2', 'poster_path': '/poster.jpg'}]}
    get = Mock(return_value=response)
    monkeypatch.setattr('movie_court.tmdb.requests.get', get)
    with app.app_context():
        results = tmdb.search_movies('Shrek')
    assert results[0]['title'] == 'Shrek 2'
    assert get.call_args.kwargs['headers'] == {'Authorization': 'Bearer test-only-token'}
    assert get.call_args.kwargs['timeout'] == (3, 10)
    assert get.call_args.kwargs['params']['include_adult'] == 'false'


@pytest.mark.parametrize('failure', [requests.Timeout(), requests.ConnectionError(), ValueError()])
def test_upstream_failure(app, monkeypatch, failure):
    app.config['TMDB_READ_TOKEN'] = 'test-only-token'
    monkeypatch.setattr('movie_court.tmdb.requests.get', Mock(side_effect=failure))
    with app.app_context(), pytest.raises(BadGateway):
        tmdb.request_tmdb('movie/809')


def test_invalid_upstream_data(app, monkeypatch):
    app.config['TMDB_READ_TOKEN'] = 'test-only-token'
    response = Mock()
    response.json.return_value = {'results': None}
    monkeypatch.setattr('movie_court.tmdb.requests.get', Mock(return_value=response))
    with app.app_context(), pytest.raises(BadGateway):
        tmdb.search_movies('Shrek')
