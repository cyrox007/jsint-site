from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import (
    UUID as PG_UUID,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    asc,
    desc,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.publication import Publication


class Category(Database.Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("site_id", "slug", name="uq_categories_site_slug"),
    )

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[UUIDType]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    articles: Mapped[List["Publication"]] = relationship(
        "Publication",
        back_populates="category",
        lazy="selectin",
    )
    parent = relationship("Category", remote_side=[id], backref="children", lazy="selectin")

    def __repr__(self):
        return f"<Category {self.title} ({self.id})>"

    @classmethod
    def get_categories(
        cls,
        session: Session,
        *,
        site_id: UUIDType | None = None,
        title_contains: Optional[str] = None,
        slug: Optional[str] = None,
        has_articles: Optional[bool] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        filters: Optional[list] = None,
        order_by: Optional[str] = "created_at",
        order_direction: str = "desc",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List["Category"]:
        query = session.query(cls)

        if site_id is not None:
            query = query.filter(cls.site_id == site_id)
        if title_contains is not None:
            query = query.filter(cls.title.ilike(f"%{title_contains}%"))
        if slug is not None:
            query = query.filter(cls.slug == slug)
        if has_articles is True:
            query = query.filter(cls.articles.any())
        elif has_articles is False:
            query = query.filter(~cls.articles.any())
        if created_after is not None:
            query = query.filter(cls.created_at >= created_after)
        if created_before is not None:
            query = query.filter(cls.created_at <= created_before)
        if filters:
            for item in filters:
                query = query.filter(item)

        if order_by and hasattr(cls, order_by):
            col = getattr(cls, order_by)
            query = query.order_by(asc(col) if order_direction == "asc" else desc(col))
        else:
            query = query.order_by(desc(cls.created_at))

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def get_by_id(
        cls,
        session: Session,
        category_id: UUIDType,
        site_id: UUIDType | None = None,
    ) -> Optional["Category"]:
        query = session.query(cls).filter(cls.id == category_id)
        if site_id is not None:
            query = query.filter(cls.site_id == site_id)
        return query.first()

    @classmethod
    def get_by_slug(
        cls,
        session: Session,
        slug: str,
        site_id: UUIDType | None = None,
    ) -> Optional["Category"]:
        query = session.query(cls).filter(cls.slug == slug)
        if site_id is not None:
            query = query.filter(cls.site_id == site_id)
        return query.first()

    @classmethod
    def get_tree(
        cls,
        session: Session,
        site_id: UUIDType,
        parent_id: Optional[UUIDType] = None,
        _visited: Optional[set[UUIDType]] = None,
    ) -> List[dict]:
        visited = set() if _visited is None else set(_visited)
        query = (
            session.query(cls)
            .filter(cls.site_id == site_id, cls.parent_id == parent_id)
            .order_by(cls.title)
        )
        tree: list[dict] = []

        for category in query.all():
            if category.id in visited:
                continue
            next_visited = visited | {category.id}
            tree.append(
                {
                    "id": category.id,
                    "site_id": category.site_id,
                    "title": category.title,
                    "slug": category.slug,
                    "description": category.description,
                    "children": cls.get_tree(
                        session,
                        site_id,
                        category.id,
                        next_visited,
                    ),
                }
            )
        return tree

    @classmethod
    def get_ancestors(cls, session: Session, category_id: UUIDType) -> List["Category"]:
        category = cls.get_by_id(session, category_id)
        if not category:
            return []

        ancestors: list[Category] = []
        current = category
        visited = {category.id}
        while current.parent_id:
            if current.parent_id in visited:
                break
            parent = cls.get_by_id(session, current.parent_id, current.site_id)
            if not parent:
                break
            visited.add(parent.id)
            ancestors.insert(0, parent)
            current = parent
        return ancestors

    @classmethod
    def get_children(cls, session: Session, category_id: UUIDType) -> List["Category"]:
        category = cls.get_by_id(session, category_id)
        if category is None:
            return []
        return (
            session.query(cls)
            .filter(cls.site_id == category.site_id, cls.parent_id == category_id)
            .order_by(cls.title)
            .all()
        )

    @classmethod
    def get_all_descendants(cls, session: Session, category_id: UUIDType) -> List["Category"]:
        category = cls.get_by_id(session, category_id)
        if category is None:
            return []

        result: list[Category] = []
        stack = [category_id]
        visited = {category_id}

        while stack:
            current_id = stack.pop()
            children = (
                session.query(cls)
                .filter(cls.site_id == category.site_id, cls.parent_id == current_id)
                .all()
            )
            for child in children:
                if child.id in visited:
                    continue
                visited.add(child.id)
                result.append(child)
                stack.append(child.id)
        return result

    @classmethod
    def get_path(cls, session: Session, category_id: UUIDType) -> List["Category"]:
        return cls.get_ancestors(session, category_id)

    @classmethod
    def get_publication_count(cls, session: Session, category_id: UUIDType) -> int:
        from models.publication import Publication

        category = cls.get_by_id(session, category_id)
        if category is None:
            return 0
        descendants = cls.get_all_descendants(session, category_id)
        ids = [item.id for item in descendants] + [category_id]
        return (
            session.query(Publication)
            .filter(
                Publication.site_id == category.site_id,
                Publication.category_id.in_(ids),
            )
            .count()
        )
