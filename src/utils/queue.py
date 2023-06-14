import logging
import time
from datetime import datetime
from operator import attrgetter
from typing import Type, List

import click
from sqlalchemy.orm import Session as DbSession

from lemmy.api import LemmyAPI
from models.models import Community, PostDTO, Post
from reddit.reader import RedditReader, SORT_HOT

_DELAY_TIME = 6  # delay between RSS requests in seconds


# TODO: Work on a tick-basis

class Syncer:
    def __init__(self, db: DbSession, reddit_reader: RedditReader, lemmy: LemmyAPI):
        self._db: DbSession = db
        self._reddit_reader: RedditReader = reddit_reader
        self._lemmy: LemmyAPI = lemmy
        self._logger = logging.getLogger(__name__)

    def get_community_scrape_queue(self) -> list[Type[Community]]:
        """Get a batch of communities that are due for scraping."""
        return self._db.query(Community).all()

    def run_scraper(self):
        communities = self.get_community_scrape_queue()  # just grab one plox

        for index, community in enumerate(communities):
            self._logger.info(f'Scraping subreddit: {community.ident}')
            posts = self._reddit_reader.get_subreddit_topics(community.ident, mode=SORT_HOT)
            posts = self.filter_posted(posts)

            # Handle oldest entries first.
            posts = sorted(posts, key=attrgetter('updated'))

            for post in posts:
                click.echo(post)
                post = self._reddit_reader.get_post_details(post)
                self.clone_to_lemmy(post, community)

            self._logger.info(f'Done.')
            community.last_scrape = datetime.utcnow()
            self._db.add(community)
            self._db.commit()

    def filter_posted(self, posts: List[PostDTO]) -> List[PostDTO]:
        """Filter out any posts that have already been synced to Lemmy"""
        reddit_links = [post.reddit_link for post in posts]
        existing_links = self._db.query(Post.reddit_link).filter(Post.reddit_link.in_(reddit_links)).all()
        existing_links = [link[0] for link in existing_links]

        filtered_posts = [post for post in posts if post.reddit_link not in existing_links]
        return filtered_posts

    def clone_to_lemmy(self, post: PostDTO, community: Community):
        try:
            lemmy_post = self._lemmy.create_post(
                community_id=community.lemmy_id,
                name=post.title,
                body=post.body,
                url=post.external_link,
                nsfw=post.nsfw
            )
        except Exception as e:
            print(f"Something went horribly wrong when parsing {post.reddit_link}: {str(e)}")
            return

        # Save post
        try:
            db_post = Post(reddit_link=post.reddit_link, lemmy_link=lemmy_post['post_view']['post']['ap_id'],
                           community=community, updated=datetime.utcnow(), nsfw=post.nsfw)
            self._db.add(db_post)
            self._db.commit()
        except Exception as e:
            print(f"Couldn't save {post.reddit_link} to local database. MUST REMOVE FROM LEMMY OR ELSE. {str(e)}")
