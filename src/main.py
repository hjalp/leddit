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
    run_scraper(db_session, reddit_scraper)


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
    lemmy_username = os.getenv('LEMMY_USERNAME')
    lemmy_password = os.getenv('LEMMY_PASSWORD')

    initialize_database(database_url)
    lemmy_api = LemmyAPI(base_url=lemmy_base_uri)
    reddit_scraper = RedditReader()
    # foo = lemmy_api.login(lemmy_username, lemmy_password)

    cli()
