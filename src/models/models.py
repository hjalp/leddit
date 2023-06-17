from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, declarative_base

Base = declarative_base()


class Community(Base):
    """Represents a community/subreddit on both Lemmy and Reddit"""

    __tablename__: str = 'communities'

    id: int = Column(Integer, primary_key=True)
    lemmy_id: int = Column(Integer, nullable=False)
    ident: str = Column(String, nullable=False)
    nsfw: bool = Column(Boolean, nullable=False, default=False)
    last_scrape: datetime = Column(DateTime, nullable=True)

    def __str__(self) -> str:
        return f"{self.ident} path:{self.path}"


@dataclass
class PostDTO:
    reddit_link: str
    title: str
    created: datetime
    updated: datetime
    author: str
    external_link: Optional[str] = None
    body: Optional[str] = None
    nsfw: bool = False

    def __str__(self) -> str:
        return f"'{self.title}' at {self.reddit_link} updated: {self.updated}"


class Post(Base):
    __tablename__: str = 'posts'

    id: int = Column(Integer, primary_key=True)
    reddit_link: str = Column(String, nullable=False)
    lemmy_link: str = Column(String, nullable=False)
    updated: datetime = Column(DateTime, nullable=False)
    nsfw: bool = Column(Boolean, nullable=False)
    community_id: int = Column(Integer, ForeignKey('communities.id'), nullable=False)

    community: Mapped[Community] = relationship('Community')

    def __str__(self) -> str:
        return f"'#{self.id}: {self.title}' on {self.community.name}"

    @classmethod
    def from_dto(cls, post: PostDTO, community: Community) -> 'Post':
        return cls(
            reddit_link=post.reddit_link,
            community=community,
            updated=post.updated,
            nsfw=post.nsfw
        )
