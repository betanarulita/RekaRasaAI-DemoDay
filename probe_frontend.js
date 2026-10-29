// Runs calendarView() and the diff helper against a stub DOM so a runtime
// error surfaces here instead of during the demo. Not a browser and not a
// layout check: it proves the functions run and produce the markup we expect.
const fs = require('fs');
const src = fs.readFileSync('static/app.js', 'utf8');

function grab(name) {
  const start = src.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('missing function ' + name);
  let depth = 0;
  for (let j = src.indexOf('{', start); j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  throw new Error('unbalanced ' + name);
}
function grabConst(name) {
  const m = src.match(new RegExp('^const ' + name + ' = [^\\n]*', 'm'));
  if (!m) throw new Error('missing const ' + name);
  return m[0];
}

const captured = [];
function fakeEl() {
  return {
    innerHTML: '', onclick: null, onchange: null, dataset: {}, childElementCount: 0,
    append() { this.childElementCount++; }, before() {},
    classList: { add() {}, remove() {} }, scrollIntoView() {},
    querySelectorAll() { return []; }, querySelector() { return null; },
  };
}
global.document = {
  querySelector(sel) {
    const el = fakeEl();
    if (sel === '#planner-content') captured.push(el);
    return el;
  },
  querySelectorAll() { return []; },
  createElement() { return fakeEl(); },
};

// new Function, not eval: sloppy eval would hoist these declarations into this
// module's scope and collide with the destructuring below.
const api = new Function([
  grab('localDateKey'), grabConst('esc'), grabConst('labelStatus'), grabConst('date'),
  grabConst('state'), grab('taskRow'), grab('eventState'), grab('calendarView'),
  grab('bindTaskRows'), grab('sentences'), grab('sentenceDiff'),
  'return { state, calendarView, sentenceDiff };',
].join('\n'))();

const { state, calendarView, sentenceDiff } = api;

const today = new Date();
const iso = d => new Date(d).toISOString().slice(0, 10);
const day = offset => { const d = new Date(today); d.setDate(d.getDate() + offset); return iso(d); };

state.month = new Date(today.getFullYear(), today.getMonth(), 1);
state.calendarDay = day(0);
state.projects = [{ id: 'p1', name: 'Parfum R&N', sources: [] }];

const tasks = [
  { id: 't1', project_id: 'p1', project_name: 'Parfum R&N', title: 'Launch poster', format: 'Poster or static ad', platform: 'Instagram', status: 'human_approved', deadline: day(2), publish_at: null, versions: [] },
  { id: 't2', project_id: 'p1', project_name: 'Parfum R&N', title: 'Marketplace copy', format: 'Marketplace listing', platform: 'Shopee', status: 'approved_pending_human', deadline: day(0), publish_at: day(0), versions: [] },
  { id: 't3', project_id: 'p1', project_name: 'Parfum R&N', title: 'TikTok script', format: 'Short-form video', platform: 'TikTok', status: 'needs_revision', deadline: day(0), publish_at: null, versions: [] },
  { id: 't4', project_id: 'p1', project_name: 'Parfum R&N', title: 'No date task', format: 'Social post', platform: 'Instagram', status: 'planned', deadline: null, publish_at: null, versions: [] },
  { id: 't5', project_id: 'p1', project_name: 'Parfum R&N', title: 'Approved post', format: 'Social post', platform: 'Instagram', status: 'human_approved', deadline: day(5), publish_at: null, versions: [] },
  { id: 't6', project_id: 'p1', project_name: 'Parfum R&N', title: 'Pending post', format: 'Social post', platform: 'Instagram', status: 'approved_pending_human', deadline: day(5), publish_at: null, versions: [] },
  { id: 't7', project_id: 'p1', project_name: 'Parfum R&N', title: 'Blocked post', format: 'Social post', platform: 'Instagram', status: 'needs_revision', deadline: day(5), publish_at: null, versions: [] },
];

calendarView(tasks);
const html = captured[0].innerHTML;

const checks = [
  ['grid rendered', html.includes('calendar-grid')],
  ['approved event colour', html.includes('calendar-event is-approved')],
  ['pending event colour', html.includes('calendar-event is-pending')],
  ['blocked event colour', html.includes('calendar-event is-blocked')],
  ['open-count badge', /class="day-open"/.test(html)],
  ['has-open marker', /class="calendar-day[^"]*has-open/.test(html)],
  ['legend', html.includes('calendar-legend')],
  ['agenda project link', html.includes('agenda-project')],
  ['selected panel id', html.includes('id="calendar-selected"')],
  ['unscheduled count', html.includes('WITHOUT A DATE')],
  ['no undefined leaked', !html.includes('undefined')],
];

let bad = 0;
for (const [name, ok] of checks) { console.log((ok ? 'ok   ' : 'FAIL ') + name); if (!ok) bad++; }

// The badge must count only what is not approved on that date.
const badge = (html.match(/class="day-open"[^>]*>(\d+)</) || [])[1];
console.log('badge on the selected date:', badge, '(expected 2: the pending task and the blocked one; the task due and published the same day counts once)');
if (badge !== '2') { console.log('FAIL badge count'); bad++; }

// A day holding three tasks must render two and a "+1 more".
const more = (html.match(/calendar-more">\+(\d+)/) || [])[1];
console.log('overflow marker on the busy date:', more, '(expected 1)');
if (more !== '1') { console.log('FAIL overflow marker'); bad++; }

// On that busy date the two visible rows must be the blocked and the pending
// task, not the approved one: urgency sorts first.
const cell = (html.match(/data-day="[^"]*" aria-label="[^"]*, 3 planned items[^"]*"[\s\S]*?<\/button>/) || [''])[0];
const firstTwo = [...cell.matchAll(/calendar-event is-(approved|pending|blocked)/g)].map(m => m[1]).slice(0, 2);
console.log('two visible rows on the busy date:', firstTwo.join(', '), '(expected blocked, pending)');
if (firstTwo.join(',') !== 'blocked,pending') { console.log('FAIL urgency order'); bad++; }

const diff = sentenceDiff('One. Two bad claim. Three.', 'One. Three. Four.');
console.log('diff:', diff.map(p => p.type + ':' + p.text).join(' | '));
if (!diff.some(p => p.type === 'del' && p.text === 'Two bad claim.')) { console.log('FAIL diff deletion'); bad++; }
if (!diff.some(p => p.type === 'add' && p.text === 'Four.')) { console.log('FAIL diff addition'); bad++; }

console.log(bad ? bad + ' problem(s)' : 'all calendar and diff checks OK');
process.exit(bad ? 1 : 0);
