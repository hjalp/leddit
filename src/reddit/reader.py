import logging
import re
import time
from datetime import datetime
from typing import List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify
from requests import HTTPError

from models.models import PostDTO, SORT_HOT, SORT_NEW, CommentDTO
from utils.config import USER_AGENT, REQUEST_INTERVAL

class RedditReader:
    _SUBREDDIT_REGEX = re.compile(r'(.*reddit\.com/|^/?)r/([^/]+).*')
    _STRIP_EMPTY_REGEX = re.compile(r'\n{3,}')
    _next_request_after: int  # Updated on requests to reddit to prevent throttling

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self._next_request_after = 0
        self.logger: logging.Logger = logging.getLogger(__name__)

    def _request(self, *args, allow_recurse=True, **kwargs):
        now = time.time()
        if now < self._next_request_after:
            self.logger.debug('Delaying next request')
            time.sleep(self._next_request_after - now)
        self._next_request_after = int(time.time()) + REQUEST_INTERVAL
        response = self.session.request(*args, **kwargs)
        if 'over18' in response.url:
            if not allow_recurse:
                raise RecursionError('Reddit is trying to throw us into an infinite loop :(')
            response = self._request('POST', response.url, {'over18': 'yes'}, allow_recurse=False)

        return response

    def get_subreddit_topics(self, subreddit: str, mode: str = SORT_NEW, since: datetime = None) -> List[PostDTO]:
        """Get a topics from a subreddit through its RSS feed"""
        if mode == SORT_NEW:
            feed_url = f"https://www.reddit.com/r/{subreddit}/new/.rss?sort=new"
        else:
            feed_url = f"https://www.reddit.com/r/{subreddit}/.rss"

        feed = feedparser.parse(self._request('GET', feed_url).text)

        posts = []
        for entry in feed.entries:
            created = datetime.fromisoformat(entry.published)
            updated = datetime.fromisoformat(entry.updated)
            author = entry.author if 'author' in entry else '[deleted]'
            if not since or updated > since:
                posts.append(PostDTO(reddit_link=entry.link, title=entry.title, created=created, updated=updated,
                                     author=author))
        return posts

    def get_post_details(self, post: PostDTO) -> tuple[PostDTO, List[CommentDTO]]:
        """Enrich a PostDTO with all available extra data and retrieve comments"""
        old_url = post.reddit_link.replace('www', 'old')
        response = self._request('GET', old_url)

        if response.status_code != 200:
            raise HTTPError("Couldn't retrieve post detail page")

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract the body text if it exists
        body_text = soup.select_one('.expando form .md')
        post.body = self._html_node_to_markdown(body_text) if body_text else None

        # Extract other properties
        post_info = soup.select_one('div[data-timestamp][data-nsfw]')
        post.nsfw = post_info['data-nsfw'] != 'false'
        post.external_link = None if post_info['data-url'].startswith('/r/') else post_info['data-url']

        # Extract all (visible) comments
        comments = self.get_comment_details(soup)

        return post, comments

    def get_comment_details(self, soup: BeautifulSoup) -> List[CommentDTO]:
        """Retrieve comments sorted by parent"""
        comment_threads = soup.select('.sitetable')
        post_id = comment_threads[1]['id'].split('_')[2]

        # Create tags for deleted accounts
        deleted = BeautifulSoup('<a></a>', "html.parser")
        deleted.string = "[deleted]"
        deleted_body = BeautifulSoup(
            '<div class="md"><p><em>This comment was deleted before it could be archived.</em></p></div>', "html.parser"
            )
        deleted_id = deleted
        deleted_id['name'] = 'deleted'

        comments = []

        for sitetable in comment_threads[1:]: # Skip first sitetable (represents the whole page, has no comments)
            comment_index = 0

            try:
                parent = sitetable['id'].split('_')[2]
            # Resolve broken sitetables caused by deleted comments
            except IndexError:
                parent = post_id
                # deleted_warning = '**This comment was deleted before it could be archived.**\n\n'

            # Enhance comment author identification to resolve deleted accounts without the author class
            comments_author = []
            taglines = soup.select('#' + sitetable['id'] + ' > div > div > .tagline')
            for tagline in taglines:

                # Ignore "show more comments" taglines (Their comment data is not fetched)
                if tagline.select_one('span') == None:
                    continue

                author = tagline.select('.author') if tagline.select('.author') != [] else [deleted]
                comments_author.append(author)

            # Extract attributes of all comments in the sitetable
            comments_body = soup.select('#' + sitetable['id'] + ' > div > div > form .md')
            comments_created = soup.select('#' + sitetable['id'] + ' > div > div > .tagline time')
            comments_id = soup.select('#' + sitetable['id'] + ' > div > .parent a')

            if len(comments_body) != len(comments_author) and [deleted] in comments_author:
                for index, author in enumerate(comments_author):
                    if author == [deleted]:
                        print(index)
                        comments_body.insert(index, deleted_body)
                        comments_id.insert(index, deleted_id)

            for child in comments_id:
                comment_author = comments_author[comment_index][0]
                comment_body =  comments_body[comment_index]
                comment_created = comments_created[comment_index]
                comment_index += 1

                # Format attributes and remove HTML tags
                id = child['name'] # Comment ID on Reddit
                created = datetime.fromisoformat(comment_created['datetime'])
                author = comment_author.contents[0]
                body = self._html_node_to_markdown(comment_body)

                comments.append(CommentDTO(id=id, created=created, author=author, body=body, parent=parent, post_id=post_id))

        return comments

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

