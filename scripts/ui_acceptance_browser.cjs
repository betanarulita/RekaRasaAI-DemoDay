const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {createRequire} = require('module');
const cliRequire = createRequire(path.join(require('child_process').execSync('npm root -g', {encoding:'utf8'}).trim(), '@playwright/cli/package.json'));
const {chromium} = cliRequire('playwright');
const BASE = 'http://127.0.0.1:8016';
const OUT = 'C:/Users/Beta/WorkBuddy AI/2026-11-04-16-39-26/evidence-ui';
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
      if(dialog?.includes('visual-edit')){await target.locator('#edit-selected-visual').waitFor();await target.locator('#edit-selected-visual').click();await target.locator('.visual-edit-dialog[open]').waitFor();}
      if(dialog?.includes('original-photo')){await target.getByRole('button',{name:'Preview original photo',exact:true}).click();}
      else if(dialog?.includes('photo-editor')){await target.locator('#visual-mode').selectOption('edit');await target.getByRole('button',{name:'Protect product area',exact:true}).click();await target.waitForFunction(()=>document.querySelector('.protection-canvas')?.width===512);await target.locator('.center-protection').click();}
    }
    await target.evaluate(()=>document.fonts.ready);
    await target.locator('.page-content img,dialog[open] img').evaluateAll(images=>Promise.all(images.map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.addEventListener('load',resolve,{once:true});img.addEventListener('error',resolve,{once:true})}))));
    const filename=`${phase}-${name}-${label}.png`;
    await target.screenshot({path:path.join(OUT,filename),fullPage:true});
    results.screenshots.push({view:name,viewport:label,file:filename});
    const geometry=await target.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,offenders:[...document.querySelectorAll('.page-content * ,dialog[open] *')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&(r.right>innerWidth+2||r.left<-2)&&s.position!=='fixed'&&s.visibility!=='hidden'&&e.checkVisibility()}).slice(0,8).map(e=>({tag:e.tagName,id:e.id,cls:String(e.className).slice(0,70),right:Math.round(e.getBoundingClientRect().right)}))}));
    results.overflow.push({view:name,viewport:label,...geometry});
    if(target!==page)await target.close();
  }
  save();
}
async function goTask(task){await page.goto(BASE+'/#view='+encodeURIComponent(JSON.stringify({page:'workbench',taskId:task})));await ready('#draft-display');}
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
    await nav('new');await ready('#brief');await page.locator('[name=project_id]').selectOption(fixture.project);
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
    await page.locator('#brief').fill('Create a Kopi Senja caption with a revised quiet direction.');const response=await submitBrief();const body=await response.json();assert.equal(response.status(),200);assert.equal(body.plan_id,planId);assert.equal(body.plan.revision,1);
    await ready('#continue-project');await page.locator('#continue-project').click();await ready('.project-detail-page');assert.equal(await page.locator('[data-saved-plan="'+planId+'"]').count(),1);await shots('project-detail');
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
    const composition=fixture.compositions[0];await page.locator(`[data-visual-image="${composition.image_id}"]`).click();await page.locator('#edit-selected-visual').click();await ready('.visual-edit-dialog[open]');assert.equal(await page.locator('.visual-edit-dialog').getAttribute('data-image-id'),composition.image_id);assert.equal(await page.locator('.visual-edit-dialog').getAttribute('data-composition-id'),composition.id);await shots('image-edit-modal');
    await page.locator('.visual-edit-dialog [name=message]').fill('Increase the background brightness slightly.');const waiting=page.waitForResponse(r=>r.url().endsWith('/api/edit-image-chat'));await page.locator('.visual-edit-dialog [type=submit]').click();editResponse=await waiting;const request=editResponse.request().postDataJSON();results.imageEditRequest={...request,reference_base64:request.reference_base64?'[PNG '+Buffer.from(request.reference_base64,'base64').length+' bytes]':undefined,mask:request.mask?'[PNG mask]':undefined};
    assert.equal(request.image_id,composition.image_id);assert.equal(request.composition_id,composition.id);assert.equal(request.source_render_sha256,composition.render_sha256);assert(request.reference_base64,'Missing raster reference_base64');assert.equal(editResponse.status(),201);
  });
  await test('New image is reference-derived, old images retained, new download gated',async()=>{
    assert(editResponse);const result=await editResponse.json();assert.equal(editResponse.status(),201,JSON.stringify(result));assert(result.image.id&&!fixture.images.includes(result.image.id));
    const saved=(await api('/api/images?task_id='+fixture.imageTask)).body;for(const id of fixture.images)assert(saved.images.some(i=>i.id===id));assert(saved.images.some(i=>i.id===result.image.id));assert(saved.compositions.find(c=>c.image_id===result.image.id).status!=='human_approved');
    await ready(`[data-visual-image="${result.image.id}"]`);assert(await page.locator('#download-visual-png').isDisabled());await shots('image-edited-unapproved');
    const stats=(await api('/__test/stats')).body;const provider=stats.provider_calls.at(-1);assert(provider);assert.equal(result.image.reference_sha256,provider.reference_sha256);const bytes=await(await context.request.get(BASE+saved.images.find(i=>i.id===result.image.id).media_url)).body();assert.deepEqual(bytes,Buffer.from(provider.result_base64,'base64'));results.imageResult={id:result.image.id,referenceSha256:provider.reference_sha256,resultSha256:provider.result_sha256};
    const composition=saved.compositions.find(c=>c.image_id===result.image.id);assert.equal((await context.request.get(BASE+composition.preview_url+'&download=1')).status(),409);assert.equal((await api('/api/approve-visual',{composition_id:composition.id,inspected_image:false})).status,409);
    await page.locator('#visual-approval-form [name=inspected_image]').check();await page.locator('#visual-approval-form [type=submit]').click();await page.locator('#download-visual-png:enabled').waitFor();
  });
  await test('Project original photo preview and protection modal use saved project asset',async()=>{
    await goTask(fixture.imageTask);await ready('#original-image-select');assert.equal(await page.locator('#original-image-select').inputValue(),fixture.photo);await page.getByRole('button',{name:'Preview original photo',exact:true}).click();await ready('#selected-original-photo');await shots('original-photo-modal');await page.locator('#selected-original-photo button').click();
    await page.locator('#visual-mode').selectOption('edit');await page.getByRole('button',{name:'Protect product area',exact:true}).click();await ready('.photo-editor-dialog');await page.locator('.protection-canvas').waitFor();await page.waitForFunction(()=>document.querySelector('.protection-canvas')?.width===512);await page.locator('.center-protection').click();await shots('project-photo-mask');await page.locator('.confirm-protection').click();
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
  if(phase==='image')await imageFlows();else await textFlows();
  await test('No uncaught browser exceptions or external network calls',async()=>{assert.deepEqual(results.pageErrors,[]);assert.deepEqual(results.externalRequests,[]);const stats=(await api('/__test/stats')).body;assert.equal(stats.credentials_cleared,true);assert.deepEqual(stats.blocked_calls,[]);results.isolation={credentialsCleared:true,outboundCalls:0,database:stats.database};});
  await test('No horizontal document overflow at desktop or mobile375',async()=>{const bad=results.overflow.filter(i=>i.scroll>i.width+2||i.body>i.width+2);assert.deepEqual(bad,[]);});
  results.finishedAt=new Date().toISOString();results.summary={pass:results.tests.filter(t=>t.status==='pass').length,fail:results.tests.filter(t=>t.status==='fail').length};save();console.log(JSON.stringify(results.summary));
})().catch(e=>{results.blocker=e.message;save();console.error(e.message);process.exitCode=1;}).finally(async()=>{await browser?.close();});
