"""Loopback-only acceptance fixtures; never imports production credentials."""
import hashlib
import io
import json
import os
import re
import socket
import sys
import tempfile
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path('C:/Users/Beta/WorkBuddy AI/2026-11-04-16-39-26/evidence-ui')
assert EVIDENCE.is_dir()
TEST_ROOT = Path(tempfile.mkdtemp(prefix='rekarasa-acceptance-TEST-'))
# Shadow every dotenv key before application import, without loading values.
dotenv = ROOT / '.env'
if dotenv.is_file():
    for line in dotenv.read_text(encoding='utf-8').splitlines():
        match = re.match(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        if match:
            os.environ[match[1]] = ''
for key in list(os.environ):
    if any(word in key.upper() for word in ('GROQ', 'CLOUDFLARE', 'SMTP', 'SENTRY', 'API_KEY', 'API_TOKEN')):
        os.environ[key] = ''
os.environ.update(DATABASE_PATH=str(TEST_ROOT / 'TEST.sqlite3'), IMAGE_STORAGE_PATH=str(TEST_ROOT / 'images'), APP_ENV='acceptance', HOST='127.0.0.1', PORT='8016', APP_BASE_URL='http://127.0.0.1:8016', SMTP_HOST='', SMTP_USER='', SMTP_PASSWORD='', SMTP_PORT='587', SMTP_FROM='acceptance@example.test', GROQ_API_KEY='', SENTRY_DSN='', DEV_MAILBOX='false', LLM_PROVIDER='groq', MODEL='acceptance-deterministic', COMFYUI_URL='http://127.0.0.1:1', COMFYUI_TIMEOUT='1', LOG_LEVEL='ERROR')
# Deny outbound connections even if a provider stub is accidentally bypassed.
blocked_calls = []
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
def deny_connect(sock, address):
    blocked_calls.append({'kind': 'socket', 'host': str(address[0])})
    raise OSError('Outbound network disabled in acceptance harness')
socket.socket.connect = deny_connect
socket.socket.connect_ex = deny_connect
sys.path.insert(0, str(ROOT))
import app
from PIL import Image, ImageDraw, ImageEnhance
assert app.DB_PATH == TEST_ROOT / 'TEST.sqlite3'
assert app.IMAGE_STORAGE_PATH == TEST_ROOT / 'images'
assert not app.SMTP_ENABLED and not os.environ.get('GROQ_API_KEY')
app.init_db()
app.IMAGE_STORAGE_PATH.mkdir()
llm_calls, provider_calls = [], []

def png_fixture(color, number):
    image = Image.new('RGB', (512, 512), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((140, 100, 370, 430), fill=(70, 40, 25), outline='white', width=8)
    draw.rectangle((165, 200, 345, 300), fill='white')
    draw.text((185, 230), 'KOPI SENJA ' + str(number), fill='black')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()

def fake_llm(role, instructions, payload, contract):
    llm_calls.append({'role': role, 'payload': payload})
    if role == 'Planner':
        if '[FAIL_PLAN]' in payload['brief']:
            raise app.APIError(503, 'Acceptance fixture planner failure', 'fixture_plan_failure')
        preferences = payload.get('output_preferences') or ['Caption only']
        channels = payload.get('platform_preferences') or ['Instagram']
        tasks = []
        for index in range(max(len(preferences), len(channels))):
            fmt = preferences[index % len(preferences)]
            tasks.append({'title': 'Kopi Senja acceptance ' + fmt, 'format': fmt, 'platform': channels[index % len(channels)], 'angle': 'A quiet coffee break', 'goal': 'Introduce Kopi Senja', 'selection_reason': 'Matches the requested channel and format.'})
        return {'objective': 'Introduce Kopi Senja from the supplied brief', 'audience': payload.get('audience') or 'Coffee readers', 'product_facts': [], 'constraints': [], 'missing_information': [], 'tasks': tasks}, {}
    if role == 'Image Editor':
        return {'action': 'image_edit', 'text': '', 'replaces': '', 'position': 'center', 'image_prompt': 'Increase brightness of the selected reference background slightly', 'reply': 'Create a brighter version from the selected reference.', 'unhandled_requests': []}, {}
    if role == 'Reviewer':
        return {'findings': [{'criterion': rule[0], 'result': 'Pass', 'claim': '', 'rule_id': rule[0], 'evidence_source_id': None, 'explanation': 'No factual claim in this fixture.', 'recommendation': 'No change required.'} for rule in app.RULES]}, {}
    raise AssertionError('Unexpected LLM role: ' + role)

def fake_provider(prompt, size, reference=None, mask=None, strength=0.75, seed=None, **kwargs):
    if reference:
        original = Image.open(io.BytesIO(reference)).convert('RGB')
        image = ImageEnhance.Brightness(original).enhance(1.15)
        ImageDraw.Draw(image).rectangle((0, 0, 48, 48), fill=(255, 220, 120))
        output = io.BytesIO()
        image.save(output, format='PNG')
        result = output.getvalue()
    else:
        result = png_fixture((75, 130, 190), 3)
    provider_calls.append({'size': size, 'reference_sha256': hashlib.sha256(reference).hexdigest() if reference else None, 'mask_sha256': hashlib.sha256(mask).hexdigest() if mask else None, 'result_sha256': hashlib.sha256(result).hexdigest(), 'result_base64': __import__('base64').b64encode(result).decode()})
    return result, 'image/png'

app.llm_json = fake_llm
app.call_comfyui_provider = fake_provider
app.call_image_provider = fake_provider
app.comfyui_status = lambda: {'ready': True, 'state': 'ready', 'message': 'Isolated deterministic TEST provider', 'checkpoint': 'TEST'}
app.image_provider_options = lambda: [{'id': 'comfyui', 'label': 'TEST deterministic', 'available': True, 'modes': ['concept', 'img2img', 'edit'], 'note': 'No external calls'}]

def internal(path, payload):
    raw = json.dumps(payload).encode()
    environ = {'REQUEST_METHOD': 'POST', 'PATH_INFO': path, 'QUERY_STRING': '', 'CONTENT_LENGTH': str(len(raw)), 'wsgi.input': io.BytesIO(raw), 'HTTP_COOKIE': cookie.split(';', 1)[0], 'HTTP_X_CSRF_TOKEN': csrf, 'HTTP_HOST': '127.0.0.1:8016', 'REMOTE_ADDR': '127.0.0.1'}
    captured = {}
    body = b''.join(app.application(environ, lambda status, headers: captured.update(status=status)))
    result = json.loads(body)
    assert captured['status'].startswith(('200', '201')), (path, result)
    return result

owner, project, other = [app.uid() for _ in range(3)]
db = app.connect()
db.execute('INSERT INTO users VALUES(?,?,?,?)', (owner, 'acceptance@example.test', app.password_hash('Acceptance-only-123'), app.now()))
for project_id, name in ((project, 'Kopi Senja Kita'), (other, 'Studio Pagi')):
    db.execute('INSERT INTO projects VALUES(?,?,?,?)', (project_id, owner, name, app.now()))
db.commit()
db.close()
raw_session, csrf, cookie = app.issue_session(owner)
TEXT_V1 = 'Kopi Senja v1 original saved caption. Take a quiet moment between your daily tasks and notice the small details around you. Share your coffee break in your own words, with a warm and relaxed tone.'
TEXT_V2 = 'Kopi Senja v2 revised saved caption. Find a little room for a slower pause in your day. Put the busy list aside for a moment and tell us what makes your own coffee break worth remembering.'
VISUAL_COPY = 'HEADLINE: Kopi Senja\nBODY: A quiet moment\nCTA: Take a pause\nCAPTION: A quiet coffee break for your afternoon, with room to notice the small details. Share your own moment.\nVISUAL: Coffee on a warm neutral background'

def seed_task(project_id, fmt, content, approved, versions=1):
    conv, brief, plan, task = [app.uid() for _ in range(4)]
    db = app.connect()
    db.execute('INSERT INTO conversations VALUES(?,?,?,?,?)', (conv, owner, project_id, 'Kopi Senja saved brief', app.now()))
    db.execute('INSERT INTO briefs VALUES(?,?,?,?,?,?,?)', (brief, conv, 'Write a relaxed Kopi Senja caption.', 'Students', 'Warm', json.dumps([fmt]), app.now()))
    project_name = db.execute('SELECT name FROM projects WHERE id=?', (project_id,)).fetchone()['name']
    item = {'title': project_name + ' ' + fmt, 'format': fmt, 'platform': 'Instagram', 'angle': 'Quiet break', 'goal': 'Introduce the brand', 'selection_reason': 'Matches this brief.'}
    db.execute('INSERT INTO plans VALUES(?,?,?,?,?)', (plan, brief, json.dumps({'tasks': [item]}), 'confirmed', app.now()))
    db.execute('INSERT INTO tasks(id,plan_id,project_id,format,deadline,publish_at,status,remediation_count,created_at,title,platform,angle,goal) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (task, plan, project_id, fmt, app.now()[:10], None, 'human_approved' if approved else 'approved_pending_human', 0, app.now(), item['title'], 'Instagram', item['angle'], item['goal']))
    ids = []
    for number in range(1, versions + 1):
        vid = app.uid()
        text = TEXT_V1 if versions > 1 and number == 1 else content
        db.execute('INSERT INTO content_versions VALUES(?,?,?,?,?,?,?,?)', (vid, task, number, text, '[]', 'pass', int(approved), app.now()))
        review_id = app.uid()
        db.execute('INSERT INTO review_runs VALUES(?,?,?,?,?)', (review_id, task, vid, 'Pass', app.now()))
        for rule in app.RULES:
            db.execute('INSERT INTO findings(id,review_id,criterion,result,claim,rule_id,rule_version,evidence_source_id,explanation,recommendation,invalid_reference) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (app.uid(), review_id, rule[0], 'Pass', '', rule[0], rule[1], None, 'No prohibited or factual claim in this seeded fixture.', 'No change needed.', 0))
        if approved:
            db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?)', (app.uid(), vid, owner, 'approved', 'Isolated fixture approval', app.now()))
        ids.append(vid)
    db.commit()
    db.close()
    return task, ids

text_task, text_versions = seed_task(project, 'Caption only', TEXT_V2, False, 2)
image_task, image_versions = seed_task(project, 'Poster or static ad', VISUAL_COPY, True)
other_task, _ = seed_task(other, 'Caption only', TEXT_V2.replace('Kopi Senja', 'Studio Pagi'), True)
image_ids, compositions = [], []
for number, color in ((1, (220, 140, 75)), (2, (60, 150, 145))):
    image_id = app.uid()
    png = png_fixture(color, number)
    storage_name = image_id + '.png'
    (app.IMAGE_STORAGE_PATH / storage_name).write_bytes(png)
    db = app.connect()
    db.execute('INSERT INTO generated_images VALUES(?,?,?,?,?,?,?,?,?,?,?)', (image_id, project, image_task, 'Fixture image ' + str(number), 'comfyui', 'TEST', '512x512', storage_name, 'image/png', len(png), app.now()))
    db.commit()
    db.close()
    composition = internal('/api/compose-visual', {'image_id': image_id})['composition']
    composition = internal('/api/approve-visual', {'composition_id': composition['id'], 'inspected_image': True})['composition']
    image_ids.append(image_id)
    compositions.append(composition)
photo_id = app.uid()
photo = png_fixture((200, 160, 120), 0)
db = app.connect()
db.execute('INSERT INTO project_assets VALUES(?,?,?,?,?,?,?)', (photo_id, project, 'kopi-senja-product.png', 'image/png', photo, hashlib.sha256(photo).hexdigest(), app.now()))
db.commit()
db.close()
proposal = internal('/api/plan', {'project_id': project, 'brief': 'Create a Kopi Senja caption for Students.', 'audience': 'Students', 'auto_confirm': False})
fixtures = {'owner': owner, 'project': project, 'otherProject': other, 'textTask': text_task, 'textVersions': text_versions, 'textV1': TEXT_V1, 'textV2': TEXT_V2, 'imageTask': image_task, 'images': image_ids, 'compositions': compositions, 'photo': photo_id, 'proposal': proposal, 'database': str(app.DB_PATH), 'storage': str(app.IMAGE_STORAGE_PATH)}
(EVIDENCE / 'fixtures.json').write_text(json.dumps(fixtures, indent=2), encoding='utf-8')

class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass

def harness(environ, start_response):
    path = environ.get('PATH_INFO', '')
    if path.startswith('/__test/'):
        assert environ.get('REMOTE_ADDR') == '127.0.0.1'
        if path == '/__test/auth':
            start_response('200 OK', [('Content-Type', 'application/json'), ('Set-Cookie', cookie), ('Cache-Control', 'no-store')])
            return [b'{"authenticated":true}']
        if path == '/__test/stats':
            body = {'llm_calls': llm_calls, 'provider_calls': provider_calls, 'blocked_calls': blocked_calls, 'database': str(app.DB_PATH), 'credentials_cleared': not any(os.environ.get(key) for key in ('GROQ_API_KEY', 'SMTP_PASSWORD', 'SMTP_USER', 'SENTRY_DSN'))}
            start_response('200 OK', [('Content-Type', 'application/json'), ('Cache-Control', 'no-store')])
            return [json.dumps(body).encode()]
        if path == '/__test/health':
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [b'{"isolated_test":true}']
    return app.application(environ, start_response)

if __name__ == '__main__':
    print('Isolated TEST WSGI ready on 127.0.0.1:8016; credentials cleared; outbound network denied', flush=True)
    with make_server('127.0.0.1', 8016, harness, handler_class=QuietHandler) as server:
        server.serve_forever()
