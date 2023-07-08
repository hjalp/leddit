# Leddit

An automated Reddit-to-Threadiverse crossposter based on [Lemmit](https://gitlab.com/sab_from_earth/lemmit). Leddit is named Leddit because it takes more from Reddit than Lemmit does. Specifically, it supports crossposting posts *and* comment threads from Reddit to Lemmy. 

Leddit does not use the Reddit API and will remain functional after the API changes come into force July 1st, 2023.

It is **strongly recommended** to deploy this bot on a a dedicated instance with high rate limits. The high activity from this bot can disrupt federation, post ranking calculation and activity on a populated instance.

Contributions are welcome! If you have any ideas, suggestions, or bug reports, please open an issue or submit a pull request. You can also visit the [Lemmy support community](https://leddit.danmark.party/c/lounge) for this bot or [DM me on Lemmy](https://leddit.danmark.party/u/Andreas) if you need something answered privately.

## Prerequisites

- Python 3.10 or higher

## Installation

1. Clone the repository:

```sh
git clone https://github.com/hjalp/leddit.git
```

2. Navigate to the project directory:

```sh
cd leddit
```

3. Install the dependencies:

```sh
pip install --no-cache-dir -r requirements.txt
```

## Configuration

Currently, Leddit only supports the Lemmy API.

The bot uses a `config.yaml` file to determine the settings for scraping and posting. Adjust the values in the `config.yaml` file according to your requirements. Make sure that the destination Lemmy communities have been created before deploying the bot.

Example `config.yaml` file:

```yml
lemmy_base_uri: https://lemmy.myinstance.com # The base instance URL without anything trailing like /api/v3/

max_post_age: 86400 # Maximum age of a post (in seconds) before new comments will not be synced
request_interval: 3 # Time (in seconds) between sending requests to fetch post information
scrape_interval: 3600 # Time (in seconds) after the last sync to start a new update
user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'

header_position: top # Either 'top' or 'bottom'. Defaults to top if not provided

community_map:
  - subreddit: sweden # Name of the subreddit to crosspost from, without /r/
    community: sweden # Name of the Lemmy community to crosspost to, without /c/ or domain
    sort: new # Either 'new' or 'hot'. Defaults to new if not provided
    post_header: '##### Det här inlägget arkiverades automatiskt av [Leddit-botten](https://github.com/hjalp/leddit). Vill du diskutera tråden? Joina vårt Lemmy-community på [feddit.nu](https://feddit.nu)!'
    # The text that appears above each cross-post's body
  - subreddit: askreddit
    community: asklemmy
    sort: hot
    post_header: '##### This is an automated archive made by the [Leddit Bot](https://github.com/hjalp/leddit). Want to discuss this thread? Join our Lemmy community on [/c/asklemmy on My Lemmy Instance](https://lemmy.instance.com/c/asklemmy)!'
```
## Usage

Set up the following environment variables by copying the provided `.env.template` file and renaming it to `.env`. Update the values in the `.env` file according to your crossposting bot's Lemmy account and operating instance.

- `LEMMY_USERNAME`: Username for the bot's Lemmy account
- `LEMMY_PASSWORD`: Password for the bot's Lemmy account
- `LEMMY_BASE_URI`: URL of the instance that posts will be crossposted to

Adjust the values in the `config.yaml` file according to your requirements and move this file to the `src/data` folder inside your Leddit folder.

Run the bot.

```sh
python /home/user/location-of-leddit-installation/src/main.py
```

## Deployment with Docker

Build the Leddit Docker image using the Dockerfile provided.

```sh
docker build -t leddit:latest /home/user/location-of-leddit-installation
```

Create and run the Docker container.

```sh
docker run --name leddit \
-v ./leddit:/app/data \
-e DATABASE_URL=sqlite:///data/leddit.sqlite \
-e LEMMY_USERNAME=My_Leddit_Bot \
-e LEMMY_PASSWORD=My%Leddit&B0ts-Password! \
-d leddit:latest
```

If deploying with Compose, add this snippet under `services`.

```yml
  leddit:
    image: leddit:latest
    environment:
      - DATABASE_URL=sqlite:///data/leddit.sqlite
      - LEMMY_USERNAME=My_Leddit_Bot
      - LEMMY_PASSWORD=My%Leddit&B0ts-Password!
      - LOGLEVEL=INFO
    volumes:
      - ./leddit:/app/data
    restart: always
    logging: *default-logging
```

To edit the config, stop the Docker container and edit `config.yaml` inside the `leddit` folder that is located in the same directory as `docker-compose.yml`, or the folder you ran the `docker run` command in.

## Known bugs

- When a time-out occurs on a post, it will not be posted again. Often, the post created successfully, but something goes wrong in the gateway. Proper solution would be to check afterwards.
- Posts to `/user/` subreddits (the user profile) are broken.

## To-do

- MORE TESTS!
- Implement blocking comments from accounts defined in the config
- Add configuration so the bot can archive `i.redd.it` and `v.redd.it` uploads to an external file storage service, and point those links to the archive, so that no user traffic reaches any Reddit website.
  * Image uploads are cached to the instance's `pict-rs` server by default.
- Refactor code to streamline the duplicate post/comment functions that mostly do the same thing.

## Possible enhancements

- Update the scheduling system to trigger updates at fixed intervals instead of using `time.sleep()` which is inconsistent
- Use a more fine-grained configuration of the update schedule instead of one global variable.
  * Set each community's update frequency separately and a queue system to deal with parallel execution.
  * Change the update frequency throughout the day; useful for not performing unnecessary update cycles during nighttime in local subreddits.
  * Dynamically adapt the update frequency based on post intervals in the RSS feed.
- Add a toggle that allows the bot to retrieve comments that are hidden by the "load more comments" and "show rest of the thread" buttons.
  * Right now, the bot only retrieves the comments that are visible when loading the post. It does not recursively follow "show rest of the thread" to reduce the complexity of requests.
- Sync updates (edits/deletes) on posts and comments after they have been published to Lemmy:
  * During the comment updating period.
  * When reported on Lemmy (unless queued in last hour, to prevent abuse)
  * Alternatively, use the report function to force a post to stop being updated.