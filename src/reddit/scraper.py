from typing import List

import requests
from bs4 import BeautifulSoup

from src.models.models import Post


def get_subreddit_topics(subreddit: str, new=True) -> List[Post]:
    if new:
        # use www.reddit.com - harder, but potentially longer lived.
        return get_subreddit_topics_new(subreddit)
    else:
        # use old.reddit.com
        pass


def get_subreddit_topics_new(subreddit: str) -> List[Post]:
    url = f"https://www.reddit.com/r/{subreddit}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    posts = []

    post_elements = soup.select('*[data-adclicklocation="background"][data-click-id="background"]')
    for post_element in post_elements:
        title_element = post_element.select_one('*[data-adclicklocation="title"] a')
        user_element = post_element.select_one('a[data-click-id="user"]')

        title = title_element.get_text()
        link = title_element["href"]
        user = user_element.get_text() if user_element else None

        if link.startswith("/r/"):
            posts.append(Post(title=title, link=link, author=user))

    return posts
