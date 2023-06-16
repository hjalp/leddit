#!/usr/bin/env python3
import logging
import os
import sys
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lemmy.api import LemmyAPI
from models.models import Base
from reddit.reader import RedditReader
from utils.queue import Syncer

syncer: Syncer
logging.basicConfig(level=logging.DEBUG)


def initialize_database(db_url):
    """Initialize the database if it doesn't exist and run migrations."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    return session()


if __name__ == '__main__':
    load_dotenv()

    for var_name in ['DATABASE_URL', 'LEMMY_BASE_URI', 'LEMMY_USERNAME', 'LEMMY_PASSWORD']:
        if not os.getenv(var_name):
            logging.error(f'Error: {var_name} environment variable is not set.')
            sys.exit(1)

    database_url = os.getenv('DATABASE_URL')
    lemmy_base_uri = os.getenv('LEMMY_BASE_URI')

    db_session = initialize_database(database_url)
    lemmy_api = LemmyAPI(base_url=lemmy_base_uri, username=os.getenv('LEMMY_USERNAME'),
                         password=os.getenv('LEMMY_PASSWORD'))
    reddit_scraper = RedditReader()
    syncer = Syncer(db=db_session, reddit_reader=reddit_scraper, lemmy=lemmy_api)

    while True:
        syncer.scrape_new_posts()
        time.sleep(2)
