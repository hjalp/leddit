import yaml

with open('./data/config.yaml') as config:
    try:
        data = yaml.safe_load(config)
    except yaml.YAMLError as e:
        print(e)

COMMUNITY_MAP = data['community_map']
LEMMY_BASE_URI = data['lemmy_base_uri']
HEADER_POSITION = data['header_position']
MAX_POST_AGE = data['max_post_age']
REQUEST_INTERVAL = data['request_interval']
SCRAPE_INTERVAL = data['scrape_interval']
USER_AGENT = data['user_agent']