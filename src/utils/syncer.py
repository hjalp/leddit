import logging
import re
from datetime import datetime, timedelta
from operator import attrgetter
from typing import Type, List, Optional

from requests import HTTPError
from sqlalchemy import and_
from sqlalchemy.orm import Session as DbSession

from pythorhead import Lemmy
from models.models import PostDTO, Post, CommentDTO, Comment
from reddit.reader import RedditReader
from utils.config import COMMUNITY_MAP, HEADER_POSITION, MAX_POST_AGE, LEMMY_BASE_URI

_VALID_TITLE = re.compile(r".*\S{3,}.*")
class Syncer:

    def __init__(self, db: DbSession, reddit_reader: RedditReader, username: str, password: str):
        
        self._db: DbSession = db
        self._reddit_reader: RedditReader = reddit_reader
        self._lemmy = Lemmy(LEMMY_BASE_URI)
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._username = username
        self._password = password

    def scrape_new_posts(self):
        for com in COMMUNITY_MAP:
            subreddit = com['subreddit']
            community = com['community']
            sort = com['sort']
            post_header = com['post_header']

            self._logger.info(f'Getting community ID: {community}')
            community_id = self._lemmy.discover_community(community)

            self._logger.info(f'Scraping subreddit: {subreddit}')
            try:
                posts = self._reddit_reader.get_subreddit_topics(subreddit, mode=sort)
            except BaseException as e:
                self._logger.error(f"Error trying to retrieve topics: {str(e)}")
                return

            posts = self.filter_posted(posts)

            # Handle oldest entries first.
            posts = sorted(posts, key=attrgetter('updated'))

            try:
                self._lemmy.log_in(self._username, self._password)

            except HTTPError as e:
                self._logger.error(
                    f"Couldn\'t log in to account {self._username} on {LEMMY_BASE_URI}."
                )
                return

            for post in posts:
                self._logger.info(post)
                try:
                    post, comments = self._reddit_reader.get_post_details(post)
                except BaseException as e:
                    self._logger.error(f"Error trying to retrieve post details, try again in a bit; {str(e)}")
                    return
                post = self.clone_to_lemmy(post, subreddit, community_id, post_header)
                
                self.clone_comments_to_lemmy(post, comments)

    def update_comments(self):
        """Remove old posts and update comments of posts"""
        try:
            self._lemmy.log_in(self._username, self._password)

        except HTTPError as e:
            self._logger.error(
                f"Couldn\'t log in to account {self._username} on {LEMMY_BASE_URI}."
            )
            return

        # Remove aged posts from the database
        self.clear_aged()
        db_post_list = self._db.query(Post).filter(Post.enabled.is_(True)).all()

        for db_post in db_post_list:
            self._logger.info(f'Updating post with ID {db_post.id}')
            post = PostDTO(
                reddit_link=db_post.reddit_link,
                title='Unused',
                created=db_post.created,
                updated=db_post.updated,
                author=db_post.author,
                lemmy_id=db_post.id)
            try:
                post, comments = self._reddit_reader.get_post_details(post)
            except BaseException as e:
                self._logger.error(f"Error trying to retrieve updated comments for post {db_post.reddit_link}, try again in a bit; {str(e)}")
                continue

            filtered_comments = self.filter_posted_comments(comments)
            self.clone_comments_to_lemmy(post, filtered_comments)

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
    
    def filter_posted_comments(self, comments: List[CommentDTO]) -> List[CommentDTO]:
        comment_ids = [comment.id for comment in comments]
        existing_comments_raw = self._db.query(Comment.reddit_id).filter(Comment.reddit_id.in_(comment_ids)).all()
        existing_comments = [comment[0] for comment in existing_comments_raw]
        
        filtered_comments = []
        for comment in comments:
           if comment.id not in existing_comments:
              filtered_comments.append(comment)
        return filtered_comments
    
    def clear_aged(self):
        """Remove any posts and their comments that are older than the maximum update age from the database"""
        aged_posts = self._db.query(Post).filter(Post.enabled.is_(True), and_(Post.created <= datetime.utcnow() - timedelta(seconds=MAX_POST_AGE))).all()

        for aged_post in aged_posts:
            try:
                aged_comments = self._db.query(Comment).filter(Comment.post_id == aged_post.id)
                for comment in aged_comments:
                    self._db.delete(comment)
                    self._db.commit()
                
                self._db.delete(aged_post)
                self._db.commit()

                self._logger.info(
                    f"Deleted post {aged_post.id} and its comments from the database."
                )
            except Exception as e:
                self._logger.error(
                    f"Couldn't delete {aged_post.reddit_link} from the local database. {str(e)}"
                )

    def clone_to_lemmy(self, post: PostDTO, subreddit: str, community_id: int, post_header: str) -> PostDTO: # Returns PostDTO with Lemmy post ID

        post = self.prepare_post(post, subreddit, post_header)
        self._logger.info(
            f"Attempting to post {post.reddit_link}..."
        )
        try:
            lemmy_post = self._lemmy.post.create(
                community_id=community_id,
                name=post.title,
                url=post.external_link,
                body=post.body,
                nsfw=post.nsfw
            )

        except HTTPError as e:
            if e.response.status_code == 504 or e.response.status_code == 502:
                # ron_burgundy_-_I_dont_believe_you.gif
                self._logger.warning(f'Timeout when trying to post {post.reddit_link}: {str(e)}\nSuuuure...')
                # TODO: check if post was actually placed through a search.
                #  If not, return, so it gets picked up next time
                previous_id = self._db.query(Post.id).order_by(Post.id.desc()).first()
                lemmy_post = {'post_view': {'post': {'ap_id': f'{LEMMY_BASE_URI}/post/{previous_id + 1}', 'id': {previous_id + 1}}}}  # hack
            else:
                self._logger.error(
                    f"HTTPError trying to post {post.reddit_link}: {str(e)}: {str(e.response.content)}"
                )
                return

        except Exception as e:
            self._logger.error(
                # f"Something went horribly wrong when posting {post.reddit_link}: {str(e)}: {str(e.response.content)}"
                f"Something went horribly wrong when posting {post.reddit_link}: {str(e)}"
            )
            return
        
        try:
            lemmy_link = lemmy_post['post_view']['post']['ap_id']
            post.lemmy_id = lemmy_post['post_view']['post']['id']

        except Exception as e: # hack
            previous = self._db.query(Post.id).order_by(Post.id.desc()).first()
            post.lemmy_id = previous[0] + 1
            
            lemmy_link = f'{LEMMY_BASE_URI}/post/{previous[0] + 1}'
            self._logger.error(
                f"""Leddit hit a HTTP Error when posting comment {post.reddit_link} and didn't receive a response: {str(e)}\n
                However, it has likely been posted to Lemmy. Please do a check!\n
                This post will be committed to the database."""
            )

        # Save post to database
        try:
            db_post = Post(
                id=post.lemmy_id,
                community_id=community_id,
                reddit_link=post.reddit_link,
                lemmy_link=lemmy_link,
                created=post.created,
                updated=datetime.utcnow(),
                author=post.author,
                enabled=1
            )
            self._db.add(db_post)
            self._db.commit()
        except Exception as e:
            self._logger.error(
                f"Couldn't save {post.reddit_link} to local database. Please remove the existing post from Lemmy (or it will be duplicated next round). {str(e)}"
            )

        return post

    def clone_comments_to_lemmy(self, post: PostDTO, comments: List[CommentDTO]):

        comments_map = {}
        previous = self._db.query(Comment.id).order_by(Comment.id.desc()).first()
        id_counter = previous[0]

        for comment in comments:
            comment = self.prepare_comment(post.reddit_link, post.author, comment)
            try:
                parent_lemmy = None if comment.parent == comment.post_id else comments_map[comment.parent]

            # Search comment database if parent comment has already been posted in a previous round
            except KeyError:
                result = self._db.query(Comment).filter(Comment.reddit_id == comment.parent).first()
                parent_lemmy = result.id
                comments_map[comment.parent] = parent_lemmy

            self._logger.info(
                f"Attempting to post {comment.id}..."
            )
            try:
                lemmy_comment = self._lemmy.comment.create(
                    content=comment.body,
                    post_id=post.lemmy_id,
                    parent_id=parent_lemmy
                )

            except HTTPError as e:
                if e.response.status_code == 504 or e.response.status_code == 502:
                    # ron_burgundy_-_I_dont_believe_you.gif
                    self._logger.warning(f'Timeout or Bad Gateway when trying to post {post.reddit_link}: {str(e)}\nSuuuure...')
                    # TODO: Refactor duplicates
                    lemmy_comment = {'comment_view': {'comment': {'id': {id_counter + 1}}}}  # hack
                else:
                    self._logger.error(
                        f"HTTPError trying to post {comment.id}: {str(e)}: {str(e.response.content)}"
                    )
                    continue

            except Exception as e:
                self._logger.error(
                    f"Something went horribly wrong when posting {comment.id}: {str(e)}"
                )
                continue

            try:
                lemmy_comment_id = lemmy_comment['comment_view']['comment']['id']
                # Dictionary to map Reddit ID to Lemmy ID
                comments_map[comment.id] = lemmy_comment_id
            
            except Exception as e: # hack
                id_counter += 1
                comments_map[comment.id] = id_counter
                lemmy_comment_id = id_counter
                self._logger.error(
                    f"""Leddit hit a HTTP Error when posting comment {comment.id} and didn't receive a response: {str(e)}\n
                    However, it has likely been posted to Lemmy. Please do a check!\n
                    This comment will be committed to the database."""
                )

            # Save comment to database
            try:
                db_comment = Comment(
                    id=lemmy_comment_id,
                    reddit_id=comment.id,
                    created=comment.created,
                    post_id=post.lemmy_id
                )
                self._db.add(db_comment)
                self._db.commit()

                id_counter = lemmy_comment_id

            except Exception as e:
                print(f"Couldn't save {comment.id} to local database. Please remove the existing comment from Lemmy (or it will be duplicated next round). {str(e)}")
                continue

    @staticmethod
    def prepare_post(post: PostDTO, subreddit: str, post_header: str) -> PostDTO:
        prefix = f"""{post_header}\n
[The original]({post.reddit_link.replace('https://www.', 'https://old.')}) was posted on [/r/{subreddit}](https://old.reddit.com/r/{subreddit}) by [{post.author}](https://old.reddit.com{post.author}) at {post.created}."""
        if len(post.title) >= 200:
            prefix = prefix + f"\n**Original Title**: {post.title}\n"
            post.title = post.title[:196] + '...'
        # Lemmy post title filters
        elif not _VALID_TITLE.match(post.title):
            prefix = prefix + f"\n**Original Title**: {post.title}\n"
            post.title = post.title.rstrip() + '...'
        # Resolve Reddit crosspost links
        if post.external_link and len(post.external_link) > 512:
            prefix = prefix + f"\n**Original URL**: {post.external_link}\n"
            post.external_link = None
        if post.external_link and post.external_link.startswith('/'):
            post.external_link = 'https://old.reddit.com' + post.external_link


        if HEADER_POSITION == 'bottom':
            post.body = (post.body + '\n***\n' if post.body else '') + prefix
        else:
            post.body = prefix + ('\n***\n' + post.body if post.body else '')

        if len(post.body) > 10000:
            post.body = post.body[:9800] + '...\n***\nContent cut off. Read original on ' + post.reddit_link

        return post
    
    @staticmethod
    def prepare_comment(post_reddit_link: str, post_author: str, comment: CommentDTO) -> CommentDTO:
        
        if post_author == '/u/' + comment.author and post_author != '[deleted]':
            prefix = f'**{comment.author} (OP)** at {comment.created} ID: `{comment.id}`'
        else:
            prefix = f'**{comment.author}** at {comment.created} ID: `{comment.id}`'

        comment.body = prefix + ('\n***\n' + comment.body if comment.body else '')
        
        if len(comment.body) > 10000:
            comment.body = comment.body[:9750] + '...\n***\nContent cut off. Read original on ' + post_reddit_link + comment.id

        return comment
