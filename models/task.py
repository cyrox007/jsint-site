# models/task.py
from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime, ForeignKey, Numeric, String,
    UUID as PG_UUID, Enum as SQLAlchemyEnum, Table, Column, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.technology import Technology


class TaskCategory(str, Enum):
    DEVELOPMENT = 'development'
    ANALYTICS = 'analytics'
    DESIGN = 'design'
    BUG = 'bug'
    COMMUNICATION = 'communication'
    AGREEMENT = 'agreement'
    TESTING = 'testing'


class TaskStatus(str, Enum):
    TODO = 'todo'
    IN_PROGRES = 'in_progres'
    REVIEW = 'review'
    DONE = 'done'
    CANCELLED = 'cancelled'


# Связующая таблица Task-Technology – ОПРЕДЕЛЯЕМ ДО КЛАССА
task_technologies = Table(
    'task_technologies',
    Database.Base.metadata,
    Column('task_id', PG_UUID(as_uuid=True), ForeignKey('tasks.id', ondelete='CASCADE'), primary_key=True),
    Column('technology_id', PG_UUID(as_uuid=True), ForeignKey('technologies.id', ondelete='CASCADE'), primary_key=True),
)


class Task(Database.Base):
    __tablename__ = 'tasks'
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    order_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[TaskCategory] = mapped_column(SQLAlchemyEnum(TaskCategory), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SQLAlchemyEnum(TaskStatus), default=TaskStatus.TODO, nullable=False)

    estimated_hours: Mapped[Optional[float]] = mapped_column(Numeric(5,2), nullable=True)
    actual_hours: Mapped[Optional[float]] = mapped_column(Numeric(5,2), nullable=True)
    planned_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ПРИВАТНО
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    technologies: Mapped[List["Technology"]] = relationship(
        "Technology",
        secondary=task_technologies,
        lazy="selectin"
    )
