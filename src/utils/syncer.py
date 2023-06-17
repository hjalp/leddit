import logging
from datetime import datetime, timedelta
from operator import attrgetter
from typing import Type, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from lemmy.api import LemmyAPI
from models.models import Community, PostDTO, Post
from reddit.reader import RedditReader


class Syncer:
    interval: int = 90  # Time between updates per subreddit

    def __init__(self, db: DbSession, reddit_reader: RedditReader, lemmy: LemmyAPI, interval: int = 300):
        self._db: DbSession = db
        self._reddit_reader: RedditReader = reddit_reader
        self._lemmy: LemmyAPI = lemmy
        self._logger = logging.getLogger(__name__)
        self.interval = interval

    def next_scrape_community(self) -> Optional[Type[Community]]:
        """Get the next community that is due for scraping."""
        return self._db.query(Community) \
            .filter(
                Community.enabled.is_(True),
                or_(
                    Community.last_scrape <= datetime.utcnow() - timedelta(seconds=self.interval),
                    Community.last_scrape.is_(None)
                )
            ) \
            .order_by(Community.last_scrape) \
            .first()

    def scrape_new_posts(self):
        community = self.next_scrape_community()

        if community:
            self._logger.info(f'Scraping subreddit: {community.ident}')
            try:
                posts = self._reddit_reader.get_subreddit_topics(community.ident, mode=community.sorting)
            except BaseException as e:
                self._logger.error(f"Error trying to retrieve topics: {str(e)}")
                return

            posts = self.filter_posted(posts)

            # Handle oldest entries first.
            posts = sorted(posts, key=attrgetter('updated'))

            for post in posts:
                self._logger.info(post)
                try:
                    post = self._reddit_reader.get_post_details(post)
                except BaseException as e:
                    self._logger.error(f"Error trying to retrieve post details, try again in a bit; {str(e)}")
                    return
                self.clone_to_lemmy(post, community)

            self._logger.info(f'Done.')
            community.last_scrape = datetime.utcnow()
            self._db.add(community)
            self._db.commit()
        else:
            self._logger.info('No community due for update')

    def filter_posted(self, posts: List[PostDTO]) -> List[PostDTO]:
        """Filter out any posts that have already been synced to Lemmy"""
        reddit_links = [post.reddit_link for post in posts]
        existing_links = self._db.query(Post.reddit_link).filter(Post.reddit_link.in_(reddit_links)).all()
        existing_links = [link[0] for link in existing_links]

        filtered_posts = [post for post in posts if post.reddit_link not in existing_links]
        return filtered_posts

    def clone_to_lemmy(self, post: PostDTO, community: Community):
        post = self.prepare_post(post, community)
        try:
            lemmy_post = self._lemmy.create_post(
                community_id=community.lemmy_id,
                name=post.title,
                body=post.body,
                url=post.external_link,
                nsfw=post.nsfw
            )
        except Exception as e:
            self._logger.error(
                f"Something went horribly wrong when parsing {post.reddit_link}: {str(e)}: {str(e.response.content)}"
            )
            return

        # Save post
        try:
            db_post = Post(reddit_link=post.reddit_link, lemmy_link=lemmy_post['post_view']['post']['ap_id'],
                           community=community, updated=datetime.utcnow(), nsfw=post.nsfw)
            self._db.add(db_post)
            self._db.commit()
        except Exception as e:
            print(f"Couldn't save {post.reddit_link} to local database. MUST REMOVE FROM LEMMY OR ELSE. {str(e)}")

    @staticmethod
    def prepare_post(post: PostDTO, community: Community) -> PostDTO:
        prefix = f"""##### This is an automated archive made by the [Lemmit Bot](https://lemmit.online/).
The original was posted on [/r/{community.ident}]({post.reddit_link.replace('https://www.', 'https://old.')}) by [{post.author}](https://old.reddit.com{post.author}) on {post.created}.\n"""
        if len(post.title) >= 200:
            prefix = prefix + f"\n**Original Title**: {post.title}\n"
            post.title = post.title[:196] + '...'

        post.body = prefix + ('***\n' + post.body if post.body else '')

        if len(post.body) > 10000:
            post.body = post.body[:9800] + '...\n***\nContent cut off. Read original on ' + post.reddit_link

        return post
