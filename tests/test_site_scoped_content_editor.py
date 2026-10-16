import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SiteScopedContentEditorTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_content_list_opens_editor_in_selected_site_context(self):
        template = self.read("templates/dashboard/publication/index.html")

        self.assertIn("admin.publication.workspace_edit", template)
        self.assertIn("site_id=selected_site.id", template)
        self.assertIn("Размещение с другого сайта", template)
        self.assertIn("admin.publication.workspace_delete", template)
        self.assertIn("Убрать с сайта", template)

    def test_workspace_editor_uses_selected_site_placement(self):
        controller = self.read("views/dashboard/blog/workspace.py")

        self.assertIn("PublicationSite.site_id == site_id", controller)
        self.assertIn('PublicationSite.slug == slug', controller)
        self.assertIn("Category.get_by_id", controller)
        self.assertIn("schemas_for_site(selected_site.key)", controller)
        self.assertIn("MediaService.list_for_site(db_session, selected_site.id)", controller)
        self.assertIn("PublicationChannelService.set_placement", controller)
        self.assertIn("PublicationChannelService.sync_owner", controller)

    def test_removing_foreign_placement_does_not_delete_source_publication(self):
        controller = self.read("views/dashboard/blog/workspace.py")

        self.assertIn("if selected_site.id == publication.site_id:", controller)
        self.assertIn("PublicationService.delete_publication", controller)
        self.assertIn("PublicationChannelService.remove_placement", controller)
        self.assertIn("set_profile(", controller)

    def test_workspace_routes_are_registered(self):
        routers = self.read("views/dashboard/blog/routers.py")

        self.assertIn('admin.publication.workspace_edit', routers)
        self.assertIn('admin.publication.workspace_preview', routers)
        self.assertIn('admin.publication.workspace_delete', routers)


if __name__ == "__main__":
    unittest.main()
