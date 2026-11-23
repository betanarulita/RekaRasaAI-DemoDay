const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {createRequire} = require('module');
const cliRequire = createRequire(path.join(require('child_process').execSync('npm root -g', {encoding:'utf8'}).trim(), '@playwright/cli/package.json'));
const {chromium} = cliRequire('playwright');
const BASE = 'http://127.0.0.1:8016';
const OUT = process.env.RR_ACCEPTANCE_EVIDENCE_DIR || 'D:/RekaRasaAI-DemoDay/evidence-reviewer';
assert(fs.statSync(OUT).isDirectory());
const fixture = JSON.parse(fs.readFileSync(path.join(OUT, 'fixtures.json'), 'utf8'));
const phase = process.argv[2] || 'text';
const results = {phase, startedAt:new Date().toISOString(), fixtures:{database:fixture.database, storage:fixture.storage}, tests:[], screenshots:[], consoleErrors:[], pageErrors:[], overflow:[], externalRequests:[], requests:[]};
let browser, context, page;
function save(){fs.writeFileSync(path.join(OUT, `browser-results-${phase}.json`), JSON.stringify(results,null,2));}
async function test(name, action){
  const start=Date.now();
  try{await action();results.tests.push({name,status:'pass',durationMs:Date.now()-start});console.log('PASS '+name);}
  catch(error){results.tests.push({name,status:'fail',error:error.message,durationMs:Date.now()-start});console.log('FAIL '+name+' — '+error.message.split('\n')[0]);await page.screenshot({path:path.join(OUT,`${phase}-failure-${results.tests.length}.png`),fullPage:true}).catch(()=>{});await page.keyboard.press('Escape').catch(()=>{});}
  save();
}
async function check(name, action){return test(name,action);}
async function ready(selector){await page.locator(selector).first().waitFor({state:'visible'});}
async function nav(view){
  if(page.viewportSize().width<=780&&await page.locator('.app-shell.is-collapsed').count())await page.locator('#menu-toggle').click();
  await page.locator(view==='settings'?'.sidebar .account':`.nav-list [data-page="${view}"]`).click();
  await page.waitForFunction(v=>JSON.parse(decodeURIComponent(location.hash.slice(6))).page===v, view);
}
async function api(route,payload){
  const response=await context.request[ payload ? 'post':'get'](BASE+route,payload?{data:payload,headers:{'X-CSRF-Token':(await (await context.request.get(BASE+'/api/session')).json()).csrf}}:{});
  return {status:response.status(),body:await response.json().catch(()=>null),response};
}
async function shots(name){
  const storage=await page.evaluate(()=>Object.fromEntries(Object.entries(sessionStorage)));
  const dialog=await page.locator('dialog[open]').first().getAttribute('class').catch(()=>null);
  const audienceOpen=await page.locator('.audience-picker[open]').count();
  const outputsOpen=await page.locator('.output-preferences[open]').count();
  for(const [label,width,height] of [['desktop',1440,1000],['mobile375',375,812]]){
    let target=page;
    if(page.viewportSize().width!==width){
      target=await context.newPage();await target.setViewportSize({width,height});
      await target.addInitScript(values=>{for(const [key,value] of Object.entries(values))sessionStorage.setItem(key,value)},storage);
      await target.goto(page.url());await target.locator('.page-content').waitFor();
      if(name.startsWith('history')){await target.locator('#history-results[aria-busy=false]').waitFor();await target.locator('#history-search').fill(await page.locator('#history-search').inputValue());}
      if(dialog?.includes('brief-preferences')){await target.locator('#brief-preferences-button').click();if(audienceOpen)await target.locator('.audience-picker summary').click();if(outputsOpen)await target.locator('.output-preferences summary').click();}
      if(dialog?.includes('visual-edit')){const imageId=page.locator('.visual-edit-dialog').getAttribute('data-image-id');const selectedId=await imageId;const selected=target.locator(`[data-visual-image="${selectedId}"]`);await selected.waitFor();await selected.locator('xpath=..').locator('[data-visual-edit]').click();await target.locator('.visual-edit-dialog[open]').waitFor();}
      if(dialog?.includes('original-photo')){await target.getByRole('button',{name:'Preview original photo',exact:true}).click();}
      else if(dialog?.includes('photo-editor')){await target.locator('#visual-mode').selectOption('edit');await target.getByRole('button',{name:'Protect product area',exact:true}).click();await target.waitForFunction(()=>document.querySelector('.protection-canvas')?.width===512);await target.locator('.center-protection').click();}
    }
    await target.evaluate(()=>document.fonts.ready);
    await target.locator('.page-content img,dialog[open] img').evaluateAll(images=>Promise.all(images.map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true})}))));
    const filename=`${phase}-${name}-${label}-${process.pid}.png`;
    await target.screenshot({path:path.join(OUT,filename),fullPage:true});
    results.screenshots.push({view:name,viewport:label,file:filename});
    const geometry=await target.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,offenders:[...document.querySelectorAll('.page-content * ,dialog[open] *')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&(r.right>innerWidth+2||r.left<-2)&&s.position!=='fixed'&&s.visibility!=='hidden'&&e.checkVisibility()}).slice(0,8).map(e=>({tag:e.tagName,id:e.id,cls:String(e.className).slice(0,70),right:Math.round(e.getBoundingClientRect().right)}))}));
    results.overflow.push({view:name,viewport:label,...geometry});
    if(target!==page)await target.close();
  }
  save();
}
async function goTask(task){await page.goto(BASE+'/#view='+encodeURIComponent(JSON.stringify({page:'workbench',taskId:task})));await page.locator('#draft-display, #generate-one, #retry-generate').first().waitFor({state:'visible'});}
async function draft(){return page.evaluate(()=>{const key=Object.keys(sessionStorage).find(k=>k.startsWith('rekarasa:brief:v1:'));return key?JSON.parse(sessionStorage.getItem(key)):null;});}
async function submitBrief(){const response=page.waitForResponse(r=>r.url()===BASE+'/api/plan'&&r.request().method()==='POST');await page.locator('#brief-form [type=submit]').click();return await response;}
async function historyReady(){await ready('#history-search');await page.locator('#history-results[aria-busy=false]').waitFor();}

async function textFlows(){
  await test('Home draft input persists through navigation and refresh',async()=>{
    await ready('#home-brief');await shots('home');
    await page.locator('#home-brief').fill('Kopi Senja unsent acceptance draft');
    const initial=await draft();assert(initial.updatedAt>0);
    await nav('projects');await ready('#create-project');await shots('projects');
    await nav('home');await ready('#home-brief');assert.equal(await page.locator('#home-brief').inputValue(),initial.brief);
    await page.reload();await ready('#home-brief');assert.equal(await page.locator('#home-brief').inputValue(),initial.brief);assert.equal((await draft()).updatedAt,initial.updatedAt);
  });
  await test('New chat preferences and multiselect custom audience survive route away and reload',async()=>{
    await nav('new');await ready('#brief');await page.locator('[name=project_id]').selectOption(fixture.project);await page.waitForFunction(project=>document.querySelector('#brief-form')?.dataset.preferencesLoadedProject===project,fixture.project);
    await page.locator('#brief').fill('Create a Kopi Senja caption for a quiet afternoon.');
    await page.locator('#brief-preferences-button').click();await page.locator('.audience-picker summary').click();
    for(const value of ['Students','Working Professionals','Custom Audience'])await page.locator(`[name=audience_options][value="${value}"]`).check();
    await page.locator('[name=audience_custom]').fill('Local coffee creators');await page.locator('.audience-picker summary').click();
    await page.locator('[name=audience_age]').fill('20-35');await page.locator('[name=deadline]').fill('2026-11-20');
    await page.locator('#tone-preset').selectOption('Warm and friendly');await page.locator('[name=tone]').fill('Warm, direct, no health claims');
    await page.locator('[name=platform_preferences][value=Instagram]').check();
    await page.locator('.output-preferences summary').click();await page.locator('[name=output_preferences][value="Caption only"]').check();
    await shots('preferences');await page.locator('#done-brief-preferences').click();await shots('new-chat');
    const stored=await draft();assert.deepEqual(stored.audience_options,['Students','Working Professionals','Custom Audience']);
    await nav('planner');await ready('#planner-content');await nav('new');await ready('#brief');
    assert.equal(await page.locator('#brief').inputValue(),stored.brief);assert.equal((await draft()).updatedAt,stored.updatedAt);
    await page.reload();await ready('#brief');assert.equal((await draft()).updatedAt,stored.updatedAt);
    assert.equal(await page.locator('[name=audience]').inputValue(),'Students; Working Professionals; Local coffee creators');
    assert.equal(await page.locator('[name=tone]').inputValue(),stored.tone);assert.equal(await page.locator('[name=deadline]').inputValue(),stored.deadline);
    assert.equal(await page.locator('[name=platform_preferences]:checked').count(),1);
  });
  await test('Draft expires at 24 hours without route refresh extending timestamp',async()=>{
    await page.evaluate(()=>{const key=Object.keys(sessionStorage).find(k=>k.startsWith('rekarasa:brief:v1:'));const value=JSON.parse(sessionStorage.getItem(key));value.updatedAt=Date.now()-24*60*60*1000-1;sessionStorage.setItem(key,JSON.stringify(value));});
    // Suppress only this unload save so the deliberately aged fixture reaches startup unchanged.
    await page.evaluate(()=>removeEventListener('beforeunload',captureBriefDraft));
    await page.reload();await ready('#brief');assert.equal(await page.locator('#brief').inputValue(),'');assert.equal(await draft(),null);
  });
  await test('Future draft timestamps are rejected',async()=>{
    await page.evaluate(()=>sessionStorage.setItem(briefStorageKey(),JSON.stringify({brief:'future fixture',updatedAt:Date.now()+60000})));
    await page.evaluate(()=>removeEventListener('beforeunload',captureBriefDraft));await page.reload();await ready('#brief');assert.equal(await page.locator('#brief').inputValue(),'');
  });
  await test('Blank send is blocked without planner request',async()=>{
    await page.locator('[name=project_id]').selectOption(fixture.project);await page.locator('#brief').fill('');
    const before=results.requests.filter(r=>r.route==='/api/plan').length;
    await page.locator('#brief-form [type=submit]').click();assert.equal(results.requests.filter(r=>r.route==='/api/plan').length,before);assert.equal(await page.locator('#brief').evaluate(e=>e.validity.valueMissing),true);
  });
  await test('Planner failure retains unsent text and preferences after refresh',async()=>{
    await page.locator('#brief').fill('[FAIL_PLAN] Kopi Senja failure retention');
    await page.locator('#brief-preferences-button').click();await page.locator('.audience-picker summary').click();await page.locator('[name=audience_options][value=Students]').check();await page.locator('[name=tone]').fill('Quiet warm voice');await page.locator('#done-brief-preferences').click();
    const response=await submitBrief();assert.equal(response.status(),503);await page.locator('.submit-brief:enabled').waitFor();
    assert.equal(await page.locator('#brief').inputValue(),'[FAIL_PLAN] Kopi Senja failure retention');await page.reload();await ready('#brief');assert.equal(await page.locator('[name=tone]').inputValue(),'Quiet warm voice');assert((await page.locator('#brief').inputValue()).includes('[FAIL_PLAN]'));await shots('failed-send');
  });
  let submitted;
  await test('Successful send transmits saved custom audience and clears unsent draft',async()=>{
    await page.locator('#brief').fill('Create a Kopi Senja caption for a quiet afternoon.');await page.locator('#brief-preferences-button').click();await page.locator('.audience-picker summary').click();
    for(const value of ['Students','Working Professionals','Custom Audience'])await page.locator(`[name=audience_options][value="${value}"]`).check();
    await page.locator('[name=audience_custom]').fill('Local coffee creators');await page.locator('.audience-picker summary').click();await page.locator('[name=audience_age]').fill('20-35');await page.locator('[name=platform_preferences][value=Instagram]').check();await page.locator('.output-preferences summary').click();await page.locator('[name=output_preferences][value="Caption only"]').check();await page.locator('#done-brief-preferences').click();
    const response=await submitBrief();submitted=await response.json();assert.equal(response.status(),201);await ready('#continue-project');
    const payload=response.request().postDataJSON();assert.equal(payload.audience,'Students; Working Professionals; Local coffee creators; Target age: 20-35');assert.deepEqual(payload.output_preferences,['Caption only']);assert.deepEqual(payload.platform_preferences,['Instagram']);assert.equal(await draft(),null);await shots('understanding');
  });
  await test('Understanding has exactly Edit and Continue, no removed labels',async()=>{
    await ready('.understanding-actions');assert.deepEqual(await page.locator('.understanding-actions button').allTextContents(),['Edit','Continue']);
    const text=await page.locator('.page-content').innerText();for(const forbidden of ['Product sources','Policy rules','FACTS FROM SOURCES','CONSTRAINTS'])assert(!text.includes(forbidden),forbidden);
  });
  await test('Understanding Edit revises the same plan and Continue opens project',async()=>{
    assert(submitted);const planId=submitted.plan_id;await page.locator('#edit-original-brief').click();await ready('#brief');assert.equal((await draft()).edit_plan.plan_id,planId);
    await page.locator('#brief').fill('Create a Kopi Senja caption with a revised quiet direction.');const response=await submitBrief();const body=await response.json();assert.equal(response.status(),200);assert.equal(body.plan_id,planId);assert.equal(body.plan.revision,1);submitted=body;
    await ready('#continue-project');await page.locator('#continue-project').click();await ready('.project-detail-page');assert.equal(await page.locator('[data-saved-plan="'+planId+'"]').count(),1);await shots('project-detail');
  });
  let reviewerTaskId;
  await test('Kopi Senja review failure preserves v1; Reviewer retry and Writer revision stay separate',async()=>{
    const confirmed=await api('/api/confirm-plan',{plan_id:submitted.plan_id,tasks:submitted.plan.tasks});assert.equal(confirmed.status,200,JSON.stringify(confirmed.body));reviewerTaskId=confirmed.body.tasks[0].id;
    const scheduled=await context.request.post(BASE+'/__test/fail-next-review');assert.equal(scheduled.status(),200);
    await goTask(reviewerTaskId);const firstReview=page.waitForResponse(r=>r.url()===BASE+'/api/generate'&&r.request().method()==='POST');await page.locator('#generate-one').click();const failed=await firstReview;assert.equal(failed.status(),502);await ready('#review-latest');
    assert.equal(await page.locator('#remediate').count(),0);assert((await page.locator('.review-retry-note').innerText()).includes('remediation count are preserved'));
    let state=(await api('/__test/task-state?task='+reviewerTaskId)).body;assert.equal(state.task.status,'needs_revision');assert.equal(state.task.remediation_count,0);assert.equal(state.versions.length,1);assert.equal(state.versions[0].review_status,'review_error');assert.equal(state.versions[0].human_approved,0);assert.equal(state.writer_revision_count,0);assert.equal(state.review_count,0);assert.deepEqual(state.runs.map(run=>[run.role,run.status]),[['Writer','completed'],['Reviewer','failed']]);
    const retryResponse=page.waitForResponse(r=>r.url()===BASE+'/api/review-edit'&&r.request().method()==='POST');await page.locator('#review-latest').click();const retried=await retryResponse;assert.equal(retried.status(),200);await ready('#remediate');
    state=(await api('/__test/task-state?task='+reviewerTaskId)).body;assert.equal(state.versions.length,1);assert.equal(state.versions[0].review_status,'needs_evidence');assert.equal(state.task.remediation_count,0);assert.equal(state.writer_revision_count,0);assert.equal(state.review_count,1);assert.deepEqual(state.runs.map(run=>[run.role,run.status]),[['Writer','completed'],['Reviewer','failed'],['Reviewer','completed']]);
    const projects=(await api('/api/projects')).body;let task=projects.projects.flatMap(project=>project.tasks).find(item=>item.id===reviewerTaskId);let current=task.versions.at(-1);assert.equal(current.review.product_category,'food_beverage');assert(current.review.findings.some(item=>item.severity==='HIGH'&&item.rule_id==='DEMO-FACT-001'&&item.recommendation.includes('Remove the stress and focus effects')));
    const quality=new Set(current.review.findings.filter(item=>item.criterion.startsWith('Content quality:')).map(item=>item.criterion));assert.deepEqual([...quality].sort(),['Content quality: Brief fit','Content quality: Brand voice consistency','Content quality: Clarity','Content quality: Copy quality','Content quality: Format compliance','Content quality: Platform fit','Content quality: Target audience fit'].sort());
    const referenceIds=new Set(current.review.findings.flatMap(item=>(item.policy_references||[]).map(reference=>reference.id)));assert(referenceIds.has('UU-PK-8-1999'));assert(!referenceIds.has('BPOM-18-2024'));assert((await page.locator('.review-header').innerText()).includes('Food / beverage'));assert((await page.locator('.review-panel').innerText()).includes('Severity: HIGH.'));await page.locator('.regulatory-links summary').first().click();assert((await page.locator('.review-panel').innerText()).includes('UU 8/1999'));assert(!(await page.locator('.review-panel').innerText()).includes('PerBPOM 18/2024'));await shots('reviewer-needs-evidence');
    const revision=page.waitForResponse(r=>r.url()===BASE+'/api/revise'&&r.request().method()==='POST');await page.locator('#remediate').click();const revised=await revision;assert.equal(revised.status(),201);await ready('#human-approve');
    state=(await api('/__test/task-state?task='+reviewerTaskId)).body;assert.equal(state.versions.length,2);assert.equal(state.versions[0].review_status,'needs_evidence');assert.equal(state.versions[1].review_status,'pass');assert(state.versions[1].content.length>=120);assert(!state.versions[1].content.includes('It reduces stress'));assert.equal(state.task.remediation_count,1);assert.equal(state.writer_revision_count,1);assert.equal(state.review_count,2);assert.deepEqual(state.runs.map(run=>[run.role,run.status]),[['Writer','completed'],['Reviewer','failed'],['Reviewer','completed'],['Writer','completed'],['Reviewer','completed']]);
    task=(await api('/api/projects')).body.projects.flatMap(project=>project.tasks).find(item=>item.id===reviewerTaskId);current=task.versions.at(-1);assert.equal(current.review.verdict,'Pass');assert.equal(current.review.findings.filter(item=>item.criterion.startsWith('Content quality:')).length,7);assert.equal(current.human_approved,0);assert.equal(await page.locator('.version-row').count(),2);await shots('reviewer-revised');
    await page.locator('#human-approve').click();await page.waitForFunction(id=>document.querySelector('.workbench-heading')?.innerText.includes('Human approved'),reviewerTaskId);const copyAction=page.getByRole('button',{name:'Copy caption',exact:true});await copyAction.waitFor({state:'visible'});assert.equal(await copyAction.isDisabled(),false);
    state=(await api('/__test/task-state?task='+reviewerTaskId)).body;assert.equal(state.task.status,'human_approved');assert.equal(state.approval_count,1);assert.equal(state.approval_events.length,1);assert.equal(state.approval_events[0].event,'human.approved');assert.equal(JSON.parse(state.approval_events[0].details).version_id,state.versions[1].id);results.reviewerLifecycle={taskId:reviewerTaskId,afterFailure:{versions:1,remediationCount:0,reviewRuns:0},afterRetry:{versions:1,remediationCount:0,reviewRuns:1,productCategory:'food_beverage',references:[...referenceIds]},afterRevision:{versions:2,remediationCount:1,reviewRuns:2},afterHumanApproval:{status:state.task.status,approvalCount:state.approval_count}};
  });
  await test('Submitted brief never resurrects on route back or reload',async()=>{
    await nav('new');await ready('#brief');assert.equal(await page.locator('#brief').inputValue(),'');await page.reload();await ready('#brief');assert.equal(await page.locator('#brief').inputValue(),'');
  });
  await test('Saved proposal Edit retrieves real brief and retains original plan id',async()=>{
    await nav('projects');await ready('#create-project');await page.locator(`[data-project="${fixture.project}"]`).click();await ready('.project-detail-page');await page.locator(`[data-edit-plan="${fixture.proposal.plan_id}"]`).click();await ready('#brief');assert.equal((await draft()).edit_plan.plan_id,fixture.proposal.plan_id);assert.equal(await page.locator('#brief').inputValue(),'Create a Kopi Senja caption for Students.');
  });
  await test('Projects to project to editor back button and browser back',async()=>{
    await nav('projects');await ready('#create-project');await page.locator(`[data-project="${fixture.project}"]`).click();await ready('.project-detail-page');await page.locator(`[data-task="${fixture.textTask}"]`).click();await ready('#draft-display');assert((await page.locator('#draft-display').innerText()).includes(fixture.textV2));await shots('text-editor');
    assert((await page.locator('#back-task').innerText()).includes('Kopi Senja'));await page.locator('#back-task').click();await ready('.project-detail-page');await page.locator('#back-projects').click();await ready('#create-project');
    await page.locator(`[data-project="${fixture.project}"]`).click();await ready('.project-detail-page');await page.locator(`[data-task="${fixture.textTask}"]`).click();await ready('#draft-display');await page.goBack();await ready('.project-detail-page');await page.goBack();await ready('#create-project');
  });
  await test('History token search returns actual text and image versions',async()=>{
    await nav('history');await historyReady();await shots('history');await page.locator('#history-search').fill('Kopi Senja');
    assert(await page.locator(`[data-history-version="${fixture.textVersions[0]}"]`).count());assert(await page.locator(`[data-history-version="${fixture.images[0]}"]`).count());assert.equal(await page.locator('.history-version').filter({hasText:'Studio Pagi'}).count(),0);await shots('history-search');
  });
  await test('History no-match empty state clears search',async()=>{
    await page.locator('#history-search').fill('NOT_FOUND_ACCEPTANCE_XYZ');await ready('#history-clear-empty');await shots('history-empty');await page.locator('#history-clear-empty').click();assert.equal(await page.locator('#history-search').inputValue(),'');assert(await page.locator(`[data-history-version="${fixture.textVersions[1]}"]`).count());
  });
  await test('History v1 opens saved old content; back and reload preserve version route',async()=>{
    await page.locator(`[data-history-version="${fixture.textVersions[0]}"]`).click();await ready('#draft-display');assert((await page.locator('#draft-display').innerText()).includes(fixture.textV1));assert(!(await page.locator('#draft-display').innerText()).includes(fixture.textV2));await shots('old-version');
    await page.reload();await ready('#draft-display');assert((await page.locator('#draft-display').innerText()).includes(fixture.textV1));assert.equal(await page.locator('#human-approve').count(),0);await page.locator('#back-task').click();await historyReady();
    await page.locator(`[data-history-version="${fixture.textVersions[0]}"]`).click();await ready('#draft-display');await page.goBack();await historyReady();
  });
  await test('Planner upper has no All folders; calendar filters retained across view switch',async()=>{
    await nav('planner');await ready('#project-filter');assert(!((await page.locator('.page-head,.planner-toolbar').allInnerTexts()).join(' ')).includes('All folders'));await page.locator('#project-filter').selectOption(fixture.project);await page.locator('#format-filter').selectOption('Caption only');await shots('planner-calendar');
    await page.locator('#list-view').click();await ready('.planner-list-view');await shots('planner-list');await page.locator('#calendar-view').click();await ready('#project-filter');assert.equal(await page.locator('#project-filter').inputValue(),fixture.project);assert.equal(await page.locator('#format-filter').inputValue(),'Caption only');
    await nav('projects');await ready('#create-project');await nav('planner');await ready('#project-filter');assert.equal(await page.locator('#project-filter').inputValue(),fixture.project);
  });
  await test('Review/export approval gates remain enforced by UI and API',async()=>{
    await goTask(fixture.textTask);assert(await page.getByRole('button',{name:'Copy caption',exact:true}).isDisabled());results.approvalProbe={copyDisabledBeforeApproval:true};
    const result=await api('/api/approve',{task_id:fixture.textTask,note:'Acceptance human inspection'});assert.equal(result.status,200);await page.reload();await ready('#draft-display');assert.equal(await page.getByRole('button',{name:'Copy caption',exact:true}).isDisabled(),false);
    const edit=await api('/api/edit',{task_id:fixture.textTask,content:fixture.textV2+' A new unreviewed change.'});assert.equal(edit.status,201);await page.reload();await ready('#draft-display');assert(await page.getByRole('button',{name:'Copy caption',exact:true}).isDisabled());assert.equal((await api('/api/approve',{task_id:fixture.textTask})).status,409);
  });
  await test('Settings compact view and sidebar contain no Groq verified banner',async()=>{
    await nav('settings');await ready('.settings-panel');await shots('settings');assert(!/Groq|Verified/i.test(await page.locator('.sidebar').innerText()));
    await goTask(fixture.textTask);for(const forbidden of ['AGENT EXCHANGES','VERSIONED POLICY','Source citations validated','FACTS FROM SOURCES'])assert(!(await page.locator('.page-content').innerText()).includes(forbidden),forbidden);
  });
}

async function imageFlows(){
  await test('Image editor main preview has both thumbnails and opens no dialog automatically',async()=>{
    await goTask(fixture.imageTask);await ready('#visual-history .visual-thumb');assert.equal(await page.locator('.visual-thumb').count(),2);assert.equal(await page.locator('.visual-edit-dialog[open]').count(),0);await shots('image-editor');
    for(const image of fixture.images){await page.locator(`[data-visual-image="${image}"]`).click();assert.equal(await page.locator('.visual-edit-dialog[open]').count(),0);const selected=await page.locator('.visual-thumb[aria-pressed=true]').getAttribute('data-visual-image');assert.equal(selected,image);}
  });
  await test('Each approved thumbnail download matches the selected approved SVG and exact rendered PNG',async()=>{
    results.downloads=[];
    for(const composition of fixture.compositions){
      const thumb=page.locator(`[data-visual-image="${composition.image_id}"][data-visual-composition="${composition.id}"]`);
      const card=thumb.locator('..');const downloadEvent=page.waitForEvent('download');await card.locator('[data-visual-download]').click();const download=await downloadEvent;
      const filename=`approved-${composition.image_id}.png`;await download.saveAs(path.join(OUT,filename));assert(download.suggestedFilename().includes(composition.image_id)&&download.suggestedFilename().includes(composition.id));
      const selectedPreview=await page.locator('#visual-preview>img').getAttribute('src');assert(selectedPreview.includes(composition.id));
      const expected=await page.evaluate(async url=>{const blob=await(await fetch(url)).blob();const data=await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.readAsDataURL(blob)});const img=await new Promise((r,j)=>{const i=new Image();i.onload=()=>r(i);i.onerror=j;i.src=data});const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);return c.toDataURL('image/png').split(',')[1]},composition.preview_url);
      assert.deepEqual(fs.readFileSync(path.join(OUT,filename)),Buffer.from(expected,'base64'));
      const svgResponse=await context.request.get(BASE+composition.download_url);assert.equal(svgResponse.status(),200);const svg=await svgResponse.body();const hash=require('crypto').createHash('sha256').update(svg).digest('hex');assert.equal(hash,composition.render_sha256);results.downloads.push({imageId:composition.image_id,compositionId:composition.id,filename,svgSha256:hash,pngSha256:require('crypto').createHash('sha256').update(Buffer.from(expected,'base64')).digest('hex')});
    }
    assert.notEqual(results.downloads[0].pngSha256,results.downloads[1].pngSha256);
  });
  let editResponse;
  await test('Edit dialog opens only on click and sends exact selected composition/raster reference',async()=>{
    const composition=fixture.compositions[0];const selectedThumb=page.locator(`[data-visual-image="${composition.image_id}"]`);await selectedThumb.click();await selectedThumb.locator('xpath=..').locator('[data-visual-edit]').click();await ready('.visual-edit-dialog[open]');assert.equal(await page.locator('.visual-edit-dialog').getAttribute('data-image-id'),composition.image_id);assert.equal(await page.locator('.visual-edit-dialog').getAttribute('data-composition-id'),composition.id);await shots('image-edit-modal');
    await page.locator('.visual-edit-dialog [name=message]').fill('Increase the background brightness slightly.');const waiting=page.waitForResponse(r=>r.url().endsWith('/api/edit-image-chat'));await page.locator('.visual-edit-dialog [type=submit]').click();editResponse=await waiting;const request=editResponse.request().postDataJSON();results.imageEditRequest={...request,reference_base64:request.reference_base64?'[PNG '+Buffer.from(request.reference_base64,'base64').length+' bytes]':undefined,mask:request.mask?'[PNG mask]':undefined};
    assert.equal(request.image_id,composition.image_id);assert.equal(request.composition_id,composition.id);assert.equal(request.source_render_sha256,composition.render_sha256);assert(request.reference_base64,'Missing raster reference_base64');assert.equal(editResponse.status(),201);
  });
  await test('New image is reference-derived, old images retained, new download gated',async()=>{
    assert(editResponse);const result=await editResponse.json();assert.equal(editResponse.status(),201,JSON.stringify(result));assert(result.image.id&&!fixture.images.includes(result.image.id));
    const saved=(await api('/api/images?task_id='+fixture.imageTask)).body;for(const id of fixture.images)assert(saved.images.some(i=>i.id===id));assert(saved.images.some(i=>i.id===result.image.id));const composition=saved.compositions.find(c=>c.image_id===result.image.id);assert(composition);assert.equal(composition.status,'pending_visual_approval');
    await ready(`[data-visual-image="${result.image.id}"]`);await ready('#visual-approval-form');await shots('image-edited-unapproved');
    const stats=(await api('/__test/stats')).body;const provider=stats.provider_calls.at(-1);assert(provider);assert.equal(result.image.reference_sha256,provider.reference_sha256);const bytes=await(await context.request.get(BASE+saved.images.find(i=>i.id===result.image.id).media_url)).body();assert.deepEqual(bytes,Buffer.from(provider.result_base64,'base64'));results.imageResult={id:result.image.id,referenceSha256:provider.reference_sha256,resultSha256:provider.result_sha256};
    assert.equal((await context.request.get(BASE+composition.preview_url+'&download=1')).status(),409);assert.equal((await api('/api/approve-visual',{composition_id:composition.id,inspected_image:false})).status,409);
    await page.locator('#visual-approval-form [name=inspected_image]').check();const approval=page.waitForResponse(r=>r.url()===BASE+'/api/approve-visual'&&r.request().method()==='POST');await page.locator('#visual-approval-form [type=submit]').click();assert.equal((await approval).status(),200);await page.locator(`[data-visual-image="${result.image.id}"]`).locator('xpath=..').locator('[data-visual-download]:enabled').waitFor();assert.equal((await context.request.get(BASE+'/api/visual-file?id='+composition.id+'&download=1')).status(),200);
  });
  await test('Project original photo preview and protection modal use saved project asset',async()=>{
    await goTask(fixture.imageTask);await ready('#original-image-select');assert.equal(await page.locator('#original-image-select').inputValue(),fixture.photo);await page.getByRole('button',{name:'Preview original photo',exact:true}).click();await ready('#selected-original-photo');await shots('original-photo-modal');await page.locator('#selected-original-photo button').click();
    await page.locator('#visual-mode').selectOption('edit');await page.getByRole('button',{name:'Protect product area',exact:true}).click();await ready('.photo-editor-dialog');await page.locator('.protection-canvas').waitFor();await page.waitForFunction(()=>document.querySelector('.protection-canvas')?.width===512);await page.locator('.center-protection').click();await shots('project-photo-mask');await page.locator('.confirm-protection').click();
  });
}

async function versionHistoryFlow(){
  const actual=fixture.actual;
  assert(actual&&actual.version_ids?.length===2,'isolated database must contain the preserved v1/v2 task');
  let serialized, savedState, v1, v2;
  await test('Actual Kopi Senja v1/v2 data stays linked before retry',async()=>{
    const projects=(await api('/api/projects')).body.projects;
    const project=projects.find(item=>item.id===actual.project_id);
    const task=project?.tasks.find(item=>item.id===actual.task_id);
    assert(task,'copied task is visible to the isolated acceptance account');
    serialized=task;v1=task.versions[0];v2=task.versions[1];
    assert.deepEqual(task.versions.map(item=>item.id),actual.version_ids);
    assert.equal(v1.review.id,actual.review_ids[0]);
    assert.equal(v1.review.verdict,'Needs Evidence');
    assert(v1.review.findings.some(item=>item.document_id===v1.id&&item.claim.toLowerCase().includes('menambah energi')));
    assert.equal(v2.review_status,'review_error');
    assert.equal(v2.review,null);
    assert.equal(v2.human_approved,0);
    assert.equal(task.remediation_count,1);
    assert.equal(task.versions.length,2);
    assert(!v2.content.toLowerCase().includes('menambah energi'));
    assert(v2.content.toLowerCase().includes('50 pengunjung pertama'));
    assert(v2.content.includes('diskon 50%'));
    await goTask(actual.task_id);await ready('#review-latest');await page.locator('.history-detail>summary').click();await shots('kopi-v2-before-retry');
    assert((await page.locator('#draft-display').innerText()).includes(v2.content));
    assert((await page.locator('.workbench-heading p').innerText()).includes('Reviewer failed'));
    const reviewPanel=await page.locator('.review-panel').innerText();
    assert(reviewPanel.includes('Reviewer failed before returning a result.'));
    assert.equal(await page.locator('.verdict-badge').count(),0);
    assert.equal(await page.locator('.finding').count(),0);
    assert(!reviewPanel.includes('Human approved'));
    assert(!reviewPanel.includes('Rejected'));
    assert.equal(await page.locator('.version-row').count(),2);
    const historyLabel=await page.locator('.version-section h2').innerText();
    assert.equal(historyLabel,'Every version, preserved',`Unexpected revision heading: ${historyLabel}`);
    const v1Row=await page.locator(`[data-editor-version="${v1.id}"]`).innerText();
    const v2Row=await page.locator(`[data-editor-version="${v2.id}"]`).innerText();
    assert(v1Row.includes('Writer draft')&&v1Row.includes('Needs evidence'));
    assert(v2Row.includes('Writer revision')&&v2Row.includes('Reviewer failed to complete'));
    assert(String(new Date(v2.created_at).getFullYear())&&v2Row.includes(String(new Date(v2.created_at).getFullYear())));
    const diffSummary=await page.locator('.version-diff summary').innerText();
    const diffText=await page.locator('.version-diff').innerText();
    assert(diffSummary.includes('passage')&&!diffSummary.includes('line'));
    assert(diffText.includes('menambah energi')&&diffText.includes('50 pengunjung pertama')&&diffText.includes('diskon 50%'));
    const blankDiff=await page.evaluate(()=>sentenceDiff('First paragraph.\n\nSecond paragraph.','First paragraph.\n\n\nSecond paragraph.'));
    assert(blankDiff.every(part=>part.type==='same'));
  });
  await test('Historical navigation and edit form do not create or alter versions',async()=>{
    await page.locator('.history-detail>summary').click();
    await page.locator('.history-detail>summary').click();
    await page.locator(`[data-editor-version="${v1.id}"]`).click();await page.waitForFunction(()=>document.querySelector('.workbench-heading p')?.textContent.includes('Version 1'));await ready('#draft-display');await shots('kopi-v1-history');
    assert((await page.locator('#draft-display').innerText()).includes(v1.content));
    assert((await page.locator('.review-panel').innerText()).includes('menambah energi'));
    assert((await page.locator('.workbench-heading p').innerText()).includes('Needs evidence'));
    assert.equal(await page.locator('#human-approve').count(),0);
    await page.getByRole('button',{name:'Edit as new version'}).click();await page.locator('#edit-form').waitFor({state:'visible'});
    assert.equal(await page.locator('#edit-form textarea').inputValue(),v1.content);
    assert.equal(await page.locator('.version-row').count(),2);
    await page.locator('#edit-form [type=submit]').click();
    await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('No content changed'));
    assert.equal(await page.locator('.version-row').count(),2);
    await page.locator('#cancel-edit').click();await page.waitForFunction(()=>document.querySelector('.workbench-heading p')?.textContent.includes('Version 1'));await ready('#draft-display');
    assert.equal(await page.locator('.version-row').count(),2);
    savedState=(await api('/__test/task-state?task='+actual.task_id)).body;
    assert.deepEqual(savedState.versions.map(item=>item.id),actual.version_ids);
    assert.equal(savedState.task.remediation_count,1);
    await page.getByRole('button',{name:'Return to latest version'}).click();await page.waitForFunction(()=>document.querySelector('.workbench-heading p')?.textContent.includes('Version 2'));await ready('#review-latest');
    assert((await page.locator('#draft-display').innerText()).includes(v2.content));
  });
  await test('Reviewer retry uses v2 ID and content without Writer, v3, or human approval',async()=>{
    const before=(await api('/__test/stats')).body;
    const requestPromise=page.waitForRequest(request=>request.url()===BASE+'/api/review-edit'&&request.method()==='POST');
    const responsePromise=page.waitForResponse(response=>response.url()===BASE+'/api/review-edit'&&response.request().method()==='POST');
    await page.locator('#review-latest').click();
    const request=await requestPromise,response=await responsePromise;
    assert.equal(response.status(),200,await response.text());
    assert.deepEqual(request.postDataJSON(),{task_id:actual.task_id,version_id:v2.id});
    await page.waitForFunction(()=>!document.querySelector('.review-retry-note'));
    await ready('#draft-display');
    const after=(await api('/__test/stats')).body;
    assert.equal(after.writer_calls,before.writer_calls);
    assert.deepEqual(after.llm_calls.slice(before.llm_calls.length).map(call=>call.role),['Reviewer']);
    const reviewerPayload=after.llm_calls.at(-1).payload;
    assert.equal(reviewerPayload.draft,v2.content);
    const sourceText=reviewerPayload.sources.map(source=>source.text||'').join('\n');
    assert(/first\s+50|50\s+(?:pengunjung|visitors)/i.test(sourceText));
    assert(/50\s*%/.test(sourceText));
    assert(/grand.?opening|hari ini/i.test(sourceText));
    const freshProjects=(await api('/api/projects')).body.projects;
    const freshTask=freshProjects.find(project=>project.id===actual.project_id).tasks.find(item=>item.id===actual.task_id);
    const latest=freshTask.versions.at(-1);
    assert.equal(freshTask.versions.length,2);
    assert.equal(latest.id,v2.id);
    assert.equal(latest.content,v2.content);
    assert.notEqual(latest.review_status,'review_error');
    assert(latest.review);
    assert.deepEqual(latest.review.findings.filter(item=>item.criterion.startsWith('Content quality:')).map(item=>item.criterion).sort(),['Content quality: Brief fit','Content quality: Brand voice consistency','Content quality: Clarity','Content quality: Copy quality','Content quality: Format compliance','Content quality: Platform fit','Content quality: Target audience fit'].sort());
    assert(latest.review.findings.every(item=>!item.document_id||item.document_id===latest.id));
    savedState=(await api('/__test/task-state?task='+actual.task_id)).body;
    assert.deepEqual(savedState.reviews.map(item=>item.version_id),actual.version_ids);
    assert.equal(savedState.reviews.at(-1).id,latest.review.id);
    assert.equal(savedState.task.remediation_count,1);
    assert.equal(savedState.writer_revision_count,1);
    assert.equal(savedState.approval_count,0);
    assert.equal(savedState.task.status,'approved_pending_human');
    assert.equal(latest.human_approved,0);
    assert.equal(await page.locator('#human-approve').count(),1);
    assert.equal(await page.locator('#download-draft').isDisabled(),true);
    assert.equal(await page.locator('#export-draft').isDisabled(),true);
    const copyButtons=page.locator('.ready-copy-card button');
    for(let index=0;index<await copyButtons.count();index++)assert.equal(await copyButtons.nth(index).isDisabled(),true);
    await shots('kopi-v2-reviewed-human-gate');
  });
}

(async()=>{
  browser=await chromium.launch({headless:true,channel:'chrome'});
  results.browserVersion=browser.version();
  context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route('**/*',async route=>{const url=new URL(route.request().url());if(['data:','blob:'].includes(url.protocol)||url.origin===BASE)return route.continue();results.externalRequests.push({origin:url.origin,path:url.pathname});await route.abort('blockedbyclient');});
  await context.request.get(BASE+'/__test/auth');page=await context.newPage();page.setDefaultTimeout(7000);
  page.on('console',m=>{if(m.type()==='error')results.consoleErrors.push({message:m.text(),location:m.location()});});page.on('pageerror',e=>results.pageErrors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'&&r.url().startsWith(BASE+'/api/')){let payload;try{payload=r.postDataJSON()}catch{}if(payload){delete payload.reference_base64;delete payload.mask;}results.requests.push({route:new URL(r.url()).pathname,payload});}});
  await page.goto(BASE);
  if(phase==='image')await imageFlows();else if(phase==='version-history')await versionHistoryFlow();else await textFlows();
  await test('No uncaught browser exceptions or external network calls',async()=>{assert.deepEqual(results.pageErrors,[]);assert.deepEqual(results.externalRequests,[]);const stats=(await api('/__test/stats')).body;assert.equal(stats.credentials_cleared,true);assert.deepEqual(stats.blocked_calls,[]);results.isolation={credentialsCleared:true,outboundCalls:0,database:stats.database};});
  await test('No visible content or control overflows desktop or mobile375 bounds',async()=>{const bad=results.overflow.filter(i=>i.scroll>i.width+2||i.body>i.width+2||i.offenders.length);assert.deepEqual(bad,[]);});
  results.finishedAt=new Date().toISOString();results.summary={pass:results.tests.filter(t=>t.status==='pass').length,fail:results.tests.filter(t=>t.status==='fail').length};save();console.log(JSON.stringify(results.summary));
})().catch(e=>{results.blocker=e.message;save();console.error(e.message);process.exitCode=1;}).finally(async()=>{await browser?.close();});
