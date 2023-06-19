# Lemmit

A Reddit-to-Lemmy cross-poster.

## Known bugs:
- When a time-out occurs on a post, it will not be posted again. Often, the post created successfully, but something goes wrong in the gateway. Proper solution would be to check afterwards.
- Posts to `/user/` subreddits are broken.

## To do:
- MORE TESTS!
- Follow links on "bestof" posts: If post has no body, and "external link" is also reddit, retrieve body from external link.
- Harden Subreddit-Request handling
  - (skip existing. Duh!)
- Create a watcher that periodically checks for updates (edits / deletes) on reddit post and sync those:
  * 1 hour, day, week, month after posting.
  * Automatically when reported (Unless queued in last hour, to prevent abuse)
- Toggle between copying **New** or just the **Hot** posts
  * What should be the default? For properly moderated subs, New can be used.

## Maybe later
- Have a hardcoded set of subs, rather than working through a request community, for running on other instances.
