# Lemmit

A Reddit-to-Lemmy cross-poster.

## To do:
- MORE TESTS!
- Harden Subreddit-Request handling
  - (skip existing. Duh!)
- Create a watcher that periodically checks for updates (edits / deletes) on reddit post and sync those:
  * 1 hour, day, week, month after posting.
  * Automatically when reported (Unless queued in last hour, to prevent abuse)
- Toggle between copying **New** or just the **Hot** posts
  * What should be the default? For properly moderated subs, New can be used.
