import re
from datetime import datetime
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
from requests import HTTPError

from models.models import PostDTO
from reddit import USER_AGENT

SORT_HOT = 'hot'
SORT_NEW = 'new'


class RedditReader:
    _SUBREDDIT_REGEX = re.compile(r'path.com/r/([^/]+)/.*')
    _STRIP_EMPTY_REGEX = re.compile(r'\n{3,}')

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def get_subreddit_topics(self, subreddit: str, mode: str = SORT_HOT, since: datetime = None) -> List[PostDTO]:
        """Get a topics from a subreddit through its RSS feed"""
        if mode == SORT_NEW:
            feed_url = f"https://www.reddit.com/r/{subreddit}/new/.rss?sort=new"
        else:
            feed_url = f"https://www.reddit.com/r/{subreddit}/.rss"

        feed = feedparser.parse(self.session.get(feed_url).text)

        posts = []
        for entry in feed.entries:
            created = datetime.fromisoformat(entry.published)
            updated = datetime.fromisoformat(entry.updated)
            if not since or updated > since:
                posts.append(
                    PostDTO(reddit_link=entry.link, title=entry.title, created=created, updated=updated,
                            author=entry.author))
        return posts

    def get_post_details(self, post: PostDTO) -> PostDTO:
        """Enrich a PostDTO with all available extra data"""
        old_url = post.reddit_link.replace('www', 'old')
        response = self.session.get(old_url)

        if 'over18' in response.url:
            response = self.session.post(response.url, {'over18': 'yes'})

        if response.status_code != 200:
            raise HTTPError("Couldn't retrieve post detail page")

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract the body text if it exists
        body_text = soup.select_one('.expando form .md')
        post.body = self._html_node_to_markdown(body_text) if body_text else None

        # Extract other properties
        post_info = soup.select_one('div[data-timestamp][data-author][data-nsfw]')
        post.nsfw = post_info['data-nsfw'] != 'false'
        post.external_link = None if post_info['data-url'].startswith('/r/') else post_info['data-url']

        return post

    @classmethod
    def get_subreddit_ident(cls, link: str) -> str:
        """Extract the subreddit string from a path post"""
        match = cls._SUBREDDIT_REGEX.search(link)
        if match:
            return match.group(1)
        else:
            raise ValueError("No subreddit found in the reddit_link")

    def _html_node_to_markdown(self, source: Tag) -> Optional[str]:
        """Convert the contents of a BeautifulSoup Tag into markdown"""
        # Make all links absolute
        for link in source.find_all('a', href=True):
            if str(link['href']).startswith('/'):
                link['href'] = 'https://old.reddit.com' + link['href']

        # Remove extraneous empty paragraphs
        html = str(source).replace('\u200B', '')
        markdown = markdownify(html)

        return self._STRIP_EMPTY_REGEX.sub('\n\n', markdown) if markdown else None
