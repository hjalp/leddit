import time
from typing import Type

import click
from sqlalchemy.orm import Session as DbSession

from models.models import Community
from reddit.reader import RedditReader, SORT_HOT

_DELAY_TIME = 6  # delay between RSS requests in seconds


def get_community_scrape_queue(db: DbSession) -> list[Type[Community]]:
    """Get a batch of communities that are due for scraping."""
    return db.query(Community).all()


def run_scraper(db: DbSession, reddit_reader: RedditReader):
    communities = get_community_scrape_queue(db)

    max_index = len(communities) - 1

    for index, community in enumerate(communities):
        iteration_start_time = time.time()
        click.echo(f'Scraping subreddit: {community.name}')
        posts = reddit_reader.get_subreddit_topics(community.path, mode=SORT_HOT)
        for post in posts:
            click.echo(post)

        if len(posts):
            # details = reddit_reader.get_post_details(posts[0])
            # click.echo(pformat(details))
            pass

        delay = _DELAY_TIME - (time.time() - iteration_start_time)
        if index < max_index and delay > 0:
            click.echo(f'Waiting for {delay} seconds')
            time.sleep(delay)
