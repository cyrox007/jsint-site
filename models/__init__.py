# 1. Сначала User (от него зависят другие модели)
from models.users import User

# 2. Потом Category (от неё зависит Article)
from models.categories import Category

# 3. В конце Article (зависит от User и Category)
from models.articles import Article

# Если будут другие модели — добавляйте в правильном порядке
# from models.comments import Comment  # зависит от Article и User

__all__ = ["User", "Category", "Article"]