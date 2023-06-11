from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped

Base = declarative_base()


class Community(Base):
    """Represents a community/subreddit on both Lemmy and Reddit"""

    __tablename__: str = 'communities'

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String)
    path: str = Column(String)
    nsfw: bool = Column(Boolean)
    last_scrape: datetime = Column(DateTime)

    def __init__(self, name: str, path: str, nsfw: bool, last_scrape: datetime):
        self.name = name
        self.path = path
        self.nsfw = nsfw
        self.last_scrape = last_scrape

    def __str__(self) -> str:
        return f"{self.name} path:{self.path}"


@dataclass
class PostDTO:
    reddit_link: str
    title: str
    created: datetime
    updated: datetime
    author: Optional[str] = None
    external_link: Optional[str] = None
    nsfw: bool = False

    def __str__(self) -> str:
        return f"'{self.title}' at {self.reddit_link} updated: {self.updated}"


class Post(Base):
    __tablename__: str = 'posts'

    id: int = Column(Integer, primary_key=True)
    reddit_link: str = Column(String)
    updated: datetime = Column(DateTime)
    nsfw: bool = Column(Boolean)
    community_id: int = Column(Integer, ForeignKey('communities.id'))

    community: Mapped[Community] = relationship('Community')

    def __init__(self, reddit_link: str, community: Community, updated: datetime, nsfw: bool):
        self.reddit_link = reddit_link
        self.community = community
        self.updated = updated
        self.nsfw = nsfw

    def __str__(self) -> str:
        return f"'{self.title}' on {self.link} by {self.author if self.author else 'unknown'}"

    @classmethod
    def from_dto(cls, post: PostDTO, community: Community) -> 'Post':
        return cls(
            reddit_link=post.reddit_link,
            community=community,
            updated=post.updated,
            nsfw=post.nsfw
        )
