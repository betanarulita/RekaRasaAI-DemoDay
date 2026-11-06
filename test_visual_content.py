import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

import test_app as workflow
from test_app import planner_result, planner_task
import app
from visual_content import CHANNELS, CompositionError, composition_svg, extract_image_copy


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII=")
COPY = ("HEADLINE: FreshGlow untuk sehari-hari\n"
        "BODY: Pelembap wajah untuk penggunaan harian dengan tekstur ringan.\n"
        "CTA: Kenali FreshGlow\n"
        "CAPTION: FreshGlow adalah pelembap wajah untuk penggunaan harian. Teksturnya ringan.\n"
        "VISUAL: Konsep permukaan netral dengan ruang untuk teks. Bentuk kemasan belum diketahui.")


class VisualWorkflowTests(unittest.TestCase):
    request = workflow.WorkflowTests.request
    register = workflow.WorkflowTests.register
    project = workflow.WorkflowTests.project
    task = workflow.WorkflowTests.task

    def setUp(self):
        mail = patch.object(app, "SMTP_ENABLED", False)
        mail.start()
        self.addCleanup(mail.stop)
        workflow.WorkflowTests.setUp(self)
        folder = tempfile.TemporaryDirectory(prefix="rekarasa-visual-")
        self.addCleanup(folder.cleanup)
        storage = patch.object(app, "IMAGE_STORAGE_PATH", Path(folder.name))
        storage.start()
        self.addCleanup(storage.stop)
        self.cookie, self.csrf, self.owner = self.register()
        self.project_id = self.project(self.owner, "FreshGlow")

    def seed_visual(self, content=COPY, status="approved_pending_human", review="Pass"):
        task_id, version_id = self.task(self.owner, self.project_id, content=content, status=status, review=review)
        db = app.connect()
        db.execute("UPDATE tasks SET format='Poster or static ad',platform='Instagram' WHERE id=?", (task_id,))
        db.execute("UPDATE content_versions SET review_status=? WHERE id=?", ("pass" if review == "Pass" else "fail", version_id))
        db.commit()
        db.close()
        with patch.object(app, "call_image_provider", return_value=(PNG, "image/png")):
            code, _, data = self.request("/api/generate-image", "POST", {"task_id": task_id, "prompt": "A plain neutral concept, no text", "ratio": "portrait"}, self.cookie, self.csrf)
        self.assertEqual(code, 201, data)
        return task_id, version_id, data["image"]["id"]

    def compose(self, image_id, version_id=None):
        return self.request("/api/compose-visual", "POST", {"image_id": image_id, "version_id": version_id}, self.cookie, self.csrf)

    def approve_copy(self, task_id):
        code, _, data = self.request("/api/approve", "POST", {"task_id": task_id, "note": "Explicit human copy approval"}, self.cookie, self.csrf)
        self.assertEqual(code, 200, data)

    def approve_visual(self, composition_id, inspected=True):
        return self.request("/api/approve-visual", "POST", {"composition_id": composition_id, "inspected_image": inspected, "note": "Inspected concept, image details, and every displayed word"}, self.cookie, self.csrf)

    def test_freshglow_image_copy_review_and_explicit_asset_approval_persist(self):
        task_id, version_id, image_id = self.seed_visual()
        code, _, data = self.compose(image_id, version_id)
        self.assertEqual(code, 201, data)
        composition = data["composition"]
        self.assertEqual(composition["status"], "pending_copy_approval")
        self.assertEqual(composition["copy"]["body"], "Pelembap wajah untuk penggunaan harian dengan tekstur ringan.")
        code, _, svg = self.request(composition["preview_url"], cookie=self.cookie)
        self.assertEqual(code, 200)
        root = ElementTree.fromstring(svg)
        text = " ".join(node.text or "" for node in root.findall("{http://www.w3.org/2000/svg}text"))
        for value in composition["copy"].values():
            self.assertIn(value, text)
        for unsupported in ("jerawat", "klinis", "halal", "aman untuk semua", "cepat meresap"):
            self.assertNotIn(unsupported, text)
        self.assertNotIn("Bentuk kemasan", text)
        self.assertEqual(self.approve_visual(composition["id"])[0], 409)
        self.assertEqual(self.request(composition["preview_url"] + "&download=1", cookie=self.cookie)[0], 409)
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(composition["id"], inspected=False)[0], 409)
        code, _, approved = self.approve_visual(composition["id"])
        self.assertEqual(code, 200, approved)
        self.assertEqual(approved["composition"]["status"], "human_approved")
        code, headers, final = self.request(approved["composition"]["download_url"], cookie=self.cookie)
        self.assertEqual(code, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(final, svg)
        self.assertEqual(self.approve_visual(composition["id"])[0], 200)
        reopened = app.connect()
        stored = reopened.execute("SELECT * FROM visual_compositions WHERE id=?", (composition["id"],)).fetchone()
        self.assertEqual(stored["version_id"], version_id)
        self.assertEqual(stored["image_id"], image_id)
        self.assertEqual(stored["image_sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(stored["render_sha256"], hashlib.sha256(svg).hexdigest())
        self.assertEqual(stored["svg_content"], svg)
        self.assertEqual(stored["approved_by"], self.owner)
        self.assertTrue(stored["approved_at"])
        self.assertEqual(reopened.execute("SELECT count(*) FROM approvals WHERE version_id=? AND decision='approved'", (version_id,)).fetchone()[0], 1)
        self.assertEqual(reopened.execute("SELECT count(*) FROM audit_events WHERE task_id=? AND event='visual.approved'", (task_id,)).fetchone()[0], 1)
        self.assertEqual(reopened.execute("SELECT count(*) FROM audit_events WHERE task_id=? AND event='visual.approval_blocked'", (task_id,)).fetchone()[0], 2)
        reopened.close()

    def test_approved_snapshot_survives_renderer_changes_and_is_exported(self):
        task_id, _, image_id = self.seed_visual()
        _, _, data = self.compose(image_id)
        visual = data["composition"]
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(visual["id"])[0], 200)
        _, _, original = self.request(visual["preview_url"], cookie=self.cookie)
        with patch.object(app, "composition_svg", side_effect=RuntimeError("A later renderer must not change an approved asset")):
            code, _, downloaded = self.request(visual["preview_url"] + "&download=1", cookie=self.cookie)
        self.assertEqual(code, 200)
        self.assertEqual(downloaded, original)
        code, _, export = self.request("/api/export", cookie=self.cookie)
        self.assertEqual(code, 200, export)
        stored = export["visual_compositions"][0]
        self.assertEqual(base64.b64decode(stored["svg_content_base64"]), original)

    def test_modified_snapshot_is_not_approved_or_exported(self):
        task_id, _, image_id = self.seed_visual()
        _, _, data = self.compose(image_id)
        visual = data["composition"]
        self.approve_copy(task_id)
        db = app.connect()
        db.execute("UPDATE visual_compositions SET svg_content=? WHERE id=?", (b"changed snapshot", visual["id"]))
        db.commit()
        db.close()
        code, _, body = self.approve_visual(visual["id"])
        self.assertEqual(code, 409, body)
        self.assertEqual(body["code"], "visual_changed")
        self.assertEqual(self.request(visual["preview_url"], cookie=self.cookie)[0], 409)

    def test_edit_invalidates_visual_export_and_requires_new_composition(self):
        task_id, version_id, image_id = self.seed_visual()
        _, _, data = self.compose(image_id, version_id)
        visual = data["composition"]
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(visual["id"])[0], 200)
        code, _, edited = self.request("/api/edit", "POST", {"task_id": task_id, "content": COPY.replace("Kenali FreshGlow", "Lihat FreshGlow")}, self.cookie, self.csrf)
        self.assertEqual(code, 201, edited)
        self.assertEqual(self.request(visual["preview_url"] + "&download=1", cookie=self.cookie)[0], 409)
        self.assertEqual(self.approve_visual(visual["id"])[0], 409)
        self.assertEqual(self.compose(image_id, version_id)[0], 409)
        code, _, composed = self.compose(image_id)
        self.assertEqual(code, 201, composed)
        self.assertEqual(composed["composition"]["status"], "needs_review")
        self.assertIsNone(composed["composition"]["approved_at"])

    def test_composition_retry_is_idempotent_and_new_image_is_not_approved(self):
        task_id, version_id, image_id = self.seed_visual()
        _, _, first = self.compose(image_id, version_id)
        code, _, second = self.compose(image_id, version_id)
        self.assertEqual(code, 200, second)
        self.assertEqual(first["composition"]["id"], second["composition"]["id"])
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(first["composition"]["id"])[0], 200)
        with patch.object(app, "call_image_provider", return_value=(PNG, "image/png")):
            code, _, generated = self.request("/api/generate-image", "POST", {"task_id": task_id, "prompt": "Another composition", "ratio": "square"}, self.cookie, self.csrf)
        self.assertEqual(code, 201, generated)
        _, _, composed = self.compose(generated["image"]["id"])
        self.assertEqual(composed["composition"]["status"], "pending_visual_approval")
        self.assertIsNone(composed["composition"]["approved_at"])

    def test_model_failure_leaves_no_images_or_visual_approvals(self):
        task_id, _ = self.task(self.owner, self.project_id)
        with patch.object(app, "call_image_provider", side_effect=app.APIError(504, "Timeout", "image_provider_timeout")):
            code, _, body = self.request("/api/generate-image", "POST", {"task_id": task_id, "prompt": "Neutral concept"}, self.cookie, self.csrf)
        self.assertEqual(code, 504, body)
        db = app.connect()
        for table in ("generated_images", "visual_compositions", "approvals"):
            self.assertEqual(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
        db.close()
        self.assertEqual(list(app.IMAGE_STORAGE_PATH.iterdir()), [])

    def test_foreign_account_cannot_read_compose_or_approve_visual(self):
        _, _, image_id = self.seed_visual()
        _, _, data = self.compose(image_id)
        visual = data["composition"]
        cookie, csrf, _ = self.register("other@example.test")
        for path in (visual["preview_url"], visual["preview_url"] + "&download=1"):
            self.assertEqual(self.request(path, cookie=cookie)[0], 404)
        self.assertEqual(self.request("/api/compose-visual", "POST", {"image_id": image_id}, cookie, csrf)[0], 404)
        self.assertEqual(self.request("/api/approve-visual", "POST", {"composition_id": visual["id"], "inspected_image": True}, cookie, csrf)[0], 404)
        self.assertEqual(self.request("/api/approve-visual", "POST", {"composition_id": visual["id"]}, self.cookie)[0], 403)

    def test_overlong_copy_cannot_be_silently_truncated_or_saved(self):
        _, _, image_id = self.seed_visual(content="HEADLINE: " + "x" * 81)
        code, _, data = self.compose(image_id)
        self.assertEqual(code, 400, data)
        self.assertEqual(data["code"], "invalid_visual_copy")
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM visual_compositions").fetchone()[0], 0)
        db.close()

    def test_changed_base_image_cannot_be_approved_or_exported(self):
        task_id, _, image_id = self.seed_visual()
        _, _, data = self.compose(image_id)
        visual = data["composition"]
        self.approve_copy(task_id)
        (app.IMAGE_STORAGE_PATH / (image_id + ".png")).write_bytes(PNG + b"changed")
        code, _, body = self.approve_visual(visual["id"])
        self.assertEqual(code, 409, body)
        self.assertEqual(body["code"], "image_changed")

    def test_text_free_hero_and_legacy_image_rows_remain_available(self):
        task_id, _, image_id = self.seed_visual(content="CAPTION: FreshGlow adalah pelembap wajah harian. Teksturnya ringan.\nVISUAL: Konsep netral, tanpa klaim atau teks.")
        _, _, data = self.compose(image_id)
        self.assertFalse(any(data["composition"]["copy"].values()))
        code, _, body = self.request("/api/images?task_id=" + task_id, cookie=self.cookie)
        self.assertEqual(code, 200, body)
        self.assertEqual(body["images"][0]["id"], image_id)
        self.assertEqual(body["default_ratio"], "portrait")
        self.assertEqual(body["default_prompt"], "Konsep netral, tanpa klaim atau teks.")
        app.init_db()
        self.assertEqual(self.request(body["images"][0]["media_url"], cookie=self.cookie)[0], 200)

    def test_writer_visual_direction_reaches_the_image_provider(self):
        task_id, version_id, _ = self.seed_visual()
        with patch.object(app, "call_image_provider", return_value=(PNG, "image/png")) as provider:
            code, _, body = self.request("/api/generate-image", "POST", {"task_id": task_id, "prompt": "Soft daylight", "ratio": "landscape"}, self.cookie, self.csrf)
        self.assertEqual(code, 201, body)
        prompt, size = provider.call_args.args
        self.assertIn("Konsep permukaan netral", prompt)
        self.assertIn("Soft daylight", prompt)
        self.assertIn("no text, lettering, logos", prompt)
        self.assertEqual(size, "1344x768")
        db = app.connect()
        event = db.execute("SELECT details FROM audit_events WHERE event='image.generated' ORDER BY rowid DESC LIMIT 1").fetchone()
        self.assertEqual(json.loads(event["details"])["copy_version_id"], version_id)
        db.close()

    def test_six_channels_without_format_are_preserved_and_grounded(self):
        channels = list(CHANNELS)
        tasks = [planner_task("Photo post" if name == "TikTok" else "Poster or static ad", platform=name) for name in channels]
        def planner(role, instructions, payload, contract):
            self.assertEqual(role, "Planner")
            self.assertEqual(payload["output_preferences"], [])
            self.assertEqual(payload["platform_preferences"], channels)
            self.assertIn("photo post", instructions)
            return planner_result(*tasks, product_facts=["Teksturnya ringan.", "Menyembuhkan jerawat."]), {}
        with patch.object(app, "llm_json", side_effect=planner):
            code, _, data = self.request("/api/plan", "POST", {"project_id": self.project_id, "brief": "FreshGlow adalah pelembap wajah untuk penggunaan harian. Teksturnya ringan. Buat konten gambar.", "platform_preferences": channels, "auto_confirm": True}, self.cookie, self.csrf)
        self.assertEqual(code, 201, data)
        self.assertNotIn("tasks", data, "Removed unsupported facts require explicit plan confirmation")
        self.assertEqual(data["plan"]["product_facts"], ["Teksturnya ringan."])
        code, _, confirmed = self.request("/api/confirm-plan", "POST", {"plan_id": data["plan_id"]}, self.cookie, self.csrf)
        self.assertEqual(code, 200, confirmed)
        self.assertEqual({task["platform"] for task in confirmed["tasks"]}, set(channels))
        for task in confirmed["tasks"]:
            self.assertTrue(task["selection_reason"])
            self.assertEqual(task["format"], "Photo post" if task["platform"] == "TikTok" else "Poster or static ad")

    def test_missing_channel_fails_before_history_and_retry_does_not_duplicate(self):
        payload = {"project_id": self.project_id, "brief": "Buat poster FreshGlow untuk Instagram dan X.", "platform_preferences": ["Instagram", "X"], "auto_confirm": True}
        with patch.object(app, "llm_json", return_value=(planner_result(planner_task("Poster", platform="Instagram")), {})):
            self.assertEqual(self.request("/api/plan", "POST", payload, self.cookie, self.csrf)[0], 502)
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM conversations WHERE project_id=?", (self.project_id,)).fetchone()[0], 0)
        db.close()
        result = planner_result(*(planner_task("Poster", platform=name) for name in ("Instagram", "X")))
        with patch.object(app, "llm_json", return_value=(result, {})):
            code, _, data = self.request("/api/plan", "POST", payload, self.cookie, self.csrf)
        self.assertEqual(code, 201, data)
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM tasks WHERE project_id=?", (self.project_id,)).fetchone()[0], 2)
        db.close()

    def test_revision_limit_cannot_be_bypassed_by_visual_approval(self):
        task_id, _, image_id = self.seed_visual(status="escalated", review="Fail")
        db = app.connect()
        db.execute("UPDATE tasks SET remediation_count=3 WHERE id=?", (task_id,))
        db.commit()
        db.close()
        _, _, data = self.compose(image_id)
        self.assertEqual(self.approve_visual(data["composition"]["id"])[0], 409)
        with patch.object(app, "llm_json") as provider:
            self.assertEqual(self.request("/api/revise", "POST", {"task_id": task_id}, self.cookie, self.csrf)[0], 409)
            provider.assert_not_called()

    def test_acne_cure_is_rejected_even_when_the_model_returns_pass(self):
        task_id, version_id, _ = self.seed_visual(content=COPY.replace("Pelembap wajah untuk penggunaan harian dengan tekstur ringan.", "FreshGlow menyembuhkan jerawat dalam 7 hari."))
        findings = [{"criterion": rule_id, "result": "Pass", "claim": "", "rule_id": rule_id, "evidence_source_id": None, "explanation": "Model claims this is fine.", "recommendation": "None."} for rule_id, _, _ in app.RULES]
        db = app.connect()
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        version = db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone()
        review = app.save_review(db, self.owner, task, version, findings, set(), [])
        self.assertEqual(review["verdict"], "Fail")
        guard = next(finding for finding in review["findings"] if finding["result"] == "Fail")
        self.assertEqual(guard["rule_id"], "DEMO-CLAIM-001")
        self.assertEqual(version["content"][guard["span_start"]:guard["span_end"]], guard["claim"])
        db.commit()
        db.close()
        self.assertEqual(self.request("/api/approve", "POST", {"task_id": task_id}, self.cookie, self.csrf)[0], 409)


class VisualLayoutTests(unittest.TestCase):
    def test_literal_newline_block_separators_do_not_swallow_copy(self):
        text = r"HEADLINE: Kopi Senja\nBODY: Tekstur ringan\nCTA: Pesan sekarang\nCAPTION: Caption terpisah\nVISUAL: Coffee on a desk"
        result = extract_image_copy(text)
        self.assertEqual(result, {"headline":"Kopi Senja", "body":"Tekstur ringan", "cta":"Pesan sekarang"})


    def test_short_freshglow_copy_fits_all_supported_canvas_ratios(self):
        for size in app.IMAGE_SIZES.values():
            with self.subTest(size=size):
                svg = composition_svg(PNG, "image/png", size, extract_image_copy(COPY))
                root = ElementTree.fromstring(svg)
                self.assertEqual(root.attrib["width"] + "x" + root.attrib["height"], size)
                self.assertEqual(" ".join(node.text for node in root.findall("{http://www.w3.org/2000/svg}text")), " ".join(extract_image_copy(COPY).values()))

    def test_markup_is_escaped_and_caption_is_not_rendered(self):
        copy = extract_image_copy("HEADLINE: <script>alert(1)</script> & kopi\nBODY: Teks ringan\nCTA: Lihat\nCAPTION: Caption terpisah\nVISUAL: No text")
        svg = composition_svg(PNG, "image/png", "1024x1280", copy)
        root = ElementTree.fromstring(svg)
        self.assertFalse(root.findall(".//{http://www.w3.org/2000/svg}script"))
        self.assertNotIn(b"Caption terpisah", svg)
        self.assertIn(b"&lt;script&gt;", svg)

    def test_duplicate_blocks_and_overflow_are_rejected(self):
        with self.assertRaises(CompositionError):
            extract_image_copy("HEADLINE: One\nHEADLINE: Two")
        with self.assertRaises(CompositionError):
            composition_svg(PNG, "image/png", "1024x256", {"headline": "A headline " * 7, "body": "A body " * 20, "cta": "See more"})

    def test_channel_guidance_is_shared_by_writer_and_remediation(self):
        for channel in CHANNELS:
            for remediation in (False, True):
                prompt = app.writer_instructions("Static ad", remediation=remediation, platform=channel)
                self.assertIn("HEADLINE", prompt)
                self.assertIn("CAPTION", prompt)
                self.assertIn("source", prompt)
                self.assertIn(CHANNELS[channel]["direction"], prompt)


if __name__ == "__main__":
    unittest.main()
