"""Small TMDB client. Never send the service token to the browser."""
import requests
from flask import current_app
from werkzeug.exceptions import BadGateway, ServiceUnavailable


def request_tmdb(path, **params):
    token = current_app.config.get('TMDB_READ_TOKEN')
    if not token:
        raise ServiceUnavailable('Movie search needs a TMDB read access token. Ask the app owner to configure it.')
    try:
        response = requests.get(
            'https://api.themoviedb.org/3/' + path,
            params=params, headers={'Authorization': 'Bearer ' + token}, timeout=(3, 10),
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError('Invalid response')
        return data
    except (requests.RequestException, ValueError):
        raise BadGateway('The movie service is unavailable. Please try again later.') from None


def movie_data(data):
    """Store only the fields the application needs, not arbitrary upstream data."""
    if not isinstance(data, dict) or not isinstance(data.get('id'), int) or not isinstance(data.get('title'), str):
        raise BadGateway('The movie service returned an invalid movie.')
    poster = data.get('poster_path')
    if not isinstance(poster, str) or not poster.startswith('/') or poster.startswith('//'):
        poster = None
    return {
        'id': data['id'], 'title': data['title'][:300],
        'release_date': str(data.get('release_date') or '')[:10],
        'overview': str(data.get('overview') or '')[:5000], 'poster_path': poster,
    }


def search_movies(query):
    data = request_tmdb('search/movie', query=query, include_adult='false')
    results = data.get('results')
    if not isinstance(results, list):
        raise BadGateway('The movie service returned an invalid search result.')
    return [movie_data(item) for item in results[:20]]


def get_movie(movie_id):
    return movie_data(request_tmdb(f'movie/{movie_id}'))
