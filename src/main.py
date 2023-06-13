#!/usr/bin/env python3
import os
import sys

import click
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DbSession

from lemmy.api import LemmyAPI
from models.models import Base, Community
from reddit.reader import RedditReader
from utils.queue import run_scraper

db_session: DbSession
lemmy_api: LemmyAPI
reddit_scraper: RedditReader


@click.group()
def cli():
    """CLI commands for managing communities."""


@cli.command()
@click.option('--name', prompt=True, help='Name of the subreddit')
def add_community(name):
    """Add a new subreddit to the database."""
    # TODO: properly implement (including icon fetching)
    community = Community(ident=name)
    db_session.add(community)
    db_session.commit()
    click.echo('Community added successfully.')


@cli.command()
def scrape_communities():
    """Scrape all communities in the database."""
    run_scraper(db_session, reddit_scraper, lemmy_api)


def initialize_database(db_url):
    """Initialize the database if it doesn't exist and run migrations."""
    global db_session
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    db_session = session()


if __name__ == '__main__':
    load_dotenv()

    for var_name in ['DATABASE_URL', 'LEMMY_BASE_URI', 'LEMMY_USERNAME', 'LEMMY_PASSWORD']:
        if not os.getenv(var_name):
            click.echo(f'Error: {var_name} environment variable is not set.')
            sys.exit(1)

    database_url = os.getenv('DATABASE_URL')
    lemmy_base_uri = os.getenv('LEMMY_BASE_URI')

    initialize_database(database_url)
    lemmy_api = LemmyAPI(base_url=lemmy_base_uri, username=os.getenv('LEMMY_USERNAME'), password=os.getenv('LEMMY_PASSWORD'))
    reddit_scraper = RedditReader()

    cli()
