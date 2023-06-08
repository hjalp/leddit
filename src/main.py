from reddit.scraper import get_subreddit_topics

posts = get_subreddit_topics('showerthoughts')
for post in posts:
    print(post)
