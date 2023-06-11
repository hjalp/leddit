#!/usr/bin/env python3
import os
import sys
import time

import click
import requests
from dotenv import load_dotenv
from requests import Session as HttpSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DbSession

from models.models import Base, Community
from reddit.scraper import get_subreddit_topics, SORT_NEW
from utils import USER_AGENT

db_session: DbSession
http_session: HttpSession


@click.group()
def cli():
    """CLI commands for managing communities."""


@cli.command()
@click.option('--name', prompt=True, help='Name of the subreddit')
@click.option('--path', prompt=True, help='Path to the subreddit')
def add_community(name, reddit):
    """Add a new subreddit to the database."""
    community = Community(name=name, path=reddit)
    db_session.add(community)
    db_session.commit()
    click.echo('Community added successfully.')


@cli.command()
def scrape_communities():
    """Scrape all communities in the database."""
    communities = db_session.query(Community).all()

    delay_time = 6
    max_index = len(communities) - 1

    for index, community in enumerate(communities):
        iteration_start_time = time.time()
        click.echo(f'Scraping subreddit: {community.name}')
        posts = get_subreddit_topics(community.path, http_session, mode=SORT_NEW)
        for post in posts:
            click.echo(post)

        # details = get_post_details(posts[0], http_session)
        # pprint.pprint(details)

        delay = delay_time - (time.time() - iteration_start_time)
        if index < max_index and delay > 0:
            click.echo(f'Waiting for {delay} seconds')
            time.sleep(delay)


def initialize_database(database_url):
    """Initialize the database if it doesn't exist and run migrations."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    global db_session
    db_session = session()


def initialize_http_session():
    global http_session
    http_session = requests.Session()
    http_session.headers.update({'User-Agent': USER_AGENT})


if __name__ == '__main__':
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('Error: DATABASE_URL environment variable is not set.')
        sys.exit(1)

    initialize_database(database_url)
    initialize_http_session()
    cli()
