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


# TODO: Convert to class, so it doesn't have to pass instances around
# TODO: Work on a tick-basis

def get_community_scrape_queue(db: DbSession) -> list[Type[Community]]:
    """Get a batch of communities that are due for scraping."""
    return db.query(Community).all()


def run_scraper(db: DbSession, reddit_reader: RedditReader, lemmy: LemmyAPI):
    communities = get_community_scrape_queue(db)

    max_index = len(communities) - 1

    for index, community in enumerate(communities):
        iteration_start_time = time.time()
        click.echo(f'Scraping subreddit: {community.ident}')
        posts = reddit_reader.get_subreddit_topics(community.ident, mode=SORT_HOT)

        posts = filter_posted(posts, db)

        posts = sorted(posts, key=attrgetter('updated'))  # Handle oldest entries first.

        for post in posts:
            click.echo(post)
            post = reddit_reader.get_post_details(post)
            clone_to_lemmy(post, community, lemmy, db)

        delay = _DELAY_TIME - (time.time() - iteration_start_time)
        if index < max_index and delay > 0:
            click.echo(f'Waiting for {delay} seconds')
            time.sleep(delay)


def filter_posted(posts: List[PostDTO], db: DbSession) -> List[PostDTO]:
    """Filter out any posts that have already been synced to Lemmy"""
    reddit_links = [post.reddit_link for post in posts]
    existing_links = db.query(Post.reddit_link).filter(Post.reddit_link.in_(reddit_links)).all()
    existing_links = [link[0] for link in existing_links]

    filtered_posts = [post for post in posts if post.reddit_link not in existing_links]
    return filtered_posts


def clone_to_lemmy(post: PostDTO, community: Community, lemmy: LemmyAPI, db: DbSession):
    try:
        lemmy_post = lemmy.create_post(
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
        dbPost = Post(reddit_link=post.reddit_link, lemmy_link=lemmy_post['post_view']['post']['ap_id'],
                      community=community, updated=datetime.utcnow(), nsfw=post.nsfw)
        db.add(dbPost)
        db.commit()
    except Exception as e:
        print(f"Couldn't save {post.reddit_link} to local database. MUST REMOVE FROM LEMMY OR ELSE. {str(e)}")

