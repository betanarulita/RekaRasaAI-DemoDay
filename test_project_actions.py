import unittest
from unittest.mock import patch
import test_app

app = test_app.app


class ProjectActionTests(unittest.TestCase):
    setUp = test_app.WorkflowTests.setUp
    request = test_app.WorkflowTests.request
    register = test_app.WorkflowTests.register
    project = test_app.WorkflowTests.project
    task = test_app.WorkflowTests.task

    def setUp(self):
        test_app.WorkflowTests.setUp(self)
        self.mail = patch.object(app, "send_email", return_value=False)
        self.mail.start()
        self.addCleanup(self.mail.stop)
        self.cookie, self.csrf, self.owner = self.register("project-actions@example.test")
        self.project_id = self.project(self.owner)

    def source(self):
        status, _, result = self.request("/api/sources", "POST", {"project_id": self.project_id, "name": "Facts.md", "content": "Kopi susu 250 ml"}, self.cookie, self.csrf)
        self.assertEqual(status, 201)
        return result["id"]

    def test_source_can_be_opened_and_archived_without_erasing_history(self):
        source_id = self.source()
        status, _, result = self.request("/api/source?id=" + source_id, cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(result["source"]["content"], "Kopi susu 250 ml")
        for _ in range(2):
            self.assertEqual(self.request("/api/remove-source", "POST", {"source_id": source_id}, self.cookie, self.csrf)[0], 200)
        db = app.connect()
        self.assertEqual(app.source_payload(db, self.project_id), [])
        self.assertEqual(len(app.source_payload(db, self.project_id, [source_id])), 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE event='source.archived'").fetchone()[0], 1)
        db.close()
        projects = self.request("/api/projects", cookie=self.cookie)[2]["projects"]
        self.assertEqual(next(p for p in projects if p["id"] == self.project_id)["sources"], [])

    def test_other_account_cannot_open_or_remove_source(self):
        source_id = self.source()
        cookie, csrf, _ = self.register("other-project-actions@example.test")
        self.assertEqual(self.request("/api/source?id=" + source_id, cookie=cookie)[0], 404)
        self.assertEqual(self.request("/api/remove-source", "POST", {"source_id": source_id}, cookie, csrf)[0], 404)

    def test_task_archive_preserves_versions_and_blocks_generation(self):
        task_id, version_id = self.task(self.owner, self.project_id)
        status, _, result = self.request("/api/delete-task", "POST", {"task_id": task_id}, self.cookie, self.csrf)
        self.assertEqual(status, 200, result)
        self.assertEqual(self.request("/api/generate", "POST", {"task_id": task_id}, self.cookie, self.csrf)[0], 409)
        db = app.connect()
        self.assertEqual(db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0], "archived")
        self.assertIsNotNone(db.execute("SELECT id FROM content_versions WHERE id=?", (version_id,)).fetchone())
        self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE event='task.archived'").fetchone()[0], 1)
        db.close()
        projects = self.request("/api/projects", cookie=self.cookie)[2]["projects"]
        self.assertEqual(next(p for p in projects if p["id"] == self.project_id)["tasks"], [])

    def test_other_account_cannot_archive_task(self):
        task_id, _ = self.task(self.owner, self.project_id)
        cookie, csrf, _ = self.register("other-task-actions@example.test")
        self.assertEqual(self.request("/api/delete-task", "POST", {"task_id": task_id}, cookie, csrf)[0], 404)

    def test_proposed_plan_archive_is_idempotent_and_blocks_confirmation(self):
        output = test_app.planner_result(test_app.planner_task("Poster or static ad"))
        with patch.object(app, "llm_json", return_value=(output, {})):
            status, _, result = self.request("/api/plan", "POST", {"project_id": self.project_id, "brief": "Buat poster kopi."}, self.cookie, self.csrf)
        self.assertEqual(status, 201, result)
        plan_id = result["plan_id"]
        for _ in range(2):
            self.assertEqual(self.request("/api/delete-plan", "POST", {"plan_id": plan_id}, self.cookie, self.csrf)[0], 200)
        self.assertEqual(self.request("/api/confirm-plan", "POST", {"plan_id": plan_id}, self.cookie, self.csrf)[0], 409)
        db = app.connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE event='plan.archived'").fetchone()[0], 1)
        db.close()


class AttachmentUXTests(unittest.TestCase):
    setUp = ProjectActionTests.setUp
    request = ProjectActionTests.request
    register = ProjectActionTests.register
    project = ProjectActionTests.project

    def upload_photo(self, name="product.png"):
        from test_visual_content import PNG
        import base64
        return self.request("/api/attachments", "POST", {"project_id":self.project_id,"name":name,"content_base64":base64.b64encode(PNG).decode()},self.cookie,self.csrf)

    def test_photo_upload_archive_preserves_original_and_owner_boundary(self):
        code,_,created=self.upload_photo()
        self.assertEqual(code,201,created)
        asset=created["asset"]
        other,other_csrf,_=self.register("asset-other@example.test")
        self.assertEqual(self.request("/api/archive-asset","POST",{"asset_id":asset["id"]},other,other_csrf)[0],404)
        self.assertEqual(self.request("/api/archive-asset","POST",{"asset_id":asset["id"]},self.cookie)[0],403)
        for _ in range(2):
            self.assertEqual(self.request("/api/archive-asset","POST",{"asset_id":asset["id"]},self.cookie,self.csrf)[0],200)
        projects=self.request("/api/projects",cookie=self.cookie)[2]["projects"]
        self.assertEqual(next(p for p in projects if p["id"]==self.project_id)["assets"],[])
        self.assertEqual(self.request(asset["url"],cookie=self.cookie)[0],200)
        db=app.connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM project_assets WHERE id=?",(asset["id"],)).fetchone()[0],1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_events WHERE event='project.image_archived'").fetchone()[0],1)
        db.close()
        again=self.upload_photo()[2]["asset"]
        self.assertEqual(again["id"],asset["id"])
        projects=self.request("/api/projects",cookie=self.cookie)[2]["projects"]
        self.assertEqual(len(next(p for p in projects if p["id"]==self.project_id)["assets"]),1)

    def test_upload_batch_limit_is_separate_from_model_request_limit(self):
        for _ in range(20):self.assertEqual(self.upload_photo()[0],201)
        db=app.connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM project_assets WHERE project_id=?",(self.project_id,)).fetchone()[0],1)
        db.close()
        for _ in range(app.RATE_MAX_REQUESTS):app.rate_limit(self.owner,"/api/generate")
        with self.assertRaises(app.APIError):app.rate_limit(self.owner,"/api/generate")

    def test_unsupported_or_oversized_upload_creates_no_asset(self):
        import base64
        for name,raw in [("photo.webp",b"not a supported photo"),("large.png",b"x"*5000001)]:
            code,_,_=self.request("/api/attachments","POST",{"project_id":self.project_id,"name":name,"content_base64":base64.b64encode(raw).decode()},self.cookie,self.csrf)
            self.assertEqual(code,400)
        db=app.connect()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM project_assets WHERE project_id=?",(self.project_id,)).fetchone()[0],0)
        db.close()

    def test_local_poppins_fonts_have_explicit_static_allowlist(self):
        for weight in ["Regular","Medium","SemiBold","Bold"]:
            code,headers,body=self.request("/fonts/Poppins-"+weight+".ttf")
            self.assertEqual(code,200)
            self.assertEqual(headers["Content-Type"],"font/ttf")
            self.assertTrue(len(body)>10000)
        self.assertEqual(self.request("/fonts/../../app.py")[0],404)
