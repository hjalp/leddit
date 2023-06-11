import time
from typing import Type

import click
from requests import Session as HttpSession
from sqlalchemy.orm import Session as DbSession

from models.models import Community
from reddit.scraper import get_subreddit_topics, SORT_HOT

_DELAY_TIME = 6  # delay between RSS requests in seconds


def get_community_scrape_queue(db: DbSession) -> list[Type[Community]]:
    """Get a batch of communities that are due for scraping."""
    return db.query(Community).all()


def run_scraper(db: DbSession, http: HttpSession):
    communities = get_community_scrape_queue(db)

    max_index = len(communities) - 1

    for index, community in enumerate(communities):
        iteration_start_time = time.time()
        click.echo(f'Scraping subreddit: {community.name}')
        posts = get_subreddit_topics(community.path, http, mode=SORT_HOT)
        for post in posts:
            click.echo(post)

        # details = get_post_details(posts[0], http)
        # from pprint import pprint
        # pprint(details)

        delay = _DELAY_TIME - (time.time() - iteration_start_time)
        if index < max_index and delay > 0:
            click.echo(f'Waiting for {delay} seconds')
            time.sleep(delay)
