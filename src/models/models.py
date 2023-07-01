from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, declarative_base

Base = declarative_base()

SORT_HOT = 'hot'
SORT_NEW = 'new'

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
    lemmy_id: int = 0

    def __str__(self) -> str:
        return f"'{self.title}' at {self.reddit_link} updated: {self.updated}"


class Post(Base):
    __tablename__: str = 'posts'

    id: int = Column(Integer, primary_key=True) # Post ID on Lemmy
    community_id: int = Column(Integer, nullable=False) # Community ID on Lemmy
    reddit_link: str = Column(String, nullable=False)
    lemmy_link: str = Column(String, nullable=False)
    created: datetime = Column(DateTime, nullable=False)
    updated: datetime = Column(DateTime, nullable=False)
    author: str = Column(String, nullable=False)
    enabled: bool = Column(Boolean, nullable=False, server_default='1') # To scrape or not to scrape

    def __str__(self) -> str:
        return f"'#{self.id}: {self.title}' on {self.community.name}"

    @classmethod
    def from_dto(cls, post: PostDTO) -> 'Post':
        return cls(
            reddit_link=post.reddit_link,
            updated=post.updated,
            nsfw=post.nsfw
        )
    
@dataclass
class CommentDTO:
    id: str # Reddit comment ID
    created: datetime
    author: str
    body: str
    parent: str # Reddit parent ID
    post_id: str # Reddit original post ID

class Comment(Base):
    __tablename__: str = 'comments'

    id: int = Column(Integer, primary_key=True) # Comment ID on Lemmy
    reddit_id: str = Column(String, nullable=False) # Comment ID on Reddit
    created: datetime = Column(DateTime, nullable=False)
    post_id: int = Column(Integer, ForeignKey('posts.id'), nullable=False) # Parent post ID on Lemmy

    post: Mapped[Post] = relationship('Post')

    def __str__(self) -> str:
        return f"'#{self.id}: child of {self.parent}' on {self.post_id}"
