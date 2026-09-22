# 1. Независимые модели (не имеют внешних ключей на другие наши модели)
from models.technology import Technology
from models.users import User
from models.categories import Category

# 2. Модели, зависящие от других
from models.publication import Publication
from models.task import Task
from models.control_plane import LicenseRecord, ReleaseRecord

# Если будут другие модели — добавляйте в правильном порядке
# from models.comments import Comment  # зависит от Article и User

__all__ = ["User", "Category", "Technology", "Publication", "Task", "LicenseRecord", "ReleaseRecord"]