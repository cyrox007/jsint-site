from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UserManagementContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_users_are_wired_into_admin(self):
        app = self.read("app.py")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        router = self.read("views/dashboard/users/router.py")

        self.assertIn("d_users_router.install(app)", app)
        self.assertIn("<span>Пользователи</span>", sidebar)
        self.assertIn('admin.users.index', router)

    def test_user_deletion_has_safety_guards(self):
        view = self.read("views/dashboard/users/views.py")
        self.assertIn("Нельзя удалить собственную активную учётную запись", view)
        self.assertIn("Нельзя удалить последнего администратора", view)
        self.assertIn("Publication.author_id == user.id", view)

    def test_user_password_is_not_stored_plaintext(self):
        view = self.read("views/dashboard/users/views.py")
        self.assertIn("hash_password(password)", view)
        self.assertIn("не менее 12 символов", view)


if __name__ == "__main__":
    unittest.main()
