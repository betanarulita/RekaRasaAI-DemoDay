import io
import base64
import json
import os
import sqlite3
import tempfile
import unittest
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="rekarasa-tests-")
os.environ["DATABASE_PATH"] = str(Path(TEMP.name) / "test.sqlite3")
import app


def planner_task(output_format, title="Planned output", platform="General", reason="This output fits the stated brief.", angle="Use a clear creative angle", goal="Help the audience understand"):
    return {"title":title,"format":output_format,"platform":platform,"angle":angle,"goal":goal,"selection_reason":reason}


def planner_result(*tasks, product_facts=None, missing_information=None):
    return {"objective":"Create useful content", "audience":"People interested in the product", "product_facts":product_facts or [], "constraints":[], "missing_information":missing_information or [], "tasks":list(tasks)}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        app.DB_PATH = Path(TEMP.name) / (self.id().replace(".", "_") + ".sqlite3")
        if app.DB_PATH.exists():
            app.DB_PATH.unlink()
        app.init_db()
        app.RATE_HITS.clear()

    def request(self, path, method="GET", body=None, cookie=None, csrf=None):
        raw = json.dumps(body or {}).encode()
        route, _, query = path.partition("?")
        env = {"REQUEST_METHOD": method, "PATH_INFO": route, "QUERY_STRING": query, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_HOST": "localhost"}
        if cookie:
            env["HTTP_COOKIE"] = cookie
        if csrf:
            env["HTTP_X_CSRF_TOKEN"] = csrf
        captured = {}
        result = app.application(env, lambda status, headers: captured.update(status=status, headers=dict(headers)))
        raw_result = b"".join(result)
        try:
            data = json.loads(raw_result)
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = raw_result
        return int(captured["status"].split()[0]), captured["headers"], data

    def register(self, email="owner@example.test"):
        status, headers, body = self.request("/api/register", "POST", {"email": email, "password": "test-password-123"})
        self.assertEqual(status, 200, body)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        return cookie, body["csrf"], body["user"]["id"]

    def project(self, owner, name="Test project"):
        db = app.connect()
        project_id = app.uid()
        db.execute("INSERT INTO projects VALUES(?,?,?,?)", (project_id, owner, name, app.now()))
        db.commit()
        db.close()
        return project_id

    def task(self, owner, project_id, status="needs_revision", remediation_count=0, content="A safe draft.", approved=False, review="Fail"):
        db = app.connect()
        conv, brief, plan, task_id, version_id = [app.uid() for _ in range(5)]
        db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (conv, owner, project_id, "Brief", app.now()))
        db.execute("INSERT INTO briefs VALUES(?,?,?,?,?,?,?)", (brief, conv, "Make content", "Audience", "Warm", json.dumps(["Social video script"]), app.now()))
        db.execute("INSERT INTO plans VALUES(?,?,?,?,?)", (plan, brief, json.dumps({"tasks": []}), "confirmed", app.now()))
        db.execute("INSERT INTO tasks(id,plan_id,project_id,format,deadline,publish_at,status,remediation_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (task_id, plan, project_id, "Social video script", None, None, status, remediation_count, app.now()))
        db.execute("INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)", (version_id, task_id, 1, content, "[]", "pass" if approved else "fail", int(approved), app.now()))
        if review:
            review_id = app.uid()
            db.execute("INSERT INTO review_runs VALUES(?,?,?,?,?)", (review_id, task_id, version_id, review, app.now()))
        db.commit()
        result = (task_id, version_id)
        db.close()
        return result

    def test_password_storage_uses_salt_and_verifies(self):
        first = app.password_hash("long-password-123")
        second = app.password_hash("long-password-123")
        self.assertNotEqual(first, second)
        self.assertTrue(app.verify_password("long-password-123", first))
        self.assertFalse(app.verify_password("wrong-password", first))

    def test_dotenv_loader_reads_values_without_overriding_process_environment(self):
        with tempfile.TemporaryDirectory(prefix="rekarasa-env-test-") as folder:
            path = Path(folder) / ".env"
            path.write_text("RR_DOTENV_TEST=file-value\nexport RR_DOTENV_QUOTED='quoted value'\n", encoding="utf-8")
            with patch.dict(os.environ, {"RR_DOTENV_TEST": "process-value"}, clear=False):
                app.load_dotenv(path)
                self.assertEqual(os.environ["RR_DOTENV_TEST"], "process-value")
                self.assertEqual(os.environ["RR_DOTENV_QUOTED"], "quoted value")
                os.environ.pop("RR_DOTENV_QUOTED", None)

    def test_groq_planner_request_uses_strict_json_schema_and_validates_response(self):
        planner = {"objective":"Introduce the drink", "audience":"Drink fans", "product_facts":[], "constraints":[], "missing_information":[], "tasks":[{"title":"A warm pause", "format":"Social video script", "platform":"TikTok", "angle":"A warm pause", "goal":"Introduce it", "selection_reason":"The brief asks for a short social video."}]}
        result = {"choices":[{"message":{"content":json.dumps(planner)}}], "usage":{"prompt_tokens":12,"completion_tokens":9}}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit): return json.dumps(result).encode()

        with patch.dict(os.environ, {"GROQ_API_KEY":"test-only-key"}), patch.object(app, "urlopen", return_value=FakeResponse()) as request:
            parsed, usage = app.llm_json("Planner", "Plan only", {"brief":"A ginger drink"}, app.PLAN_SCHEMA)
        sent = request.call_args.args[0]
        body = json.loads(sent.data)
        self.assertEqual(sent.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(body["model"], app.MODEL)
        self.assertEqual(body["max_completion_tokens"], 1800)
        self.assertEqual(body["response_format"]["json_schema"]["strict"], True)
        self.assertNotIn("minItems", json.dumps(body["response_format"]))
        self.assertEqual(parsed, planner)
        self.assertEqual(usage, {"input_tokens":12,"output_tokens":9})

    def test_groq_output_is_rejected_when_it_does_not_match_the_local_schema(self):
        result = {"choices":[{"message":{"content":"{}"}}], "usage":{}}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit): return json.dumps(result).encode()

        with patch.dict(os.environ, {"GROQ_API_KEY":"test-only-key"}), patch.object(app, "urlopen", return_value=FakeResponse()):
            with self.assertRaises(app.APIError) as raised:
                app.llm_json("Planner", "Plan only", {}, app.PLAN_SCHEMA)
        self.assertEqual(raised.exception.code, "provider_schema_invalid")

    def test_groq_auth_error_is_reported_without_leaking_the_api_key(self):
        error_body = json.dumps({"error":{"message":"Rejected credential test-only-key"}}).encode()
        upstream_error = HTTPError("https://api.groq.com/openai/v1/chat/completions", 403, "Forbidden", {}, io.BytesIO(error_body))
        with patch.dict(os.environ, {"GROQ_API_KEY":"test-only-key"}), patch.object(app, "urlopen", side_effect=upstream_error):
            with self.assertRaises(app.APIError) as raised:
                app.llm_json("Planner", "Plan only", {}, app.PLAN_SCHEMA)
        self.assertIn("HTTP 403", raised.exception.message)
        self.assertIn("[redacted]", raised.exception.message)
        self.assertNotIn("test-only-key", raised.exception.message)

    def test_groq_strict_schemas_require_every_field_and_disallow_extra_keys(self):
        def visit(contract):
            if contract.get("type") == "object":
                self.assertEqual(set(contract["required"]), set(contract["properties"]))
                self.assertFalse(contract["additionalProperties"])
                for child in contract["properties"].values(): visit(child)
            if contract.get("type") == "array": visit(contract["items"])
        for contract in (app.PLAN_SCHEMA, app.WRITER_SCHEMA, app.REVIEW_SCHEMA): visit(contract)

    def test_brief_without_output_preferences_is_planned(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner)
        result = planner_result(planner_task("Social media post", title="A first hello", platform="Instagram", reason="The brief asks for a concise introduction."))
        with patch.object(app, "llm_json", return_value=(result,{"input_tokens":5,"output_tokens":8})) as model:
            status, _, response = self.request("/api/plan", "POST", {"project_id":project,"brief":"Introduce the new studio in a warm social post."}, cookie, csrf)
        self.assertEqual(status, 201, response)
        self.assertEqual(model.call_args.args[2]["output_preferences"], [])
        self.assertEqual(response["plan"]["tasks"][0]["format"], "Social media post")
        db = app.connect()
        self.assertEqual(json.loads(db.execute("SELECT formats FROM briefs").fetchone()[0]), [])
        db.close()

    def test_poster_preference_produces_poster_task_and_keeps_unavailable_facts_out(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner)
        result = planner_result(planner_task("Poster or static ad", title="A warm welcome", reason="The requested poster is the clearest launch asset."), product_facts=["Open every day", "Free delivery"])
        with patch.object(app, "llm_json", return_value=(result,{"input_tokens":6,"output_tokens":7})) as model:
            status, _, response = self.request("/api/plan", "POST", {"project_id":project,"brief":"Create a warm poster announcing our new shop.","output_preferences":["Poster or static ad"]}, cookie, csrf)
        self.assertEqual(status, 201, response)
        self.assertEqual(response["plan"]["tasks"][0]["format"], "Poster or static ad")
        self.assertIn("poster", response["plan"]["tasks"][0]["selection_reason"].lower())
        self.assertEqual(response["plan"]["product_facts"], [])
        self.assertTrue(any("not found" in x for x in response["plan"]["missing_information"]))
        self.assertIn("HEADLINE, BODY, and CTA", app.writer_instructions("Poster or static ad"))
        self.assertIn("do not claim text has been rendered", app.writer_instructions("Poster or static ad"))
        self.assertEqual(model.call_args.args[2]["output_preferences"], ["Poster or static ad"])
        task_plan = response["plan"]["tasks"][0]
        status, _, confirmed = self.request("/api/confirm-plan", "POST", {"plan_id":response["plan_id"],"tasks":[task_plan]}, cookie, csrf)
        self.assertEqual(status, 200, confirmed)
        task_id = confirmed["tasks"][0]["id"]
        rules = [rule_id for rule_id, _, _ in app.RULES]

        def fake_writer_reviewer(role, system, payload, output_schema):
            if role == "Writer":
                self.assertIn("HEADLINE, BODY, and CTA", system)
                self.assertEqual(payload["this_task"]["selection_reason"], task_plan["selection_reason"])
                return {"drafts":[{"task_id":task_id,"content":"HEADLINE: Our new shop\nBODY: Welcome to our new shop.\nCTA: Visit us today.","source_ids":[]}]}, {"input_tokens":8,"output_tokens":8}
            return {"findings":[{"criterion":rule,"result":"Pass","claim":"","rule_id":rule,"evidence_source_id":None,"explanation":"Checked against the available brief and sources.","recommendation":"No change required."} for rule in rules]}, {"input_tokens":8,"output_tokens":8}

        with patch.object(app, "llm_json", side_effect=fake_writer_reviewer):
            status, _, generated = self.request("/api/generate", "POST", {"task_id":task_id}, cookie, csrf)
        self.assertEqual(status, 201, generated)
        self.assertEqual(generated["review"]["verdict"], "Pass")
        self.assertIn("HEADLINE:", generated["task"]["versions"][0]["content"])
        status, _, approved = self.request("/api/approve", "POST", {"task_id":task_id,"note":"Poster copy reviewed by a human."}, cookie, csrf)
        self.assertEqual(status, 200, approved)
        self.assertEqual(approved["task"]["status"], "human_approved")

    def test_planner_cannot_silently_drop_an_explicit_preference(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner)
        result = planner_result(planner_task("Poster or static ad", title="A simple announcement", reason="A visual announcement fits the brief."))
        with patch.object(app, "llm_json", return_value=(result,{"input_tokens":3,"output_tokens":3})):
            status, _, response = self.request("/api/plan", "POST", {"project_id":project,"brief":"Write a short video introducing the studio.","output_preferences":["Short-form video"]}, cookie, csrf)
        self.assertEqual(status, 502, response)
        self.assertEqual(response["code"], "invalid_agent_output")
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM briefs").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM plans").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM tasks").fetchone()[0], 0)
        db.close()

    def test_custom_format_can_be_planned_and_confirmed(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner)
        result = planner_result(planner_task("Custom: podcast intro", title="A short audio welcome", platform="Podcast", reason="The user requested an audio introduction."))
        with patch.object(app, "llm_json", return_value=(result,{"input_tokens":6,"output_tokens":7})):
            status, _, proposed = self.request("/api/plan", "POST", {"project_id":project,"brief":"Welcome new listeners to our show.","custom_format":"Podcast intro"}, cookie, csrf)
        self.assertEqual(status, 201, proposed)
        task_plan = proposed["plan"]["tasks"][0]
        self.assertEqual(task_plan["format"], "Custom: podcast intro")
        self.assertEqual(task_plan["selection_reason"], "The user requested an audio introduction.")
        status, _, confirmed = self.request("/api/confirm-plan", "POST", {"plan_id":proposed["plan_id"],"tasks":[task_plan]}, cookie, csrf)
        self.assertEqual(status, 200, confirmed)
        task_id = confirmed["tasks"][0]["id"]
        db = app.connect()
        stored = db.execute("SELECT format,platform FROM tasks WHERE id=?", (task_id,)).fetchone()
        self.assertEqual((stored["format"],stored["platform"]), ("Custom: podcast intro","Podcast"))
        self.assertEqual(db.execute("SELECT details FROM audit_events WHERE event='plan.confirmed'").fetchone()[0] is not None, True)
        self.assertEqual(app.serialize_task(db, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())["selection_reason"], task_plan["selection_reason"])
        db.close()

    def test_planner_failure_retry_leaves_no_partial_history_or_tasks(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner)
        result = planner_result(planner_task("Short-form video", title="A quick hello", platform="TikTok", reason="The brief requests a short vertical video."))
        with patch.object(app, "llm_json", side_effect=[app.APIError(502,"Model unavailable.","provider_unavailable"),(result,{"input_tokens":2,"output_tokens":4})]):
            status, _, failed = self.request("/api/plan", "POST", {"project_id":project,"brief":"Introduce the product in a short video."}, cookie, csrf)
            self.assertEqual(status, 502, failed)
            db = app.connect()
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM briefs").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM plans").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM tasks").fetchone()[0], 0)
            db.close()
            status, _, retried = self.request("/api/plan", "POST", {"project_id":project,"brief":"Introduce the product in a short video."}, cookie, csrf)
        self.assertEqual(status, 201, retried)
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT count(*) FROM briefs").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT count(*) FROM plans").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT count(*) FROM tasks").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT count(*) FROM agent_runs WHERE role='Planner'").fetchone()[0], 2)
        db.close()

    def test_schema_migration_is_recorded_and_repeatable(self):
        app.init_db()
        app.init_db()
        db = app.connect()
        # Derived from the migrations folder, so adding a migration does not
        # require editing this test. The point is that each file is applied
        # exactly once and re-running is a no-op.
        expected = max(int(path.name.split("_", 1)[0]) for path in (app.ROOT / "migrations").glob("[0-9][0-9][0-9]_*.sql"))
        self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], expected)
        self.assertEqual(db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], expected)
        self.assertTrue(db.execute("SELECT 1 FROM rule_registry WHERE id='DEMO-CLAIM-001'").fetchone())
        db.close()

    def test_task_detail_migration_preserves_existing_task_rows(self):
        with tempfile.TemporaryDirectory(prefix="rekarasa-migration-test-") as folder:
            path = Path(folder) / "prior.sqlite3"
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            db.executescript((Path(app.ROOT) / "migrations" / "001_initial.sql").read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations VALUES(1,?)", (app.now(),))
            owner, project, conversation, brief, plan, task = [app.uid() for _ in range(6)]
            timestamp = app.now()
            db.execute("INSERT INTO users VALUES(?,?,?,?)", (owner, "migration@example.test", "hash", timestamp))
            db.execute("INSERT INTO projects VALUES(?,?,?,?)", (project, owner, "Old project", timestamp))
            db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (conversation, owner, project, "Old brief", timestamp))
            db.execute("INSERT INTO briefs VALUES(?,?,?,?,?,?,?)", (brief, conversation, "Old brief", "Audience", "Tone", "[]", timestamp))
            old_plan = json.dumps({"tasks":[{"format":"Social video script","angle":"A warm pause","goal":"Introduce the product"}]})
            db.execute("INSERT INTO plans VALUES(?,?,?,?,?)", (plan, brief, old_plan, "confirmed", timestamp))
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)", (task, plan, project, "Social video script", None, None, "planned", 0, timestamp))
            db.commit()
            db.close()
            with patch.object(app, "DB_PATH", path):
                app.init_db()
                migrated = app.connect()
                row = migrated.execute("SELECT * FROM tasks WHERE id=?", (task,)).fetchone()
                self.assertEqual(row["format"], "Social video script")
                self.assertEqual(row["title"], "Social video script")
                self.assertEqual(row["platform"], "TikTok")
                self.assertEqual(row["angle"], "A warm pause")
                self.assertEqual(row["goal"], "Introduce the product")
                self.assertEqual(migrated.execute("SELECT count(*) FROM tasks WHERE id=?", (task,)).fetchone()[0], 1)
                migrated.close()

    def test_image_generation_uses_task_project_context_and_persists_private_png(self):
        cookie, csrf, owner = self.register()
        project = self.project(owner, "Ginger Studio")
        task_id, _ = self.task(owner, project)
        db = app.connect()
        db.execute("UPDATE tasks SET title='Warm pause',platform='TikTok',angle='Cozy morning',goal='Introduce the drink' WHERE id=?", (task_id,))
        db.execute("UPDATE briefs SET body='Promote our ginger drink',audience='Busy commuters',tone='Warm' WHERE id=(SELECT brief_id FROM plans WHERE id=(SELECT plan_id FROM tasks WHERE id=?))", (task_id,))
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?)", (app.uid(), project, "facts.md", "text/markdown", "Ginger and honey; 10 sachets.", app.now()))
        db.commit(); db.close()
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=")
        storage = Path(TEMP.name) / "image-files"
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-image-key"}), patch.object(app, "IMAGE_PROVIDER", "openai"), patch.object(app, "IMAGE_STORAGE_PATH", storage), patch.object(app, "call_image_provider", return_value=(image, "image/png")) as provider:
            status, _, created = self.request("/api/generate-image", "POST", {"task_id":task_id,"prompt":"Soft morning light, ceramic cup, ginger on linen","ratio":"portrait"}, cookie, csrf)
            self.assertEqual(status, 201, created)
            prompt, size = provider.call_args.args
            self.assertIn("Promote our ginger drink", prompt)
            self.assertIn("Busy commuters", prompt)
            self.assertIn("Warm pause", prompt)
            self.assertIn("Ginger and honey", prompt)
            self.assertIn("Soft morning light", prompt)
            self.assertEqual(size, "1024x1280")
            status, _, listed = self.request("/api/images?task_id="+task_id, cookie=cookie)
            self.assertEqual(status, 200)
            self.assertEqual(listed["images"][0]["task_id"], task_id)
            self.assertIn("Busy commuters", listed["default_prompt"])
            self.assertIn("Warm pause", listed["default_prompt"])
            self.assertIn("Cozy morning", listed["default_prompt"])
            db = app.connect()
            row = db.execute("SELECT project_id,task_id,provider,model,media_type,byte_size,storage_name FROM generated_images WHERE id=?", (created["image"]["id"],)).fetchone()
            self.assertEqual((row["project_id"], row["task_id"]), (project, task_id))
            self.assertEqual((row["provider"], row["model"], row["media_type"]), ("openai", app.IMAGE_MODEL, "image/png"))
            self.assertEqual(row["byte_size"], len(image))
            db.close()
            status, headers, fetched = self.request(created["image"]["media_url"], cookie=cookie)
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "image/png")
            self.assertEqual(fetched, image)
            self.assertTrue((storage / row["storage_name"]).is_file())

    def test_image_generation_missing_credentials_returns_setup_message(self):
        cookie, csrf, owner = self.register()
        task_id, _ = self.task(owner, self.project(owner))
        with patch.dict(os.environ, {"OPENAI_API_KEY":""}, clear=False), patch.object(app, "IMAGE_PROVIDER", "openai"):
            status, _, body = self.request("/api/generate-image", "POST", {"task_id":task_id,"prompt":"A warm product scene","ratio":"square"}, cookie, csrf)
        self.assertEqual(status, 503)
        self.assertEqual(body["code"], "image_provider_unconfigured")
        self.assertIn("OPENAI_API_KEY", body["error"])

    def test_image_provider_api_error_is_mapped_without_crashing(self):
        cookie, csrf, owner = self.register()
        task_id, _ = self.task(owner, self.project(owner))
        with patch.object(app, "call_image_provider", side_effect=app.APIError(502, "The image provider could not complete this request.", "image_provider_error")):
            status, _, body = self.request("/api/generate-image", "POST", {"task_id":task_id,"prompt":"A visual","ratio":"square"}, cookie, csrf)
        self.assertEqual(status, 502)
        self.assertEqual(body["code"], "image_provider_error")

    def test_comfyui_queues_standard_workflow_polls_history_and_fetches_png(self):
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=")

        class FakeResponse:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, limit): return self.payload

        def fake_urlopen(request, timeout=10):
            if request.full_url.endswith("/prompt"):
                body = json.loads(request.data)
                self.assertEqual(body["prompt"]["1"]["inputs"]["ckpt_name"], "sd15.safetensors")
                self.assertEqual(body["prompt"]["4"]["inputs"]["width"], 1024)
                self.assertEqual(body["prompt"]["4"]["inputs"]["height"], 1280)
                return FakeResponse(json.dumps({"prompt_id":"fake-job"}).encode())
            if request.full_url.endswith("/history/fake-job"):
                return FakeResponse(json.dumps({"fake-job":{"status":{"completed":True},"outputs":{"7":{"images":[{"filename":"result.png","subfolder":"","type":"output"}]}}}}).encode())
            self.assertIn("/view?filename=result.png", request.full_url)
            return FakeResponse(image)

        with patch.object(app, "IMAGE_PROVIDER", "comfyui"), patch.object(app, "COMFYUI_CHECKPOINT", "sd15.safetensors"), patch.object(app, "COMFYUI_URL", "http://127.0.0.1:8188"), patch.object(app, "urlopen", side_effect=fake_urlopen):
            actual, media_type = app.call_image_provider("A warm product scene", "1024x1280")
        self.assertEqual(actual, image)
        self.assertEqual(media_type, "image/png")

    def test_comfyui_requires_explicit_checkpoint_configuration(self):
        with patch.object(app, "IMAGE_PROVIDER", "comfyui"), patch.object(app, "COMFYUI_CHECKPOINT", ""):
            with self.assertRaises(app.APIError) as raised:
                app.call_image_provider("A visual", "1024x1024")
        self.assertEqual(raised.exception.code, "image_provider_unconfigured")

    def test_comfyui_timeout_returns_gateway_timeout_error(self):
        class FakeResponse:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, limit): return self.payload
        def fake_urlopen(request, timeout=10):
            if request.full_url.endswith("/prompt"):
                return FakeResponse(b'{"prompt_id":"slow-job"}')
            return FakeResponse(b'{}')
        with patch.object(app, "IMAGE_PROVIDER", "comfyui"), patch.object(app, "COMFYUI_CHECKPOINT", "sd15.safetensors"), patch.object(app, "COMFYUI_TIMEOUT", 1), patch.object(app, "urlopen", side_effect=fake_urlopen), patch.object(app.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(app.APIError) as raised:
                app.call_image_provider("A visual", "1024x1024")
        self.assertEqual(raised.exception.status, 504)
        self.assertEqual(raised.exception.code, "image_provider_timeout")

    def test_generated_image_file_requires_owner_session(self):
        cookie_a, csrf_a, owner_a = self.register("image-owner@example.test")
        task_id, _ = self.task(owner_a, self.project(owner_a))
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=")
        with patch.dict(os.environ, {"OPENAI_API_KEY":"test-image-key"}), patch.object(app, "IMAGE_PROVIDER", "openai"), patch.object(app, "IMAGE_STORAGE_PATH", Path(TEMP.name) / "image-files"), patch.object(app, "call_image_provider", return_value=(image, "image/png")):
            _, _, created = self.request("/api/generate-image", "POST", {"task_id":task_id,"prompt":"Visual","ratio":"square"}, cookie_a, csrf_a)
        cookie_b, _, _ = self.register("other-image-owner@example.test")
        status, _, body = self.request(created["image"]["media_url"], cookie=cookie_b)
        self.assertEqual(status, 404)
        self.assertEqual(body["code"], "not_found")

    def test_csrf_is_required_for_mutations(self):
        cookie, csrf, _ = self.register()
        status, _, _ = self.request("/api/projects", "POST", {"name": "No CSRF"}, cookie)
        self.assertEqual(status, 403)
        status, _, body = self.request("/api/projects", "POST", {"name": "Has CSRF"}, cookie, csrf)
        self.assertEqual(status, 201, body)

    def test_accounts_cannot_read_another_owners_project_sources(self):
        cookie_a, csrf_a, owner_a = self.register("a@example.test")
        project_a = self.project(owner_a)
        cookie_b, csrf_b, owner_b = self.register("b@example.test")
        status, _, body = self.request("/api/sources", "POST", {"project_id": project_a, "name": "facts.md", "content": "Private facts", "media_type": "text/markdown"}, cookie_b, csrf_b)
        self.assertEqual(status, 404)
        self.assertEqual(body["code"], "not_found")
        self.assertNotEqual(owner_a, owner_b)

    def test_source_references_must_belong_to_project(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        db = app.connect()
        with self.assertRaises(app.APIError) as raised:
            app.source_payload(db, project_id, ["invented-source-id"])
        self.assertEqual(raised.exception.code, "invalid_source_reference")
        db.close()

    def test_conversations_can_be_reopened_and_continued_without_duplication(self):
        cookie, csrf, _ = self.register()
        db = app.connect()
        project = db.execute("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1").fetchone()[0]
        db.close()
        planner = {"objective":"Product introduction", "audience":"Drink fans", "product_facts":[], "constraints":[], "missing_information":[], "tasks":[{"title":"Warm pause", "format":"Social video script", "platform":"TikTok", "angle":"Warm pause", "goal":"Introduce drink", "selection_reason":"A short social video fits the brief."}]}
        with patch.object(app, "llm_json", return_value=(planner,{"input_tokens":10,"output_tokens":10})):
            status, _, first = self.request("/api/plan", "POST", {"project_id":project,"brief":"First brief","audience":"Drink fans","tone":"Warm","formats":["Social video script"]}, cookie, csrf)
            self.assertEqual(status, 201, first)
            status, _, opened = self.request("/api/conversation?id="+first["conversation_id"], cookie=cookie)
            self.assertEqual(status, 200, opened)
            self.assertEqual(opened["conversation"]["brief"], "First brief")
            status, _, continued = self.request("/api/plan", "POST", {"project_id":project,"conversation_id":first["conversation_id"],"brief":"Continued brief","audience":"Drink fans","tone":"Warm","formats":["Social video script"]}, cookie, csrf)
            self.assertEqual(status, 201, continued)
        self.assertEqual(continued["conversation_id"], first["conversation_id"])
        status, _, history = self.request("/api/history", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(len(history["conversations"]), 1)
        self.assertEqual(history["conversations"][0]["brief"], "Continued brief")

    def test_demo_cure_rule_rejects_a_disease_cure_claim(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id, content="Jahe ini membuat maag saya sembuh total!")
        db = app.connect()
        review = app.save_review(db, owner, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone(), db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone(), [], set())
        db.commit()
        finding = next(f for f in review["findings"] if f["rule_id"] == "DEMO-CLAIM-001")
        self.assertEqual(finding["result"], "Fail")
        self.assertIn("not legal advice", db.execute("SELECT text FROM rule_registry WHERE id='DEMO-CLAIM-001'").fetchone()[0])
        self.assertEqual(review["verdict"], "Fail")
        db.close()

    def test_invalid_rule_and_source_references_are_not_trusted(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id)
        db = app.connect()
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        version = db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone()
        review = app.save_review(db, owner, task, version, [{"criterion":"Evidence", "result":"Pass", "claim":"100% organic", "rule_id":"MADE-UP", "evidence_source_id":"missing", "explanation":"Looks good", "recommendation":"None"}], set())
        db.commit()
        finding = review["findings"][0]
        self.assertEqual(finding["result"], "Needs Evidence")
        self.assertIsNone(finding["rule_id"])
        self.assertTrue(finding["invalid_reference"])
        db.close()

    def test_passing_claim_without_source_is_downgraded(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id)
        db = app.connect()
        review = app.save_review(db, owner, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone(), db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone(), [{"criterion":"Product fact", "result":"Pass", "claim":"Made from ginger", "rule_id":"DEMO-FACT-001", "evidence_source_id":None, "explanation":"Supported", "recommendation":"None"}], set())
        self.assertEqual(review["findings"][0]["result"], "Needs Evidence")
        db.close()

    def test_a_prohibition_rule_can_pass_without_citing_a_source(self):
        # "No halal claim is present" has no source to cite; demanding one made
        # every approval impossible, which is what this test locks down.
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id, content="A warm ginger and honey drink.", review=None)
        findings = [
            {"criterion": rule_id, "result": "Pass", "claim": "Checked; nothing prohibited found.", "rule_id": rule_id, "evidence_source_id": None, "explanation": "Checked against the draft.", "recommendation": "None."}
            for rule_id in ("DEMO-CLAIM-001", "DEMO-HALAL-001", "DEMO-TONE-001")
        ]
        findings.append({"criterion": "Product fact", "result": "Pass", "claim": "", "rule_id": "DEMO-FACT-001", "evidence_source_id": None, "explanation": "No product claim to support.", "recommendation": "None."})
        db = app.connect()
        review = app.save_review(db, owner, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone(), db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone(), findings, set())
        self.assertEqual(review["verdict"], "Pass")
        db.close()

    def test_a_factual_pass_still_needs_a_source(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id, content="Made from ginger and honey.", review=None)
        findings = [{"criterion": "Product fact", "result": "Pass", "claim": "Made from ginger and honey", "rule_id": "DEMO-FACT-001", "evidence_source_id": None, "explanation": "Supported.", "recommendation": "None."}]
        db = app.connect()
        review = app.save_review(db, owner, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone(), db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone(), findings, set())
        self.assertEqual(review["verdict"], "Needs Evidence")
        db.close()

    def test_an_undocumented_halal_claim_fails_even_when_the_model_passes_it(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id, content="Jahe Rasa is halal certified and gentle on the stomach.", review=None)
        findings = [
            {"criterion": rule_id, "result": "Pass", "claim": "", "rule_id": rule_id, "evidence_source_id": None, "explanation": "Checked.", "recommendation": "None."}
            for rule_id in ("DEMO-CLAIM-001", "DEMO-FACT-001", "DEMO-HALAL-001", "DEMO-TONE-001")
        ]
        db = app.connect()
        review = app.save_review(db, owner, db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone(), db.execute("SELECT * FROM content_versions WHERE id=?", (version_id,)).fetchone(), findings, set(), [])
        self.assertEqual(review["verdict"], "Fail")
        halal = [f for f in review["findings"] if f["rule_id"] == "DEMO-HALAL-001"]
        self.assertTrue(any(f["result"] == "Fail" for f in halal))
        db.close()

    def test_a_rate_limited_call_is_retried_before_failing(self):
        planner = {"objective":"Introduce the drink", "audience":"Drink fans", "product_facts":[], "constraints":[], "missing_information":[], "tasks":[{"title":"A warm pause", "format":"Social video script", "platform":"TikTok", "angle":"A warm pause", "goal":"Introduce it", "selection_reason":"The brief asks for a short social video."}]}
        result = {"choices":[{"message":{"content":json.dumps(planner)}}], "usage":{"prompt_tokens":1,"completion_tokens":1}}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _limit): return json.dumps(result).encode()

        attempts = []

        def fake_urlopen(request, timeout=None):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                raise HTTPError(request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
            return FakeResponse()

        with patch.dict(os.environ, {"GROQ_API_KEY":"test-only-key"}), patch.object(app, "urlopen", side_effect=fake_urlopen), patch.object(app, "LLM_BACKOFF_SECONDS", 0):
            parsed, _ = app.llm_json("Planner", "Plan only", {"brief":"A ginger drink"}, app.PLAN_SCHEMA)
        self.assertEqual(parsed, planner)
        self.assertEqual(len(attempts), 2)

    def test_three_remediations_is_a_hard_server_limit(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="needs_revision", remediation_count=3)
        status, _, body = self.request("/api/revise", "POST", {"task_id": task_id}, cookie, csrf)
        self.assertEqual(status, 409, body)
        self.assertEqual(body["code"], "iteration_limit")
        db = app.connect()
        self.assertEqual(db.execute("SELECT remediation_count FROM tasks WHERE id=?", (task_id,)).fetchone()[0], 3)
        db.close()

    def test_human_cannot_approve_without_a_passing_latest_review(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="needs_revision", review="Fail")
        status, _, body = self.request("/api/approve", "POST", {"task_id": task_id}, cookie, csrf)
        self.assertEqual(status, 409, body)
        self.assertEqual(body["code"], "approval_blocked")

    def test_edit_after_approval_creates_a_new_unapproved_version(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="human_approved", content="Approved copy", approved=True, review="Pass")
        status, _, body = self.request("/api/edit", "POST", {"task_id": task_id, "content":"An edited version."}, cookie, csrf)
        self.assertEqual(status, 201, body)
        latest = body["task"]["versions"][-1]
        self.assertEqual(latest["review_status"], "pending")
        self.assertEqual(latest["human_approved"], 0)
        self.assertEqual(body["task"]["status"], "needs_revision")

    def test_provider_failure_is_explicit_and_does_not_fabricate_success(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaises(app.APIError) as raised:
                app.llm_json("Planner", "system", {}, app.PLAN_SCHEMA)
        self.assertEqual(raised.exception.code, "provider_unconfigured")

    def test_agent_schemas_are_closed_and_have_required_contracts(self):
        self.assertEqual(app.PLAN_SCHEMA["additionalProperties"], False)
        self.assertEqual(set(app.PLAN_SCHEMA["required"]), set(app.PLAN_SCHEMA["properties"]))
        self.assertEqual(app.WRITER_SCHEMA["additionalProperties"], False)
        self.assertEqual(app.REVIEW_SCHEMA["additionalProperties"], False)
        self.assertIn("findings", app.REVIEW_SCHEMA["required"])

    def test_orchestrated_brief_to_review_to_human_approval(self):
        cookie, csrf, _ = self.register()
        db = app.connect()
        project = db.execute("SELECT id FROM projects ORDER BY created_at DESC LIMIT 1").fetchone()[0]
        source = db.execute("SELECT id FROM sources WHERE project_id=?", (project,)).fetchone()[0]
        db.close()
        plan = {"objective":"Introduce the drink mix", "audience":"Warm drink fans", "product_facts":["Ginger and honey"], "constraints":["No medical claims"], "missing_information":[], "tasks":[{"title":"A warm pause", "format":"TikTok short-video script", "platform":"TikTok", "angle":"A warm pause", "goal":"Introduce the product", "selection_reason":"The brief asks to introduce the drink to social audiences."},{"title":"Product listing", "format":"Marketplace description", "platform":"Marketplace", "angle":"A clear product introduction", "goal":"Describe sourced product facts", "selection_reason":"A listing gives marketplace shoppers product details."}]}
        rules = [rule_id for rule_id, _, _ in app.RULES]

        def fake_provider(role, system, payload, output_schema):
            if role == "Planner":
                self.assertEqual(payload["output_preferences"], ["TikTok short-video script","Marketplace description"])
                return plan, {"input_tokens": 30, "output_tokens": 20}
            if role == "Writer":
                self.assertIn(payload["this_task"]["platform"], ("TikTok", "Marketplace"))
                self.assertTrue(payload["this_task"]["title"])
                self.assertTrue(payload["this_task"]["angle"])
                self.assertTrue(payload["this_task"]["goal"])
                content = "HOOK: A warm pause.\nSCENE 1: Show the drink.\nVOICEOVER: Ginger and honey for your afternoon.\nCTA: See product details." if payload["this_task"]["platform"] == "TikTok" else "PRODUCT TITLE: Ginger and honey drink\nDESCRIPTION: A warm drink made with ginger and honey."
                return {"drafts":[{"task_id":payload["this_task"]["id"], "content":content, "source_ids":[source]}]}, {"input_tokens": 40, "output_tokens": 35}
            return {"findings":[{"criterion":rule, "result":"Pass", "claim":"Supported product description", "rule_id":rule, "evidence_source_id":source, "explanation":"Checked against project source and brief.", "recommendation":"No change required."} for rule in rules]}, {"input_tokens": 50, "output_tokens": 25}

        with patch.object(app, "llm_json", side_effect=fake_provider):
            status, _, proposed = self.request("/api/plan", "POST", {"project_id":project, "brief":"Introduce a ginger honey drink without medical claims.", "audience":"Warm drink fans", "tone":"Warm and factual", "output_preferences":["TikTok short-video script","Marketplace description"]}, cookie, csrf)
            self.assertEqual(status, 201, proposed)
            edited_tasks = proposed["plan"]["tasks"]
            invalid_tasks = [dict(edited_tasks[0]), dict(edited_tasks[0])]
            status, _, invalid = self.request("/api/confirm-plan", "POST", {"plan_id":proposed["plan_id"], "tasks":invalid_tasks}, cookie, csrf)
            self.assertEqual(status, 400, invalid)
            edited_tasks[0]["title"] = "TikTok launch video"
            edited_tasks[0]["angle"] = "A quick afternoon pause"
            edited_tasks[1]["title"] = "Ginger drink listing"
            status, _, confirmed = self.request("/api/confirm-plan", "POST", {"plan_id":proposed["plan_id"], "tasks":edited_tasks}, cookie, csrf)
            self.assertEqual(status, 200, confirmed)
            self.assertEqual(len(confirmed["tasks"]), 2)
            self.assertEqual([task["format"] for task in confirmed["tasks"]], ["TikTok short-video script","Marketplace description"])
            task_ids = [task["id"] for task in confirmed["tasks"]]
            for task in confirmed["tasks"]:
                status, _, generated = self.request("/api/generate", "POST", {"task_id":task["id"]}, cookie, csrf)
                self.assertEqual(status, 201, generated)
                self.assertEqual(generated["task"]["title"], task["title"])
                self.assertEqual(generated["task"]["platform"], task["platform"])
                if task["platform"] == "TikTok":
                    self.assertIn("SCENE 1:", generated["task"]["versions"][0]["content"])
                else:
                    self.assertIn("PRODUCT TITLE:", generated["task"]["versions"][0]["content"])
                self.assertEqual(generated["review"]["verdict"], "Pass")
                self.assertEqual(generated["task"]["status"], "approved_pending_human")
                status, _, approved = self.request("/api/approve", "POST", {"task_id":task["id"], "note":"Approved for manual export."}, cookie, csrf)
                self.assertEqual(status, 200, approved)
                self.assertEqual(approved["task"]["status"], "human_approved")
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM approvals WHERE decision='approved'").fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT count(*) FROM tasks WHERE id IN (?,?)", task_ids).fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT count(*) FROM content_versions WHERE task_id IN (?,?)", task_ids).fetchone()[0], 2)
        self.assertGreaterEqual(db.execute("SELECT count(*) FROM audit_events WHERE task_id IN (?,?)", task_ids).fetchone()[0], 4)
        db.close()

    def test_freshglow_reject_revise_re_review_and_explicit_human_approval(self):
        cookie, csrf, owner = self.register("freshglow@example.test")
        project_id = self.project(owner, "FreshGlow")
        allowed_facts = [
            "FreshGlow adalah pelembap wajah untuk penggunaan harian.",
            "Teksturnya ringan.",
        ]
        initial_draft = "FreshGlow terbukti menyembuhkan jerawat dalam 7 hari! Teruji klinis, bersertifikat halal, dan aman untuk semua jenis kulit. Teksturnya ringan dan cepat meresap."
        revised_draft = "FreshGlow adalah pelembap wajah untuk penggunaan harian dengan tekstur ringan."
        db = app.connect()
        source_id = app.uid()
        db.execute(
            "INSERT INTO sources VALUES(?,?,?,?,?,?)",
            (source_id, project_id, "FreshGlow product facts.md", "text/markdown", " ".join(allowed_facts), app.now()),
        )
        db.commit()
        db.close()

        planner = planner_result(
            planner_task("Marketplace listing", title="FreshGlow daily moisturizer"),
            product_facts=allowed_facts,
        )
        rejected_claims = [
            ("DEMO-CLAIM-001", "terbukti menyembuhkan jerawat dalam 7 hari", "Disease cure claim has no supporting product evidence."),
            ("DEMO-FACT-001", "Teruji klinis", "No clinical test evidence is present in the project source."),
            ("DEMO-HALAL-001", "bersertifikat halal", "No halal certification is documented in the project source."),
            ("DEMO-FACT-001", "aman untuk semua jenis kulit", "No evidence supports universal skin safety."),
            ("DEMO-FACT-001", "cepat meresap", "Light texture does not establish fast absorption."),
        ]
        provider_calls = []

        def fake_provider(role, system, payload, output_schema):
            provider_calls.append((role, payload))
            if role == "Planner":
                return planner, {"input_tokens": 10, "output_tokens": 10}
            if role == "Writer":
                content = revised_draft if payload.get("prior_draft") == initial_draft else initial_draft
                return {"drafts": [{"task_id": payload["this_task"]["id"], "content": content, "source_ids": [source_id]}]}, {"input_tokens": 10, "output_tokens": 10}

            draft = payload["draft"]
            if draft == initial_draft:
                findings = [
                    {"criterion": claim, "result": "Fail", "claim": claim, "rule_id": rule_id, "evidence_source_id": None, "explanation": explanation, "recommendation": "Remove the unsupported claim."}
                    for rule_id, claim, explanation in rejected_claims
                ]
                findings.append({"criterion": "Tone", "result": "Pass", "claim": "", "rule_id": "DEMO-TONE-001", "evidence_source_id": None, "explanation": "No tone conflict identified.", "recommendation": "No change required."})
                return {"findings": findings}, {"input_tokens": 10, "output_tokens": 10}

            findings = [
                {"criterion": "Product facts", "result": "Pass", "claim": fact, "rule_id": "DEMO-FACT-001", "evidence_source_id": source_id, "explanation": "This statement is present in the FreshGlow source.", "recommendation": "No change required."}
                for fact in allowed_facts
            ]
            findings.extend([
                {"criterion": "Disease claims", "result": "Pass", "claim": "", "rule_id": "DEMO-CLAIM-001", "evidence_source_id": None, "explanation": "No disease claim remains.", "recommendation": "No change required."},
                {"criterion": "Halal certification", "result": "Pass", "claim": "", "rule_id": "DEMO-HALAL-001", "evidence_source_id": None, "explanation": "No certification claim remains.", "recommendation": "No change required."},
                {"criterion": "Tone", "result": "Pass", "claim": "", "rule_id": "DEMO-TONE-001", "evidence_source_id": None, "explanation": "The copy is neutral and factual.", "recommendation": "No change required."},
            ])
            return {"findings": findings}, {"input_tokens": 10, "output_tokens": 10}

        with patch.object(app, "llm_json", side_effect=fake_provider):
            status, _, proposed = self.request("/api/plan", "POST", {"project_id": project_id, "brief": " ".join(allowed_facts)}, cookie, csrf)
            self.assertEqual(status, 201, proposed)
            status, _, confirmed = self.request("/api/confirm-plan", "POST", {"plan_id": proposed["plan_id"], "tasks": proposed["plan"]["tasks"]}, cookie, csrf)
            self.assertEqual(status, 200, confirmed)
            task_id = confirmed["tasks"][0]["id"]

            status, _, generated = self.request("/api/generate", "POST", {"task_id": task_id}, cookie, csrf)
            self.assertEqual(status, 201, generated)
            self.assertEqual(generated["review"]["verdict"], "Fail")
            rejected_findings = generated["review"]["findings"]
            for _, claim, _ in rejected_claims:
                finding = next(item for item in rejected_findings if item["claim"] == claim)
                self.assertEqual(finding["result"], "Fail")
                self.assertTrue(finding["explanation"])
            self.assertEqual(generated["task"]["status"], "needs_revision")

            status, _, revised = self.request("/api/revise", "POST", {"task_id": task_id}, cookie, csrf)
            self.assertEqual(status, 201, revised)
            current = revised["task"]["versions"][-1]
            self.assertEqual(current["content"], revised_draft)
            for _, unsupported_claim, _ in rejected_claims:
                self.assertNotIn(unsupported_claim, current["content"])
            self.assertEqual(revised["review"]["verdict"], "Pass")
            self.assertEqual(revised["task"]["status"], "approved_pending_human")
            self.assertEqual(current["human_approved"], 0)
            self.assertEqual([role for role, _ in provider_calls], ["Planner", "Writer", "Reviewer", "Writer", "Reviewer"])
            self.assertEqual(provider_calls[0][1]["brief"], " ".join(allowed_facts))
            self.assertEqual(provider_calls[1][1]["sources"][0]["id"], source_id)
            self.assertEqual(provider_calls[1][1]["this_task"]["format"], "Marketplace listing")
            self.assertEqual(provider_calls[3][1]["prior_draft"], initial_draft)
            self.assertEqual(provider_calls[4][1]["draft"], revised_draft)

            pending_db = app.connect()
            pending_task = pending_db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            pending_version = pending_db.execute("SELECT human_approved FROM content_versions WHERE id=?", (current["id"],)).fetchone()
            self.assertEqual(pending_task["status"], "approved_pending_human")
            self.assertEqual(pending_version["human_approved"], 0)
            self.assertEqual(pending_db.execute("SELECT count(*) FROM approvals WHERE version_id=?", (current["id"],)).fetchone()[0], 0)
            pending_db.close()

            status, _, approval = self.request("/api/approve", "POST", {"task_id": task_id, "note": "Human approved the reviewed FreshGlow copy."}, cookie, csrf)
            self.assertEqual(status, 200, approval)
            self.assertEqual(approval["task"]["status"], "human_approved")

        persisted = app.connect()
        persisted_task = persisted.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        persisted_version = persisted.execute("SELECT human_approved FROM content_versions WHERE id=?", (current["id"],)).fetchone()
        approval_row = persisted.execute("SELECT decision,note FROM approvals WHERE version_id=?", (current["id"],)).fetchone()
        approval_event = persisted.execute("SELECT details FROM audit_events WHERE task_id=? AND event='human.approved'", (task_id,)).fetchone()
        self.assertEqual(persisted_task["status"], "human_approved")
        self.assertEqual(persisted_version["human_approved"], 1)
        self.assertEqual(approval_row["decision"], "approved")
        self.assertIn("Human approved", approval_row["note"])
        self.assertEqual(json.loads(approval_event["details"])["version_id"], current["id"])
        persisted.close()

    def test_calendar_dates_are_saved_separately(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id)
        status, _, body = self.request("/api/set-dates", "POST", {"task_id":task_id, "deadline":"2026-11-02", "publish_at":"2026-11-05T09:30:00+07:00"}, cookie, csrf)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["task"]["deadline"], "2026-11-02")
        self.assertEqual(body["task"]["publish_at"], "2026-11-05T09:30:00+07:00")
        self.assertEqual(body["task"]["status"], "needs_revision")

    def test_audit_and_content_versions_persist_after_reconnect(self):
        _, _, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id)
        db = app.connect()
        app.audit(db, owner, "test.persisted", {"task": task_id}, project_id, task_id)
        db.commit()
        db.close()
        reopened = app.connect()
        self.assertEqual(reopened.execute("SELECT count(*) FROM content_versions WHERE task_id=?", (task_id,)).fetchone()[0], 1)
        self.assertEqual(reopened.execute("SELECT count(*) FROM audit_events WHERE event='test.persisted'").fetchone()[0], 1)
        reopened.close()


    # --- Task lifecycle guards ---------------------------------------------
    # These lock the difference between "the review failed" and "a human
    # edited the draft". Both used to leave the task in needs_revision, which
    # let a Writer retry silently overwrite the human's work.

    def test_revise_is_refused_after_a_human_edit(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="needs_revision", review="Fail")
        status, _, edited = self.request("/api/edit", "POST", {"task_id": task_id, "content": "Human rewrite."}, cookie, csrf)
        self.assertEqual(status, 201, edited)
        status, _, body = self.request("/api/revise", "POST", {"task_id": task_id}, cookie, csrf)
        self.assertEqual(status, 409, body)
        self.assertEqual(body["code"], "no_actionable_review")
        db = app.connect()
        latest = db.execute("SELECT content FROM content_versions WHERE task_id=? ORDER BY version DESC LIMIT 1", (task_id,)).fetchone()
        self.assertEqual(latest["content"], "Human rewrite.")
        self.assertEqual(db.execute("SELECT count(*) FROM content_versions WHERE task_id=?", (task_id,)).fetchone()[0], 2)
        db.close()

    def test_edit_is_refused_while_a_review_is_running(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="reviewing")
        status, _, body = self.request("/api/edit", "POST", {"task_id": task_id, "content": "Too early."}, cookie, csrf)
        self.assertEqual(status, 409, body)
        self.assertEqual(body["code"], "review_in_progress")

    def test_review_error_is_retried_without_creating_a_version(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, version_id = self.task(owner, project_id, status="needs_revision", review=None)
        db = app.connect()
        db.execute("UPDATE content_versions SET review_status='review_error' WHERE id=?", (version_id,))
        db.commit()
        db.close()
        findings = [{"criterion": rule_id, "result": "Pass", "claim": "", "rule_id": rule_id, "evidence_source_id": None, "explanation": "No claim to check.", "recommendation": "None."} for rule_id, _, _ in app.RULES]
        with patch.object(app, "llm_json", return_value=({"findings": findings}, {"input_tokens": 1, "output_tokens": 1})):
            status, _, body = self.request("/api/review-edit", "POST", {"task_id": task_id}, cookie, csrf)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["review"]["verdict"], "Pass")
        self.assertEqual(body["task"]["status"], "approved_pending_human")
        db = app.connect()
        self.assertEqual(db.execute("SELECT count(*) FROM content_versions WHERE task_id=?", (task_id,)).fetchone()[0], 1)
        db.close()

    def test_an_approved_task_cannot_be_rejected(self):
        cookie, csrf, owner = self.register()
        project_id = self.project(owner)
        task_id, _ = self.task(owner, project_id, status="human_approved", approved=True, review="Pass")
        status, _, body = self.request("/api/reject", "POST", {"task_id": task_id}, cookie, csrf)
        self.assertEqual(status, 409, body)
        self.assertEqual(body["code"], "already_approved")
        db = app.connect()
        self.assertEqual(db.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()[0], "human_approved")
        db.close()

    def test_readiness_tracks_provider_configuration(self):
        status, _, body = self.request("/api/ready")
        self.assertEqual(body["ready"], app.provider_configured())
        self.assertEqual(status, 200 if body["ready"] else 503)
        self.assertIn("database", body)

    def test_health_does_not_depend_on_the_provider(self):
        status, _, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)

