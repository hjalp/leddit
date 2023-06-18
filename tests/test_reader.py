import pprint
import unittest
from unittest import mock
from unittest.mock import MagicMock

from models.models import CommunityDTO
from reddit.reader import RedditReader
from tests import get_test_data


class RedditReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.subject = RedditReader()

        # Mock the requests.Session object
        self.subject.session = mock.Mock()

        # Mock the logger
        self.subject.logger = mock.Mock()

        # Mock the _request method
        self.subject._request = mock.Mock()

    def tearDown(self):
        pass

    def test_get_subreddit_info(self):
        body = get_test_data('today_i_learned.html')
        self.subject.is_sub_nsfw = mock.Mock()

        self.subject._request.return_value = MagicMock(status_code=200, text=body)
        self.subject.is_sub_nsfw.return_value = False

        community = self.subject.get_subreddit_info('todayilearned')

        self.assertEqual(community, CommunityDTO(
            ident='todayilearned',
            title="Today I Learned (TIL)",
            description='You learn something new every day; what did you '
                        'learn today? Submit interesting and specific facts '
                        'about something that you just found out here.',
            icon="//b.thumbs.redditmedia.com/pskDeiR7LPmkU3Vq1HSBs6Y0geRbSTAQiz23AwVppbs.jpg",
            nsfw=False
        ))
        self.subject.is_sub_nsfw.assert_called_once_with('todayilearned')
        self.subject._request.assert_called_once_with('GET', 'https://old.reddit.com/r/todayilearned')

    def test_is_sub_nsfw(self):
        self.assertTrue(RedditReader.is_sub_nsfw('gonewildaudio'))

    def test_get_subreddit_ident(self):
        tests = [
            ['https://www.reddit.com/r/explainlikelimfive', 'explainlikelimfive'],
            ['/r/modsupport', 'modsupport'],
            ['http://old.reddit.com/r/redditalternatives', 'redditalternatives'],
        ]

        for link, expected in tests:
            try:
                ident = RedditReader.get_subreddit_ident(link)
            except ValueError as e:
                ident = str(e)
            self.assertEqual(expected, ident)
