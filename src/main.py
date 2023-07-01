#!/usr/bin/env python3
import logging
import os
import signal
import sys
import time

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models.models import Base
from reddit.reader import RedditReader
from utils.syncer import Syncer
from utils.config import SCRAPE_INTERVAL

syncer: Syncer
load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=os.getenv('LOGLEVEL', logging.INFO))
keep_running = True


def handle_signal(signum, frame):
    global keep_running
    logging.warning(f"Received signal {signum}. Stopping gracefully...")
    keep_running = False


def initialize_database(db_url):
    """Initialize the database if it doesn't exist and run migrations."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    # Run migrations using Alembic
    alembic_cfg = Config("../alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")  # Adjust the script location if needed
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    session = sessionmaker(bind=engine)
    return session(), engine


if __name__ == '__main__':
    for var_name in ['DATABASE_URL', 'LEMMY_USERNAME', 'LEMMY_PASSWORD']:
        if not os.getenv(var_name):
            logging.error(f'Error: {var_name} environment variable is not set.')
            sys.exit(1)

    database_url = os.getenv('DATABASE_URL')
    username = os.getenv('LEMMY_USERNAME')
    password = os.getenv('LEMMY_PASSWORD')

    db_session, db_engine = initialize_database(database_url)

    reddit_scraper = RedditReader()
    syncer = Syncer(db=db_session, reddit_reader=reddit_scraper, username=username, password=password)

    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)


    while keep_running:
        # Vacuum empty rows to reduce database file size and operation time
        with db_engine.connect() as conn:
            with conn.execution_options(isolation_level='AUTOCOMMIT'):
                conn.execute(text("vacuum"))

        syncer.update_comments()
        syncer.scrape_new_posts()
        logging.info(f'Update complete. Sleeping for {SCRAPE_INTERVAL} seconds.')
        time.sleep(SCRAPE_INTERVAL)
