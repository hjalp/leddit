import re
from datetime import datetime
from typing import List, Optional

import feedparser
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
from requests import Session as HttpSession, HTTPError

from src.models.models import PostDTO

_SUBREDDIT_REGEX = re.compile(r'path.com/r/([^/]+)/.*')
_STRIP_EMPTY_REGEX = re.compile(r'\n{3,}')

SORT_HOT = 'hot'
SORT_NEW = 'new'


def get_subreddit_topics(subreddit: str, session: HttpSession, mode: str = SORT_HOT,
                         since: Optional[datetime] = None) -> List[PostDTO]:
    if mode == SORT_NEW:
        feed_url = f"https://www.reddit.com/r/{subreddit}/new/.rss?sort=new"
    else:
        feed_url = f"https://www.reddit.com/r/{subreddit}/.rss"

    feed = feedparser.parse(session.get(feed_url).text)

    posts = []
    for entry in feed.entries:
        created = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%S%z")
        updated = datetime.strptime(entry.updated, "%Y-%m-%dT%H:%M:%S%z")
        if not since or updated > since:
            posts.append(
                PostDTO(reddit_link=entry.link, title=entry.title, created=created, updated=updated,
                        author=entry.author))
    return posts


def get_post_details(post: PostDTO, session: HttpSession) -> PostDTO:
    old_url = post.reddit_link.replace('www', 'old')
    response = session.get(old_url)

    if 'over18' in response.url:
        response = session.post(response.url, {'over18': 'yes'})

    if response.status_code != 200:
        raise HTTPError("Couldn't retrieve post detail page")

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract the body text if it exists
    body_text = soup.select_one('.expando form .md')
    post.body = html_node_to_markdown(body_text) if body_text else None

    # Extract other properties
    post_info = soup.select_one('div[data-timestamp][data-author][data-nsfw]')
    post.nsfw = post_info['data-nsfw'] != 'false'
    post.external_link = None if post_info['data-url'].startswith('/r/') else post_info['data-url']

    return post


def get_subreddit_ident(link: str) -> str:
    """Extract the subreddit string from a path post"""
    match = _SUBREDDIT_REGEX.search(link)
    if match:
        return match.group(1)
    else:
        raise ValueError("No subreddit found in the reddit_link")


def html_node_to_markdown(source: Tag) -> Optional[str]:
    """Convert the contents of a BeautifulSoup tag into markdown"""
    html = str(source).replace('\u200B', '')
    markdown = markdownify(html)

    return _STRIP_EMPTY_REGEX.sub('\n\n', markdown) if markdown else None
