import logging
import time
from datetime import datetime, timedelta
from operator import attrgetter
from typing import Type, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from lemmy.api import LemmyAPI
from models.models import Community, PostDTO, Post, CommunityDTO, SORT_HOT
from reddit.reader import RedditReader

NEW_SUB_CHECK_INTERVAL: int = 60


class Syncer:
    interval: int = 120  # Time between updates per subreddit
    new_sub_check: int = None  # Time between check for new subreddit requests

    def __init__(self, db: DbSession, reddit_reader: RedditReader, lemmy: LemmyAPI, interval: int = 120,
                 request_community: str = None):
        self._db: DbSession = db
        self._reddit_reader: RedditReader = reddit_reader
        self._lemmy: LemmyAPI = lemmy
        self._logger = logging.getLogger(__name__)
        self.interval = interval
        self.request_community = request_community

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
            self._logger.debug('No community due for update')

    def filter_posted(self, posts: List[PostDTO]) -> List[PostDTO]:
        """Filter out any posts that have already been synced to Lemmy"""
        reddit_links = [post.reddit_link for post in posts]
        existing_links_raw = self._db.query(Post.reddit_link).filter(Post.reddit_link.in_(reddit_links)).all()
        existing_links = [link[0] for link in existing_links_raw]

        # filtered_posts = [post for post in posts if post.reddit_link not in existing_links]
        filtered_posts = []
        for post in posts:
            if post.reddit_link not in existing_links:
                filtered_posts.append(post)
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

    def check_new_subs(self):
        if self.new_sub_check is not None and (self.new_sub_check + NEW_SUB_CHECK_INTERVAL) > time.time():
            self._logger.debug('Not time yet for subreddit request check')
            return
        self._logger.info('Checking for new subreddit requests...')

        posts = self._get_new_sub_requests()
        for post in posts:
            self._logger.info('New subreddit request received')
            community = self._answer_sub_request(post)
            if community:
                lemmy_community = self._lemmy.create_community(
                    name=community.ident,
                    title=community.title,
                    description=community.description,
                    icon=community.icon,
                    nsfw=community.nsfw,
                    posting_restricted_to_mods=True
                )
                db_community = Community(
                    lemmy_id=lemmy_community['community_view']['community']['id'],
                    ident=community.ident,
                    nsfw=community.nsfw,
                    enabled=True,
                    sorting=SORT_HOT
                )
                self._db.add(db_community)
                self._db.commit()

                self._lemmy.create_comment(
                    post_id=post['post']['id'],
                    content=f"I'll get right on that. Check out [/c/{community.ident}](/c/{community.ident})!"
                )
                self._lemmy.mark_post_as_read(post_id=post['post']['id'], read=True)
        self.new_sub_check = int(time.time())

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

    def _get_new_sub_requests(self):
        posts = self._lemmy.get_posts(community_name=self.request_community, auth_required=True)

        ret_posts = []

        for post in posts['posts']:
            if post['read']:
                self._logger.debug(f"Already seen post {post['post']['name']}")
                continue
            ret_posts.append(post)

        return ret_posts

    def _answer_sub_request(self, post: dict) -> Optional[CommunityDTO]:
        """Create a new Lemmy Community based on request post"""
        # Try and extract the subreddit
        ident = None
        community = None
        if post['post']['url']:
            try:
                ident = RedditReader.get_subreddit_ident(post['post']['url'])
            except ValueError:
                pass
        elif post['post']['name']:
            try:
                ident = RedditReader.get_subreddit_ident(post['post']['name'])
            except ValueError:
                pass

        # TODO: this should raise proper exceptions
        if ident:
            # Figure out if subreddit exists and is open
            community = self._reddit_reader.get_subreddit_info(ident)
            if not community:
                self._logger.warning(f'Subreddit {ident} is not open for business')
                self._lemmy.create_comment(
                    post_id=post['post']['id'],
                    content=f"I cannot access the *{ident}* subreddit. Make another request when it is accessible."
                )
            else:
                self._logger.info(f'Success! Let\'s clone the sh!t out of {ident}')
                return community
        else:
            self._logger.warning(f"Couldn't determine subreddit for request {post['post']['ap_id']}")
            self._lemmy.create_comment(
                post_id=post['post']['id'],
                content=f"I don't know which subreddit you mean."
            )

        self._lemmy.mark_post_as_read(post_id=post['post']['id'], read=True)
        return community
