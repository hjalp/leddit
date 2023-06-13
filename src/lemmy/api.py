import time
from typing import Dict, Optional

import jwt
import requests


class LemmyAPI:
    _API_VERSION_: str = 'v3'

    def __init__(self, base_url: str, username: str = None, password: str = None):
        self.base_url: str = base_url
        self.__username: str = username
        self.__password: str = password
        self.__jwt: str = ''

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                      auth_required: bool = True) -> Dict:
        url = f'{self.base_url}/api/{self._API_VERSION_}{endpoint}'
        headers = {'Content-Type': 'application/json'}
        data = {} if not data else data

        if auth_required:
            self.update_auth()
            data['auth'] = self.__jwt

        response = requests.request(method, url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def login(self):
        response = self._make_request('POST', '/user/login',
                                      {'username_or_email': self.__username, 'password': self.__password},
                                      auth_required=False)
        if not response['jwt']:
            raise RuntimeError("Could not login", response)
        self.__jwt = response['jwt']

    def create_post(self, community_id: int, name: str, body: Optional[str] = None, url: Optional[str] = None,
                    nsfw: bool = False, language_id: int = None) -> Dict:
        data = {'community_id': community_id, 'name': name}

        self.__update_payload({'body': body, 'url': url, 'nsfw': nsfw, 'language_id': language_id}, data)

        return self._make_request('POST', '/post', data, auth_required=True)

    def create_community(self, name: str, title: str, description: str = None, icon: str = None, nsfw: bool = False,
                         posting_restricted_to_mods: bool = True):
        data = {'name': name, 'title': title}
        self.__update_payload(
            {'description': description, 'icon': icon, 'nsfw': nsfw,
             'posting_restricted_to_mods': posting_restricted_to_mods},
            data
        )

        return self._make_request('POST', '/community', data, auth_required=True)

    def get_info(self):
        """Returns"""
        return self._make_request('GET', '/site', auth_required=False)

    def update_auth(self):
        """Updates the authentication token if empty or near expiring."""
        if self.__jwt == '' or self.__is_token_near_expiry():
            self.login()

    def __is_token_near_expiry(self) -> bool:
        if self.__jwt is None:
            return True
        decoded_token = jwt.decode(self.__jwt, algorithms=['HS256'], options={"verify_signature": False})
        current_timestamp = int(time.time())
        return decoded_token['iat'] - current_timestamp < 300

    def __update_payload(self, optionals: dict, payload: dict) -> dict:
        for key, value in optionals.items():
            if value is not None:
                payload[key] = value
        return payload
