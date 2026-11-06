import base64
import hashlib
import io
import json
import struct
import unittest
import zlib
from contextlib import closing
from unittest.mock import patch
from xml.etree import ElementTree

from PIL import Image, ImageDraw

from comfy_workflows import build_workflow, image_options
import test_visual_content as visual

app = visual.app


def fixture_png(size=16, color=b'\x40\x80\xc0'):
    def chunk(kind, content):
        return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + color * size) * size)) + chunk(b'IEND', b''))


class ReferenceWorkflowTests(unittest.TestCase):
    def test_reference_pixels_reach_sampler_with_subunit_denoise(self):
        graph = build_workflow('sd15.safetensors', 'Soft daylight', '1200x1600', '', 42,
                               reference_name='project/photo.png', strength=0.2)
        self.assertEqual(graph['4']['class_type'], 'VAEEncode')
        self.assertEqual(graph['4']['inputs']['pixels'], ['11', 0])
        self.assertEqual(graph['11']['inputs']['image'], ['8', 0])
        self.assertEqual(graph['8']['inputs']['image'], 'project/photo.png')
        self.assertEqual(graph['5']['inputs']['denoise'], 0.2)
        self.assertEqual(graph['5']['inputs']['seed'], 42)
        self.assertEqual((graph['15']['inputs']['width'], graph['15']['inputs']['height']), (1200, 1600))
        self.assertNotIn('10', graph)

    def test_protected_pixels_bypass_generated_output_at_original_resolution(self):
        graph = build_workflow('sd15', 'Background', '1200x1600', '', 7,
                               reference_name='source.png', mask_name='mask.png', strength=0.75)
        self.assertEqual(graph['4']['class_type'], 'VAEEncodeForInpaint')
        self.assertEqual(graph['7']['inputs']['images'], ['10', 0])
        self.assertEqual(graph['10']['inputs']['destination'], ['8', 0])
        self.assertEqual(graph['10']['inputs']['mask'], ['9', 0])

    def test_comfyui_upload_keeps_exact_reference_bytes_and_queues_img2img(self):
        source, result = fixture_png(512), fixture_png(512, b'\xc0\x80\x40')
        uploaded, queued = [], []
        def response(request, timeout):
            if request.full_url.endswith('/upload/image'):
                content = request.data.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
                uploaded.append(content)
                return io.BytesIO(json.dumps({'name': 'selected.png', 'subfolder': 'exact-reference'}).encode())
            if request.full_url.endswith('/prompt'):
                queued.append(json.loads(request.data)['prompt'])
                return io.BytesIO(b'{"prompt_id":"fixture-prompt"}')
            if '/history/' in request.full_url:
                return io.BytesIO(b'{"fixture-prompt":{"outputs":{"7":{"images":[{"filename":"result.png"}]}}}}')
            if '/view?' in request.full_url:
                return io.BytesIO(result)
            self.fail('Unexpected provider request: ' + request.full_url)
        with patch.object(app, 'urlopen', side_effect=response), patch.object(app, 'COMFYUI_CHECKPOINT', 'sd15.safetensors'):
            raw, media = app.run_comfyui_workflow('Warm background', '512x512', reference=source, strength=0.32, seed=42)
        self.assertEqual(uploaded, [source])
        self.assertEqual(hashlib.sha256(uploaded[0]).hexdigest(), hashlib.sha256(source).hexdigest())
        self.assertEqual(queued[0]['8']['inputs']['image'], 'exact-reference/selected.png')
        self.assertEqual(queued[0]['4']['class_type'], 'VAEEncode')
        self.assertEqual(queued[0]['5']['inputs']['denoise'], 0.32)
        self.assertEqual(queued[0]['5']['inputs']['seed'], 42)
        self.assertEqual((raw, media), (result, 'image/png'))

    def test_text_mode_uses_noise_without_a_source(self):
        graph = build_workflow('sd15', 'Coffee', '1024x1280', '', 12)
        self.assertEqual(graph['4']['class_type'], 'EmptyLatentImage')
        self.assertEqual(graph['5']['inputs']['denoise'], 1)
        self.assertNotIn('8', graph)
        self.assertLessEqual(max(graph['4']['inputs']['width'], graph['4']['inputs']['height']), 512)

    def test_invalid_numeric_options_cannot_reach_inference(self):
        for strength in (True, '0.3', float('nan'), float('inf'), 0, 1, -0.1):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                image_options('img2img', strength)
        for seed in (True, 1.5, -1, 2**32):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                image_options('img2img', seed=seed)


class ImageChatReferenceValidationTests(unittest.TestCase):
    def test_reference_decoder_preserves_exact_bytes(self):
        raw = fixture_png(512)
        self.assertEqual(app.decode_image_chat_png(base64.b64encode(raw).decode(), (512, 512)), raw)

    def test_decoded_byte_budget_is_enforced_independently_of_request_limit(self):
        with self.assertRaises(app.APIError) as error:
            app.decode_image_chat_png(base64.b64encode(b'x' * 5_000_001).decode(), (512, 512))
        self.assertEqual(error.exception.status, 400)

    def test_dimension_budgets_reject_headers_before_pixel_decode(self):
        for dimensions in ((4, 4), (8193, 8), (6000, 6000)):
            with self.subTest(dimensions=dimensions):
                raw = fixture_png(8)
                header = struct.pack('>II', *dimensions) + raw[24:29]
                raw = raw[:16] + header + struct.pack('>I', zlib.crc32(b'IHDR' + header)) + raw[33:]
                with self.assertRaises(app.APIError) as error:
                    app.decode_image_chat_png(base64.b64encode(raw).decode(), dimensions)
                self.assertEqual(error.exception.status, 400)
                self.assertIn('24 megapixels', str(error.exception))

    def test_animated_png_is_not_a_selected_single_rendering(self):
        output = io.BytesIO()
        Image.new('RGB', (16, 16), 'white').save(output, format='PNG', save_all=True,
                                              append_images=[Image.new('RGB', (16, 16), 'black')])
        with self.assertRaises(app.APIError) as error:
            app.decode_image_chat_png(base64.b64encode(output.getvalue()).decode(), (16, 16))
        self.assertEqual(error.exception.status, 400)


class ImageModeIntegrationTests(unittest.TestCase):
    setUp = visual.VisualWorkflowTests.setUp
    request = visual.VisualWorkflowTests.request
    register = visual.VisualWorkflowTests.register
    project = visual.VisualWorkflowTests.project
    task = visual.VisualWorkflowTests.task

    def source(self, project=None):
        raw, asset_id = fixture_png(), app.uid()
        with closing(app.connect()) as db, db:
            db.execute('INSERT INTO project_assets VALUES(?,?,?,?,?,?,?)',
                       (asset_id, project or self.project_id, 'product.png', 'image/png', raw, hashlib.sha256(raw).hexdigest(), app.now()))
        return asset_id, raw

    def generate(self, task_id, **extra):
        return self.request('/api/generate-image', 'POST',
                            {'task_id': task_id, 'prompt': 'Soft daylight on the product', 'provider': 'comfyui', **extra},
                            self.cookie, self.csrf)

    def test_img2img_sends_source_bytes_and_records_seed_strength_and_provenance(self):
        task_id, version_id = self.task(self.owner, self.project_id)
        asset_id, raw = self.source()
        with patch.object(app, 'call_comfyui_provider', return_value=(raw, 'image/png')) as local, patch.object(app, 'call_image_provider') as other:
            code, _, body = self.generate(task_id, mode='img2img', asset_id=asset_id, strength=0.2, seed=42)
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], raw)
        self.assertIsNone(local.call_args.kwargs['mask'])
        self.assertEqual(local.call_args.kwargs['strength'], 0.2)
        self.assertEqual(local.call_args.kwargs['seed'], 42)
        other.assert_not_called()
        with closing(app.connect()) as db, db:
            event = json.loads(db.execute("SELECT details FROM audit_events WHERE event='image.generated' AND task_id=?", (task_id,)).fetchone()[0])
            self.assertEqual(event['source_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(event['copy_version_id'], version_id)
            self.assertEqual(event['mode'], 'img2img')
            self.assertEqual(event['seed'], 42)
            self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0], 0)

    def test_foreign_photo_is_rejected_before_provider_call(self):
        task_id, _ = self.task(self.owner, self.project_id)
        asset_id, _ = self.source(self.project(self.owner, 'Another project'))
        with patch.object(app, 'call_comfyui_provider') as local:
            code, _, _ = self.generate(task_id, mode='img2img', asset_id=asset_id)
        self.assertEqual(code, 400)
        local.assert_not_called()

    def test_cloudflare_cannot_silently_ignore_a_reference(self):
        task_id, _ = self.task(self.owner, self.project_id)
        asset_id, _ = self.source()
        with patch.object(app, 'call_image_provider') as remote:
            code, _, body = self.generate(task_id, mode='img2img', asset_id=asset_id, provider='cloudflare')
        self.assertEqual(code, 400, body)
        remote.assert_not_called()

    def test_protected_edit_requires_mask_and_img2img_requires_photo(self):
        task_id, _ = self.task(self.owner, self.project_id)
        asset_id, _ = self.source()
        with patch.object(app, 'call_comfyui_provider') as local:
            self.assertEqual(self.generate(task_id, mode='edit', asset_id=asset_id)[0], 400)
            self.assertEqual(self.generate(task_id, mode='img2img')[0], 400)
        local.assert_not_called()

    def test_archived_photo_during_inference_cannot_save_a_result(self):
        task_id, _ = self.task(self.owner, self.project_id)
        asset_id, raw = self.source()
        def archive(*args, **kwargs):
            with closing(app.connect()) as db, db:
                db.execute('INSERT INTO archived_assets(asset_id,archived_at) VALUES(?,?)', (asset_id, app.now()))
            return raw, 'image/png'
        with patch.object(app, 'call_comfyui_provider', side_effect=archive):
            code, _, body = self.generate(task_id, mode='img2img', asset_id=asset_id)
        self.assertEqual(code, 409, body)
        with closing(app.connect()) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM generated_images').fetchone()[0], 0)
        self.assertEqual(list(app.IMAGE_STORAGE_PATH.iterdir()), [])


class SelectedImageChatTests(unittest.TestCase):
    setUp = visual.VisualWorkflowTests.setUp
    request = visual.VisualWorkflowTests.request
    register = visual.VisualWorkflowTests.register
    project = visual.VisualWorkflowTests.project
    task = visual.VisualWorkflowTests.task
    approve_copy = visual.VisualWorkflowTests.approve_copy
    approve_visual = visual.VisualWorkflowTests.approve_visual

    def seed_chat(self):
        task_id, version_id = self.task(self.owner, self.project_id, content='HEADLINE: Current headline',
                                       status='approved_pending_human', review='Pass')
        with closing(app.connect()) as db, db:
            db.execute("UPDATE content_versions SET review_status='pass' WHERE id=?", (version_id,))
        return task_id, version_id, self.seed_image(task_id)

    def seed_image(self, task_id, color=b'\x40\x80\xc0'):
        image_id, raw = app.uid(), fixture_png(512, color)
        storage_name = image_id + '.png'
        (app.IMAGE_STORAGE_PATH / storage_name).write_bytes(raw)
        with closing(app.connect()) as db, db:
            db.execute('INSERT INTO generated_images VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (image_id, self.project_id, task_id, 'Selected product photo', 'comfyui', 'fixture',
                        '512x512', storage_name, 'image/png', len(raw), app.now()))
            app.audit(db, self.owner, 'image.generated', {'image_id': image_id, 'mode': 'img2img'}, self.project_id, task_id)
        return image_id

    def seed_composition(self, image_id, version_id, headline='Shown headline', overlays=None):
        copy = {'headline': headline, 'body': '', 'cta': ''}
        with closing(app.connect()) as db, db:
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (image_id,)).fetchone()
            raw = app.visual_image_bytes(image)
            svg = app.composition_svg(raw, 'image/png', image['size'], copy, overlays or [])
            composition_id = app.uid()
            db.execute('INSERT INTO visual_compositions(id,task_id,image_id,version_id,image_sha256,copy_json,svg_content,render_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                       (composition_id, image['task_id'], image_id, version_id, hashlib.sha256(raw).hexdigest(),
                        json.dumps(copy), svg, hashlib.sha256(svg).hexdigest(), app.now()))
            if overlays:
                app.audit(db, self.owner, 'image.chat_edit', {'image_id': image_id, 'mode': 'img2img', 'edit_overlays': overlays}, self.project_id, image['task_id'])
        return composition_id

    def rendered_reference(self, composition_id):
        with closing(app.connect()) as db:
            composition = db.execute('SELECT * FROM visual_compositions WHERE id=?', (composition_id,)).fetchone()
            source = db.execute('SELECT * FROM generated_images WHERE id=?', (composition['image_id'],)).fetchone()
            with Image.open(io.BytesIO(app.visual_image_bytes(source))) as image:
                raster = image.convert('RGB')
            draw = ImageDraw.Draw(raster)
            draw.rectangle((0, 380, 511, 511), fill='#173528')
            draw.text((30, 400), json.loads(composition['copy_json'])['headline'], fill='white')
            draw.text((30, 30), 'Baked label and logo', fill='white')
            output = io.BytesIO()
            raster.save(output, format='PNG')
        raw = output.getvalue()
        return raw, {'composition_id': composition_id, 'source_render_sha256': composition['render_sha256'],
                     'reference_base64': base64.b64encode(raw).decode('ascii')}

    def edit(self, task_id, image_id, message, **extra):
        return self.request('/api/edit-image-chat', 'POST',
                            {'task_id': task_id, 'image_id': image_id, 'message': message, **extra}, self.cookie, self.csrf)

    def plan(self, action='image_edit', text='', replaces='', image_prompt='Warm earthy background', **extra):
        return {'action': action, 'text': text, 'replaces': replaces, 'position': 'top_right',
                'image_prompt': image_prompt, 'reply': 'A new unapproved edit will be created.', 'unhandled_requests': [], **extra}

    def snapshot(self, image_id):
        with closing(app.connect()) as db, db:
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (image_id,)).fetchone()
            compositions = db.execute('SELECT * FROM visual_compositions WHERE image_id=? ORDER BY rowid', (image_id,)).fetchall()
            return dict(image), app.visual_image_bytes(image), [dict(row) for row in compositions]

    def assert_no_output(self, image_ids):
        with closing(app.connect()) as db, db:
            self.assertEqual({row[0] for row in db.execute('SELECT id FROM generated_images')}, set(image_ids))
            self.assertEqual(db.execute("SELECT count(*) FROM audit_events WHERE event='image.chat_edit' AND details LIKE '%source_image_id%'").fetchone()[0], 0)
        self.assertEqual({path.stem for path in app.IMAGE_STORAGE_PATH.iterdir()}, set(image_ids))

    def test_selected_older_image_exact_bytes_sha_and_lineage_reach_img2img(self):
        task_id, version_id, selected = self.seed_chat()
        newer = self.seed_image(task_id, b'\x90\x70\x20')
        before = self.snapshot(selected)
        result = fixture_png(512, b'\xc0\x80\x40')
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})) as planner, patch.object(app, 'call_comfyui_provider', return_value=(result, 'image/png')) as local, patch.object(app, 'call_image_provider') as fallback:
            code, _, body = self.edit(task_id, selected, 'Change the background to warm earthy colors')
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], before[1])
        self.assertEqual(hashlib.sha256(local.call_args.kwargs['reference']).hexdigest(), hashlib.sha256(before[1]).hexdigest())
        self.assertEqual(local.call_args.args[1], '512x512')
        self.assertEqual(local.call_args.kwargs['strength'], 0.32)
        self.assertIn('retain its subject', local.call_args.args[0])
        self.assertNotIn('Do not add text, letters, numbers, logos', local.call_args.args[0])
        self.assertEqual(planner.call_args.args[2]['current_image']['id'], selected)
        fallback.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        self.assertNotEqual(body['image']['id'], selected)
        self.assertNotEqual(body['image']['id'], newer)
        self.assertEqual(body['image']['source_image_id'], selected)
        with closing(app.connect()) as db, db:
            event = json.loads(db.execute("SELECT details FROM audit_events WHERE event='image.chat_edit'").fetchone()[0])
            composition = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (body['image']['id'],)).fetchone()
            self.assertEqual(event['source_image_id'], selected)
            self.assertEqual(event['source_sha256'], hashlib.sha256(before[1]).hexdigest())
            self.assertEqual(event['reference_sha256'], event['source_sha256'])
            self.assertEqual(event['result_sha256'], hashlib.sha256(result).hexdigest())
            self.assertEqual(event['seed'], local.call_args.kwargs['seed'])
            self.assertEqual(event['copy_version_id'], version_id)
            self.assertIsNone(composition['approved_at'])
            self.assertIsNone(composition['approved_by'])
            self.assertEqual(db.execute('SELECT count(*) FROM content_versions WHERE task_id=?', (task_id,)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0], 0)
            self.assertIsNone(app.serialize_visual(db, composition)['download_url'])
            self.assertEqual(json.loads(composition['copy_json'])['headline'], '')

    def test_overlay_keeps_selected_writer_copy_inherited_labels_and_approved_source(self):
        task_id, version_id, selected = self.seed_chat()
        labels = [{'text': 'Original label', 'position': 'top_left'}]
        composition_id = self.seed_composition(selected, version_id, overlays=labels)
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(composition_id)[0], 200)
        before = self.snapshot(selected)
        plan = self.plan(action='add_text', text='50%', image_prompt='')
        with patch.object(app, 'llm_json', return_value=(plan, {})) as planner, patch.object(app, 'call_comfyui_provider') as local, patch.object(app, 'call_image_provider') as fallback:
            code, _, body = self.edit(task_id, selected, 'Add 50% at the top right')
        self.assertEqual(code, 201, body)
        local.assert_not_called()
        fallback.assert_not_called()
        self.assertEqual(planner.call_args.args[2]['shown_writer_copy']['headline'], 'Shown headline')
        self.assertIn('never silently implement only', planner.call_args.args[1])
        self.assertEqual(self.snapshot(selected), before)
        self.assertEqual(body['image']['edit_overlays'], labels + [{'text': '50%', 'position': 'top_right'}])
        with closing(app.connect()) as db, db:
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (body['image']['id'],)).fetchone()
            new = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (image['id'],)).fetchone()
            self.assertEqual(app.visual_image_bytes(image), before[1])
            self.assertEqual(json.loads(new['copy_json'])['headline'], 'Shown headline')
            self.assertNotIn(b'Current headline', new['svg_content'])
            root = ElementTree.fromstring(new['svg_content'])
            embedded = root.find('{http://www.w3.org/2000/svg}image').attrib['href'].split(',', 1)[1]
            self.assertEqual(base64.b64decode(embedded), before[1])
            visible = ' '.join(node.text or '' for node in root.iter('{http://www.w3.org/2000/svg}text'))
            for text in ('Shown headline', 'Original label', '50%'):
                self.assertIn(text, visible)
            self.assertIsNone(new['approved_at'])
            self.assertIsNone(new['approved_by'])
            self.assertEqual(app.visual_status(db, new), 'pending_visual_approval')
            new_id = new['id']
            event = json.loads(db.execute("SELECT details FROM audit_events WHERE event='image.chat_edit' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            self.assertEqual(event['source_composition_id'], composition_id)
            self.assertEqual(event['source_render_sha256'], before[2][0]['render_sha256'])
        self.assertEqual(self.request('/api/visual-file?id=' + new_id + '&download=1', cookie=self.cookie)[0], 409)

    def test_wrong_owner_wrong_task_and_foreign_composition_denied_before_planning(self):
        task_id, version_id, selected = self.seed_chat()
        other_task, other_version = self.task(self.owner, self.project_id)
        other_image = self.seed_image(other_task)
        other_composition = self.seed_composition(other_image, other_version, headline='')
        foreign_cookie, foreign_csrf, _ = self.register('foreign@example.test')
        with patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
            self.assertEqual(self.request('/api/edit-image-chat', 'POST', {'task_id': task_id, 'image_id': selected, 'message': 'Add 50%'}, foreign_cookie, foreign_csrf)[0], 404)
            self.assertEqual(self.edit(other_task, selected, 'Add 50%')[0], 404)
            self.assertEqual(self.edit(task_id, selected, 'Add 50%', composition_id=other_composition)[0], 404)
        planner.assert_not_called()
        local.assert_not_called()
        self.assert_no_output([selected, other_image])

    def test_exact_mixed_request_never_reports_success_for_any_planner_action(self):
        task_id, version_id, selected = self.seed_chat()
        self.seed_composition(selected, version_id)
        before = self.snapshot(selected)
        request = 'Change background warm earthy, enlarge headline, keep logo and product shape'
        for action in ('add_text', 'replace_text', 'image_edit', 'image_edit_and_text', 'clarify'):
            with self.subTest(action=action), patch.object(app, 'llm_json', return_value=(self.plan(action=action, text='Shown headline'), {})), patch.object(app, 'call_comfyui_provider') as local, patch.object(app, 'call_image_provider') as fallback:
                code, _, body = self.edit(task_id, selected, request)
                self.assertEqual(code, 409, body)
                self.assertEqual(body['code'], 'unsupported_image_edit')
                self.assertIn('No image was edited', body['error'])
                self.assertNotIn('image', body)
                local.assert_not_called()
                fallback.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        self.assert_no_output([selected])

    def test_mixed_visual_and_label_executes_both_or_rejects_partial_plan(self):
        task_id, _, selected = self.seed_chat()
        request = 'Change the background to warm earthy colors and add 50% at the top right'
        result = fixture_png(512, b'\xc0\x80\x40')
        partial_plans = [self.plan(action='add_text', text='50%', image_prompt=''), self.plan()]
        for plan in partial_plans:
            with self.subTest(action=plan['action']), patch.object(app, 'llm_json', return_value=(plan, {})), patch.object(app, 'call_comfyui_provider') as local:
                code, _, body = self.edit(task_id, selected, request)
            self.assertEqual(code, 409, body)
            self.assertEqual(body['code'], 'incomplete_image_edit')
            local.assert_not_called()
            self.assert_no_output([selected])
        with patch.object(app, 'llm_json', return_value=(self.plan(action='image_edit_and_text', text='50%'), {})), patch.object(app, 'call_comfyui_provider', return_value=(result, 'image/png')) as local:
            code, _, body = self.edit(task_id, selected, request)
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], self.snapshot(selected)[1])
        with closing(app.connect()) as db, db:
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (body['image']['id'],)).fetchone()
            composition = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (image['id'],)).fetchone()
            self.assertEqual(app.visual_image_bytes(image), result)
            self.assertIn(b'50%', composition['svg_content'])
            self.assertIsNone(composition['approved_at'])

    def test_visual_edit_of_shown_text_composition_never_substitutes_base(self):
        for headline, overlays in [('Shown headline', []), ('', [{'text': 'Saved label', 'position': 'top_left'}])]:
            with self.subTest(headline=headline):
                task_id, version_id, selected = self.seed_chat()
                self.seed_composition(selected, version_id, headline=headline, overlays=overlays)
                before = self.snapshot(selected)
                with patch.object(app, 'llm_json', return_value=(self.plan(), {})) as planner, patch.object(app, 'call_comfyui_provider') as local:
                    code, _, body = self.edit(task_id, selected, 'Change the background to warm earthy colors')
                self.assertEqual(code, 409, body)
                self.assertEqual(body['code'], 'unsupported_image_edit')
                self.assertIn('text-free base will not be substituted', body['error'])
                self.assertEqual(planner.call_args.args[2]['shown_writer_copy']['headline'], headline)
                local.assert_not_called()
                self.assertEqual(self.snapshot(selected), before)

    def test_client_rendered_composition_forwards_whole_raster_without_duplicate_copy(self):
        task_id, version_id, selected = self.seed_chat()
        labels = [{'text': 'Saved label', 'position': 'top_left'}]
        composition_id = self.seed_composition(selected, version_id, overlays=labels)
        self.approve_copy(task_id)
        self.assertEqual(self.approve_visual(composition_id)[0], 200)
        before = self.snapshot(selected)
        raster, reference = self.rendered_reference(composition_id)
        result = fixture_png(512, b'\xc0\x80\x40')
        with patch.object(app, 'llm_json', return_value=(self.plan(image_prompt='Warm background, enlarge the existing headline'), {})) as planner, patch.object(app, 'call_comfyui_provider', return_value=(result, 'image/png')) as local, patch.object(app, 'call_image_provider') as fallback:
            code, _, body = self.edit(task_id, selected, 'Change background to warm earthy colors and enlarge headline', **reference)
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], raster)
        self.assertNotEqual(raster, before[1])
        self.assertEqual(local.call_args.kwargs['strength'], 0.32)
        self.assertIsNone(local.call_args.kwargs['mask'])
        self.assertIn('enlarge the existing headline', local.call_args.args[0])
        self.assertIn('best effort', local.call_args.args[0])
        self.assertIn('best effort', body['reply'])
        self.assertEqual(planner.call_args.args[2]['reference_kind'], 'client_rendered_composition')
        self.assertEqual(planner.call_args.args[2]['shown_writer_copy']['headline'], 'Shown headline')
        fallback.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        self.assertEqual(body['image']['reference_kind'], 'client_rendered_composition')
        self.assertFalse(body['image']['reference_pixel_match_verified'])
        self.assertEqual(body['image']['source_composition_id'], composition_id)
        self.assertEqual(body['image']['reference_sha256'], hashlib.sha256(raster).hexdigest())
        with closing(app.connect()) as db:
            new = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (body['image']['id'],)).fetchone()
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (body['image']['id'],)).fetchone()
            event = json.loads(db.execute("SELECT details FROM audit_events WHERE event='image.chat_edit' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            self.assertEqual(event['source_sha256'], hashlib.sha256(before[1]).hexdigest())
            self.assertEqual(event['source_render_sha256'], hashlib.sha256(before[2][0]['svg_content']).hexdigest())
            self.assertEqual(event['reference_sha256'], hashlib.sha256(raster).hexdigest())
            self.assertEqual(event['reference_kind'], 'client_rendered_composition')
            self.assertEqual(event['edit_overlays'], [])
            self.assertEqual(json.loads(new['copy_json']), {'headline': '', 'body': '', 'cta': ''})
            self.assertEqual(new['version_id'], version_id)
            self.assertIsNone(new['approved_at'])
            self.assertIsNone(new['approved_by'])
            self.assertEqual(app.visual_status(db, new), 'pending_visual_approval')
            self.assertIsNone(app.serialize_visual(db, new)['download_url'])
            self.assertEqual(app.visual_image_bytes(image), result)
            self.assertEqual(len(ElementTree.fromstring(new['svg_content']).findall('.//{http://www.w3.org/2000/svg}text')), 0)
            self.assertEqual(db.execute('SELECT count(*) FROM content_versions WHERE task_id=?', (task_id,)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0], 1)
            new_id = new['id']
        self.assertEqual(self.request('/api/visual-file?id=' + new_id + '&download=1', cookie=self.cookie)[0], 409)

    def test_headline_enlargement_alone_is_raster_edit_not_duplicate_label(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        raster, reference = self.rendered_reference(composition_id)
        with patch.object(app, 'llm_json', return_value=(self.plan(image_prompt='Enlarge existing headline visually without changing its wording'), {})), patch.object(app, 'call_comfyui_provider', return_value=(fixture_png(512, b'\xc0\x80\x40'), 'image/png')) as local:
            code, _, body = self.edit(task_id, selected, 'Enlarge headline', **reference)
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], raster)
        self.assertEqual(body['image']['edit_overlays'], [])
        self.assertEqual(body['action'], 'image_edit')
        self.assertIn('best effort', body['reply'])

    def test_composed_raster_only_adds_fresh_label_for_visual_and_text_edits(self):
        for action in ('add_text', 'image_edit_and_text'):
            with self.subTest(action=action):
                task_id, version_id, selected = self.seed_chat()
                composition_id = self.seed_composition(selected, version_id, overlays=[{'text': 'Saved label', 'position': 'top_left'}])
                before = self.snapshot(selected)
                raster, reference = self.rendered_reference(composition_id)
                result = fixture_png(512, b'\xc0\x80\x40')
                plan = self.plan(action=action, text='50%', image_prompt='' if action == 'add_text' else 'Warm background and enlarge existing headline')
                message = 'Add 50%' if action == 'add_text' else 'Change background to warm earthy colors, enlarge headline, and add 50%'
                with patch.object(app, 'llm_json', return_value=(plan, {})), patch.object(app, 'call_comfyui_provider', return_value=(result, 'image/png')) as local:
                    code, _, body = self.edit(task_id, selected, message, **reference)
                self.assertEqual(code, 201, body)
                expected = raster if action == 'add_text' else result
                if action == 'add_text':
                    local.assert_not_called()
                else:
                    self.assertEqual(local.call_args.kwargs['reference'], raster)
                self.assertEqual(self.snapshot(selected), before)
                self.assertEqual(body['image']['edit_overlays'], [{'text': '50%', 'position': 'top_right'}])
                with closing(app.connect()) as db:
                    image = db.execute('SELECT * FROM generated_images WHERE id=?', (body['image']['id'],)).fetchone()
                    composition = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (image['id'],)).fetchone()
                    root = ElementTree.fromstring(composition['svg_content'])
                    text = [node.text for node in root.iter('{http://www.w3.org/2000/svg}text')]
                    self.assertEqual(text, ['50%'])
                    self.assertEqual(app.visual_image_bytes(image), expected)
                    embedded = root.find('{http://www.w3.org/2000/svg}image').attrib['href'].split(',', 1)[1]
                    self.assertEqual(base64.b64decode(embedded), expected)
                    self.assertFalse(any(json.loads(composition['copy_json']).values()))
                    self.assertIsNone(composition['approved_at'])
                    self.assertEqual(composition['version_id'], version_id)

    def test_invalid_client_reference_contract_fails_before_planning_or_model(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        before = self.snapshot(selected)
        _, reference = self.rendered_reference(composition_id)
        other_task, other_version = self.task(self.owner, self.project_id)
        other_image = self.seed_image(other_task)
        foreign_id = self.seed_composition(other_image, other_version)
        invalid = [
            ({key: value for key, value in reference.items() if key != 'composition_id'}, 400),
            ({key: value for key, value in reference.items() if key != 'source_render_sha256'}, 400),
            ({key: value for key, value in reference.items() if key != 'reference_base64'}, 400),
            ({**reference, 'source_render_sha256': '0' * 64}, 409),
            ({**reference, 'source_render_sha256': {'hash': reference['source_render_sha256']}}, 400),
            ({**reference, 'composition_id': foreign_id}, 404),
            ({**reference, 'reference_base64': ''}, 400),
            ({**reference, 'reference_base64': None}, 400),
            ({**reference, 'reference_base64': 'not base64'}, 400),
            ({**reference, 'reference_base64': 'https://example.test/render.png'}, 400),
            ({**reference, 'reference_base64': base64.b64encode(b'not a PNG').decode()}, 400),
            ({**reference, 'reference_base64': base64.b64encode(fixture_png(256)).decode()}, 400),
            ({**reference, 'reference_base64': base64.b64encode(fixture_png(512)[:-12]).decode()}, 400),
            ({**reference, 'reference_base64': base64.b64encode(fixture_png(512)[:33]).decode()}, 400),
            ({**reference, 'reference_base64': base64.b64encode(fixture_png(512)[:45] + b'broken pixels' + fixture_png(512)[-12:]).decode()}, 400),
            ({**reference, 'reference_base64': 'A' * 6_700_001}, 413),
        ]
        for fields, expected in invalid:
            with self.subTest(fields=list(fields), expected=expected), patch.object(app, 'RATE_MAX_REQUESTS', 100), patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
                code, _, body = self.edit(task_id, selected, 'Enlarge headline', **fields)
            self.assertEqual(code, expected, body)
            planner.assert_not_called()
            local.assert_not_called()
            self.assertEqual(self.snapshot(selected), before)
            self.assert_no_output([selected, other_image])

    def test_rendered_reference_still_requires_mask_for_exact_preservation(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        _, reference = self.rendered_reference(composition_id)
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider') as local:
            code, _, body = self.edit(task_id, selected, 'Change background, enlarge headline, keep logo and product shape exactly', **reference)
        self.assertEqual(code, 409, body)
        self.assertIn('protection mask', body['error'])
        local.assert_not_called()
        self.assert_no_output([selected])

    def test_protected_composition_passes_mask_and_restores_protected_pixels(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        before = self.snapshot(selected)
        raster, reference = self.rendered_reference(composition_id)
        mask_image = Image.new('RGB', (512, 512), 'white')
        ImageDraw.Draw(mask_image).rectangle((0, 0, 100, 100), fill='black')
        output = io.BytesIO()
        mask_image.save(output, format='PNG')
        mask = output.getvalue()
        result = fixture_png(512, b'\xc0\x80\x40')
        with patch.object(app, 'llm_json', return_value=(self.plan(image_prompt='Warm background and larger headline'), {})) as planner, patch.object(app, 'call_comfyui_provider', return_value=(result, 'image/png')) as local, patch.object(app, 'call_image_provider') as fallback:
            code, _, body = self.edit(task_id, selected, 'Change background warm earthy, enlarge headline, keep logo and product shape', **reference, mask=base64.b64encode(mask).decode())
        self.assertEqual(code, 201, body)
        self.assertEqual(local.call_args.kwargs['reference'], raster)
        self.assertEqual(local.call_args.kwargs['mask'], mask)
        self.assertEqual(local.call_args.kwargs['strength'], 0.65)
        self.assertTrue(planner.call_args.args[2]['protected_mask_supplied'])
        self.assertEqual(body['image']['mode'], 'edit')
        self.assertEqual(body['image']['mask_sha256'], hashlib.sha256(mask).hexdigest())
        self.assertTrue(body['image']['protected_pixels_preserved'])
        self.assertIn('Only fully protected', body['reply'])
        fallback.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        with closing(app.connect()) as db:
            image = db.execute('SELECT * FROM generated_images WHERE id=?', (body['image']['id'],)).fetchone()
            event = json.loads(db.execute("SELECT details FROM audit_events WHERE event='image.chat_edit' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            new = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (image['id'],)).fetchone()
            self.assertEqual(event['mode'], 'edit')
            self.assertEqual(event['mask_sha256'], hashlib.sha256(mask).hexdigest())
            self.assertEqual(event['reference_sha256'], hashlib.sha256(raster).hexdigest())
            self.assertEqual(event['edit_overlays'], [])
            self.assertEqual(event['result_sha256'], hashlib.sha256(app.visual_image_bytes(image)).hexdigest())
            self.assertFalse(any(json.loads(new['copy_json']).values()))
            self.assertIsNone(new['approved_at'])
            self.assertEqual(new['version_id'], version_id)
            saved = app.visual_image_bytes(image)
        with Image.open(io.BytesIO(saved)) as edited, Image.open(io.BytesIO(raster)) as original:
            self.assertEqual(edited.convert('RGB').crop((0, 0, 101, 101)).tobytes(), original.crop((0, 0, 101, 101)).tobytes())
            self.assertEqual(edited.convert('RGB').getpixel((200, 200)), (192, 128, 64))

    def test_invalid_masks_and_baked_label_replacement_fail_closed(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id, overlays=[{'text': 'Saved label', 'position': 'top_left'}])
        _, reference = self.rendered_reference(composition_id)
        for mask in ('', None, 'invalid', base64.b64encode(fixture_png(256)).decode(), base64.b64encode(fixture_png(512)[:-12]).decode()):
            with self.subTest(mask_type=type(mask).__name__), patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
                code, _, body = self.edit(task_id, selected, 'Change background', **reference, mask=mask)
            self.assertEqual(code, 400, body)
            self.assertEqual(body['code'], 'invalid_mask')
            planner.assert_not_called()
            local.assert_not_called()
        with patch.object(app, 'llm_json', return_value=(self.plan(action='replace_text', text='50%', replaces='Saved label', image_prompt=''), {})), patch.object(app, 'call_comfyui_provider') as local:
            code, _, body = self.edit(task_id, selected, 'Replace Saved label with 50%', **reference)
        self.assertEqual(code, 409, body)
        self.assertIn('baked', body['error'])
        local.assert_not_called()
        self.assert_no_output([selected])

    def test_composed_reference_unchanged_output_and_mid_inference_hash_change_fail_closed(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        raster, reference = self.rendered_reference(composition_id)
        before = self.snapshot(selected)
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider', return_value=(raster, 'image/png')):
            code, _, body = self.edit(task_id, selected, 'Change background', **reference)
        self.assertEqual(code, 502, body)
        self.assertEqual(body['code'], 'image_edit_unchanged')
        self.assertEqual(self.snapshot(selected), before)
        def change_hash(*args, **kwargs):
            with closing(app.connect()) as db, db:
                db.execute('UPDATE visual_compositions SET render_sha256=? WHERE id=?', ('0' * 64, composition_id))
            return fixture_png(512, b'\xc0\x80\x40'), 'image/png'
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider', side_effect=change_hash):
            code, _, body = self.edit(task_id, selected, 'Change background', **reference)
        self.assertEqual(code, 409, body)
        self.assert_no_output([selected])

    def test_protected_unchanged_pixels_cannot_be_reported_as_a_success(self):
        task_id, version_id, selected = self.seed_chat()
        composition_id = self.seed_composition(selected, version_id)
        _, reference = self.rendered_reference(composition_id)
        mask = base64.b64encode(fixture_png(512, b'\0\0\0')).decode()
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider', return_value=(fixture_png(512, b'\xc0\x80\x40'), 'image/png')):
            code, _, body = self.edit(task_id, selected, 'Change background', **reference, mask=mask)
        self.assertEqual(code, 502, body)
        self.assertEqual(body['code'], 'image_edit_unchanged')
        self.assert_no_output([selected])

    def test_provider_failure_malformed_and_unchanged_outputs_fail_closed(self):
        task_id, _, selected = self.seed_chat()
        before = self.snapshot(selected)
        failures = [app.APIError(503, 'Local GPU unavailable', 'image_provider_unavailable'),
                    app.APIError(504, 'Local GPU timed out', 'image_provider_timeout'),
                    (b'not an image', 'image/png'), (fixture_png(512)[:33], 'image/png'),
                    (fixture_png(512)[:-12], 'image/png'), (fixture_png(256), 'image/png'), (before[1], 'image/png')]
        for result in failures:
            with self.subTest(result_type=type(result).__name__):
                provider = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
                with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider', **provider), patch.object(app, 'call_image_provider') as fallback:
                    code, _, body = self.edit(task_id, selected, 'Change background to warm earthy colors')
                self.assertGreaterEqual(code, 500, body)
                self.assertNotIn('image', body)
                fallback.assert_not_called()
                self.assert_no_output([selected])
                self.assertEqual(self.snapshot(selected), before)

    def test_draft_source_composition_and_ownership_changes_during_inference_cannot_save(self):
        for change in ('draft', 'source', 'composition', 'owner', 'review', 'archive'):
            with self.subTest(change=change):
                self.project_id = self.project(self.owner, 'Concurrent ' + change)
                task_id, version_id, selected = self.seed_chat()
                composition_id = self.seed_composition(selected, version_id, headline='')
                other_owner = self.register('new-' + change + '@example.test')[2] if change == 'owner' else None
                def concurrent_edit(*args, **kwargs):
                    with closing(app.connect()) as db, db:
                        if change == 'draft':
                            db.execute('INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)',
                                       (app.uid(), task_id, 2, 'HEADLINE: Changed', '[]', 'pending', 0, app.now()))
                        elif change == 'source':
                            image = db.execute('SELECT * FROM generated_images WHERE id=?', (selected,)).fetchone()
                            (app.IMAGE_STORAGE_PATH / image['storage_name']).write_bytes(fixture_png(512, b'\x90\x70\x20'))
                        elif change == 'composition':
                            db.execute('UPDATE visual_compositions SET svg_content=? WHERE id=?', (b'changed preview', composition_id))
                        elif change == 'owner':
                            db.execute('UPDATE projects SET owner_id=? WHERE id=?', (other_owner, self.project_id))
                        else:
                            db.execute('UPDATE tasks SET status=? WHERE id=?', ('reviewing' if change == 'review' else 'archived', task_id))
                    return fixture_png(512, b'\xc0\x80\x40'), 'image/png'
                with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider', side_effect=concurrent_edit):
                    code, _, body = self.edit(task_id, selected, 'Change background to warm earthy colors')
                self.assertEqual(code, 409, body)
                with closing(app.connect()) as db, db:
                    self.assertEqual(db.execute('SELECT count(*) FROM generated_images WHERE task_id=?', (task_id,)).fetchone()[0], 1)
                    self.assertEqual(db.execute("SELECT count(*) FROM audit_events WHERE event='image.chat_edit' AND task_id=?", (task_id,)).fetchone()[0], 0)
                    saved_ids = {row[0] for row in db.execute('SELECT id FROM generated_images')}
                self.assertEqual({path.stem for path in app.IMAGE_STORAGE_PATH.iterdir()}, saved_ids)

    def test_ambiguous_target_ungrounded_text_and_incomplete_plan_do_not_save(self):
        task_id, version_id, selected = self.seed_chat()
        self.seed_composition(selected, version_id, overlays=[{'text': 'Saved label', 'position': 'top_left'}])
        before = self.snapshot(selected)
        plans = [self.plan(action='replace_text', text='50%', replaces='Wrong label', image_prompt=''),
                 self.plan(action='remove_text', replaces='', image_prompt=''),
                 self.plan(action='add_text', text='Invented claim', image_prompt=''),
                 self.plan(action='add_text', text='50%', image_prompt='Visual request incorrectly discarded'),
                 self.plan(action='add_text', text='50%', image_prompt='', unhandled_requests=['Cannot preserve the requested layout']),
                 {'action': 'add_text'}]
        for plan in plans:
            with self.subTest(plan=plan), patch.object(app, 'llm_json', return_value=(plan, {})), patch.object(app, 'call_comfyui_provider') as local:
                code, _, body = self.edit(task_id, selected, 'Add 50% at the top right')
                self.assertIn(code, (409, 502), body)
                self.assertNotIn('image', body)
                local.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        with closing(app.connect()) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM generated_images').fetchone()[0], 1)

    def test_stale_and_tampered_selected_compositions_denied_before_planning(self):
        for change in ('stale', 'render', 'hash'):
            with self.subTest(change=change):
                task_id, version_id, selected = self.seed_chat()
                composition_id = self.seed_composition(selected, version_id)
                with closing(app.connect()) as db, db:
                    if change == 'stale':
                        db.execute('INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)',
                                   (app.uid(), task_id, 2, 'HEADLINE: Changed', '[]', 'pending', 0, app.now()))
                    elif change == 'render':
                        db.execute('UPDATE visual_compositions SET svg_content=? WHERE id=?', (b'tampered', composition_id))
                    else:
                        db.execute('UPDATE visual_compositions SET image_sha256=? WHERE id=?', ('wrong', composition_id))
                with patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
                    code, _, body = self.edit(task_id, selected, 'Add 50%')
                self.assertEqual(code, 409, body)
                planner.assert_not_called()
                local.assert_not_called()

    def test_message_limit_remains_aligned_with_1000_character_frontend(self):
        task_id, _, selected = self.seed_chat()
        with patch.object(app, 'llm_json', return_value=(self.plan(action='clarify', image_prompt=''), {})) as planner:
            self.assertEqual(self.edit(task_id, selected, 'x' * 1000)[0], 200)
            self.assertEqual(self.edit(task_id, selected, 'x' * 1001)[0], 400)
            self.assertEqual(self.edit(task_id, selected, '')[0], 400)
            self.assertEqual(self.edit(task_id, selected, {'instruction': 'Add 50%'})[0], 400)
        self.assertEqual(planner.call_count, 1)

    def test_exact_label_replacement_and_removal_are_immutable_overlay_edits(self):
        task_id, version_id, selected = self.seed_chat()
        labels = [{'text': 'Saved label', 'position': 'top_left'}]
        self.seed_composition(selected, version_id, overlays=labels)
        before = self.snapshot(selected)
        for action in ('replace_text', 'remove_text'):
            plan = self.plan(action=action, text='50%' if action == 'replace_text' else '', replaces='Saved label', image_prompt='')
            with self.subTest(action=action), patch.object(app, 'llm_json', return_value=(plan, {})), patch.object(app, 'call_comfyui_provider') as local:
                code, _, body = self.edit(task_id, selected, 'Replace Saved label with 50%' if action == 'replace_text' else 'Remove Saved label')
            self.assertEqual(code, 201, body)
            local.assert_not_called()
            expected = [{'text': '50%', 'position': 'top_right'}] if action == 'replace_text' else []
            self.assertEqual(body['image']['edit_overlays'], expected)
            self.assertEqual(self.snapshot(selected), before)
            with closing(app.connect()) as db, db:
                composition = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (body['image']['id'],)).fetchone()
                self.assertEqual(json.loads(composition['copy_json'])['headline'], 'Shown headline')
                self.assertNotIn(b'Saved label', composition['svg_content'])
                self.assertIsNone(composition['approved_at'])

    def test_missing_inherited_label_lineage_cannot_silently_remove_shown_artwork(self):
        task_id, version_id, selected = self.seed_chat()
        self.seed_composition(selected, version_id, overlays=[{'text': 'Saved label', 'position': 'top_left'}])
        with closing(app.connect()) as db, db:
            db.execute("DELETE FROM audit_events WHERE task_id=? AND event='image.chat_edit'", (task_id,))
        before = self.snapshot(selected)
        with patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
            code, _, body = self.edit(task_id, selected, 'Add 50%')
        self.assertEqual(code, 409, body)
        self.assertEqual(body['code'], 'image_inputs_changed')
        planner.assert_not_called()
        local.assert_not_called()
        self.assertEqual(self.snapshot(selected), before)
        self.assert_no_output([selected])

    def test_multiple_saved_previews_require_exact_selected_composition_id(self):
        task_id, version_id, selected = self.seed_chat()
        old_composition = self.seed_composition(selected, version_id, headline='Old shown headline')
        current_version = app.uid()
        with closing(app.connect()) as db, db:
            db.execute('INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)',
                       (current_version, task_id, 2, 'HEADLINE: Current headline', '[]', 'pending', 0, app.now()))
        current_composition = self.seed_composition(selected, current_version, headline='Selected shown headline')
        with patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
            code, _, body = self.edit(task_id, selected, 'Add 50%')
            self.assertEqual(code, 409, body)
            self.assertEqual(body['code'], 'image_composition_required')
            self.assertEqual(self.edit(task_id, selected, 'Add 50%', composition_id=old_composition)[0], 409)
        planner.assert_not_called()
        local.assert_not_called()
        before = self.snapshot(selected)
        with patch.object(app, 'llm_json', return_value=(self.plan(action='add_text', text='50%', image_prompt=''), {})):
            code, _, body = self.edit(task_id, selected, 'Add 50%', composition_id=current_composition)
        self.assertEqual(code, 201, body)
        self.assertEqual(self.snapshot(selected), before)
        with closing(app.connect()) as db, db:
            composition = db.execute('SELECT * FROM visual_compositions WHERE image_id=?', (body['image']['id'],)).fetchone()
            self.assertEqual(json.loads(composition['copy_json'])['headline'], 'Selected shown headline')
            self.assertIsNone(composition['approved_at'])

    def test_initial_review_and_archive_gates_block_before_any_provider_call(self):
        task_id, _, selected = self.seed_chat()
        for status in ('reviewing', 'archived'):
            with self.subTest(status=status):
                with closing(app.connect()) as db, db:
                    db.execute('UPDATE tasks SET status=? WHERE id=?', (status, task_id))
                with patch.object(app, 'llm_json') as planner, patch.object(app, 'call_comfyui_provider') as local:
                    code, _, body = self.edit(task_id, selected, 'Change background')
                self.assertEqual(code, 409, body)
                planner.assert_not_called()
                local.assert_not_called()
        self.assert_no_output([selected])

    def test_exact_product_preservation_requires_protection_and_cannot_be_promised(self):
        task_id, _, selected = self.seed_chat()
        with patch.object(app, 'llm_json', return_value=(self.plan(), {})), patch.object(app, 'call_comfyui_provider') as local:
            code, _, body = self.edit(task_id, selected, 'Change background to warm earthy colors, keep logo and product shape unchanged')
        self.assertEqual(code, 409, body)
        self.assertIn('protection mask', body['error'])
        local.assert_not_called()
        self.assert_no_output([selected])

    def test_planner_provider_failure_cannot_call_image_provider_or_save(self):
        task_id, _, selected = self.seed_chat()
        with patch.object(app, 'llm_json', side_effect=app.APIError(503, 'Provider credentials missing', 'provider_unavailable')), patch.object(app, 'call_comfyui_provider') as local, patch.object(app, 'call_image_provider') as fallback:
            code, _, body = self.edit(task_id, selected, 'Change the background')
        self.assertEqual(code, 503, body)
        local.assert_not_called()
        fallback.assert_not_called()
        self.assert_no_output([selected])

    def test_commit_failure_rolls_back_new_image_and_composition_and_cleans_file(self):
        task_id, _, selected = self.seed_chat()
        before = self.snapshot(selected)
        original_audit = app.audit
        def fail_edit_audit(db, user_id, event, *args, **kwargs):
            if event == 'image.chat_edit':
                raise app.sqlite3.OperationalError('Simulated write failure')
            return original_audit(db, user_id, event, *args, **kwargs)
        with patch.object(app, 'llm_json', return_value=(self.plan(action='add_text', text='50%', image_prompt=''), {})), patch.object(app, 'audit', side_effect=fail_edit_audit):
            code, _, body = self.edit(task_id, selected, 'Add 50%')
        self.assertEqual(code, 500, body)
        self.assertEqual(body['code'], 'database_error')
        self.assertEqual(self.snapshot(selected), before)
        self.assert_no_output([selected])
