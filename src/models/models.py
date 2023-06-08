from datetime import datetime
from typing import Optional


class Post:
    def __init__(self, title: str, link: str, author: Optional[str] = None, creation_date: Optional[datetime] = None,
                 updated_date: Optional[datetime] = None):
        self.title = title
        self.link = link
        self.author = author
        self.creation_date = creation_date
        self.updated_date = updated_date

    def __str__(self) -> str:
        return f"'{self.title}' on {self.link} by {self.author if self.author else 'unknown'}"


class Community:
    def __init__(self, name: str, lemmy: str, reddit: str, ) -> None:
        self.name = name
        self.lemmy = lemmy
        self.reddit = reddit

    def __str__(self) -> str:
        return f"{self.name} lemmy:{self.lemmy}, reddit:{self.reddit}"
