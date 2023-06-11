from typing import Dict, Optional

import requests


class LemmyAPI:
    _API_VERSION_: str = 'v3'

    def __init__(self, base_url: str):
        self.base_url = base_url

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, str]] = None) -> Dict:
        url = f'{self.base_url}/api/{self._API_VERSION_}{endpoint}'
        headers = {'Content-Type': 'application/json'}
        response = requests.request(method, url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def login(self, username, password) -> Dict:
        return self._make_request('POST', '/login', {'username_or_email': username, 'password': password})

    def create_post(self, community_id: int, title: str, content: str) -> Dict:
        endpoint = '/api/v3/posts'
        data = {'community_id': community_id, 'title': title, 'body': content}
        return self._make_request('POST', endpoint, data)

    def create_community(self, name: str):
        pass
