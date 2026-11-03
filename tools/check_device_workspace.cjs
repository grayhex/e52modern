// Stateful mock Gammu + real enrolled filesystem and browser HTTP Range.
const {chromium}=require('playwright'),{spawn}=require('child_process'),fs=require('fs'),os=require('os'),path=require('path');
const repo=path.resolve(__dirname,'..'),root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-device-ui-')),python=process.env.SYMPORT_PYTHON||'python3',shots=path.join(repo,'build/screenshots');fs.mkdirSync(shots,{recursive:true});
for(const name of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
const script=`import sys,os,json,wave
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from tests.test_device_workspace import MockPhone
from symport.web import Workbench,make_handler
from symport.phone.local import LocalTransports
r=Path(sys.argv[1]);v=r/'volume';(v/'Images').mkdir(parents=True);Image.new('RGB',(640,480),'#22d3ee').save(v/'Images/sample.jpg')
with wave.open(str(v/'sample.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(bytes(16000))
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'test-volume':str(v)}),SYMPORT_GAMMU_CONFIG='mock-only',SYMPORT_MGO_URL='',SYMPORT_BRIDGE_URL='')
w=Workbench(r);local=LocalTransports(r);phone=MockPhone();local.personal.invoke=phone.invoke
local.devices=lambda: local.files.devices()+[dict(phone.identity,id='gammu',transport='gammu',connected=True,model='Nokia E52 (mock transport)',firmware='081.003',capabilities=['device-details','personal-data','contacts-read','calendar-read','tasks-read','sms-read'],capability_status={k:{'status':'available'} for k in phone.records},sms_send_verified=False)]
w.devices.transport=local
ThreadingHTTPServer(('127.0.0.1',8779),make_handler(w)).serve_forever()`;
const server=spawn(python,['-c',script,root],{cwd:repo,env:process.env,stdio:['ignore','ignore','inherit']});
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8779');break;}catch{await new Promise(r=>setTimeout(r,200));}}
 await page.waitForFunction(()=>Object.keys(uiTranslations.en).length>100);await page.selectOption('#ui-language','en');await page.selectOption('#ui-theme','dark');
 await page.click('[data-nav="connection"]');await page.click('#dm-discover');await page.waitForFunction(()=>dmDevices.length===2);await page.selectOption('#dm-device','gammu');await page.click('[data-nav="updates"]');await page.locator('#updates.visible').waitFor();if(!await page.locator('#updates button.primary').isDisabled())throw Error('Firmware flashing must remain disabled');
 await page.click('[data-nav="files"]');
 for(const [input,button]of [['dm-path','dm-list'],['dm-upload','dm-send'],['dm-dir','dm-mkdir']]){const a=await page.locator('#'+input).boundingBox(),b=await page.locator('#'+button).boundingBox();if(Math.abs(a.height-b.height)>1)throw Error('File control height mismatch');}
 await page.click('[data-nav="connection"]');await page.selectOption('#dm-device','test-volume');await page.click('[data-nav="manager"]');
 if(await page.locator('#manager .mini-tile,#manager input[type=file],#manager #dm-send').count())throw Error('Dashboard still duplicates actions');
 if(!await page.locator('.device-reading').first().evaluate(n=>getComputedStyle(n).color===getComputedStyle(document.body).color))throw Error('Dashboard readings lost foreground contrast');
 if(await page.locator('.phone-dashboard .value-state--unknown').count()<4)throw Error('Unknown device fields hidden or invented');
 await page.waitForTimeout(150);await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'device-dashboard-dark.png'),fullPage:true,animations:"disabled"});
 await page.click('[data-nav="media"]');await page.click('#gallery-read');await page.waitForFunction(()=>document.querySelectorAll('.media-item').length===2);await page.locator('.media-item img').waitFor();
 await page.fill('#gallery-search','sample.jpg');if(await page.locator('.media-item').count()!==1)throw Error('Media search failed');await page.fill('#gallery-search','');
 await page.selectOption('#gallery-kind','audio');if(await page.locator('.media-item').count()!==1)throw Error('Media filter failed');await page.locator('.media-open').click();await page.locator('#gallery-preview[open] audio').waitFor();
 const range=await page.evaluate(async()=>{const u=document.querySelector('#gallery-player audio').src,r=await fetch(u,{headers:{Range:'bytes=0-43'}});return {status:r.status,range:r.headers.get('Content-Range'),bytes:[...new Uint8Array(await r.arrayBuffer())]};});if(range.status!==206||range.bytes.length!==44||String.fromCharCode(...range.bytes.slice(0,4))!=='RIFF')throw Error('Real ranged media preview failed');
 await page.click('#gallery-close');await page.selectOption('#gallery-kind','');await page.click('#gallery-select');const zipPromise=page.waitForEvent('download');await page.click('#gallery-download');const zip=await zipPromise;const archive=path.join(root,'download.zip');await zip.saveAs(archive);if(zip.suggestedFilename()!=='symport-media.zip'||!fs.statSync(archive).size)throw Error('Bulk media download failed');
 await page.waitForTimeout(150);await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'media-gallery-dark.png'),fullPage:true,animations:"disabled"});
 await page.click('[data-nav="contacts"]');await page.selectOption('#contacts-device','gammu');await page.click('#contacts-read');await page.waitForFunction(()=>document.querySelectorAll('#contacts-rows tr').length===1);await page.locator('#contacts-rows tr input[aria-label^="Телефоны"],#contacts-rows tr td:nth-child(3) input').fill('+987654321');await page.locator('#contacts-rows tr td:nth-child(3) input').blur();
 await page.click('#contacts-sync-preview');await page.locator('#contacts-sync-apply:not([hidden])').waitFor();if(!(await page.locator('#contacts-sync-plan').innerText()).includes('+987654321'))throw Error('Sync preview omitted the actual field change');
 page.once('dialog',d=>d.accept());const backupPromise=page.waitForEvent('download');await page.click('#contacts-sync-apply');const backup=await backupPromise;await backup.saveAs(path.join(root,'contacts-backup.json'));await page.waitForFunction(()=>document.getElementById('contacts-result').textContent.includes('verified'));
 if(!fs.readFileSync(path.join(root,'contacts-backup.json'),'utf8').includes('+123456789'))throw Error('Original contact not backed up');
 await page.click('[data-nav="messages"]');await page.selectOption('#sms-device','gammu');await page.click('#sms-read');await page.waitForFunction(()=>document.querySelectorAll('#sms-rows article').length===1);
 await page.fill('#sms-search','absent');if(await page.locator('#sms-rows article').count())throw Error('SMS search failed');await page.fill('#sms-search','');await page.selectOption('#sms-thread','+123456789');
 const csvPromise=page.waitForEvent('download');await page.click('#sms-csv');const csv=await csvPromise;await csv.saveAs(path.join(root,'sms.csv'));if(!fs.readFileSync(path.join(root,'sms.csv'),'utf8').includes("'=PRIVATE-SMS"))throw Error('SMS export/formula defense failed');if(!await page.locator('#sms-send').isDisabled())throw Error('Unverified SMS sending enabled');
 await page.click('[data-nav="calendar"]');await page.selectOption('#calendar-device','gammu');await page.click('#calendar-read');await page.waitForFunction(()=>document.querySelectorAll('#calendar-events tr').length===1);
 await page.locator('#calendar-events button').click();await page.fill('#pim-cal-summary','Updated through browser');await page.locator('#pim-calendar-editor button[type="submit"]').click();await page.locator('#pim-calendar-apply:not([hidden])').waitFor();page.once('dialog',d=>d.accept());const calBackup=page.waitForEvent('download');await page.click('#pim-calendar-apply');await calBackup;await page.waitForFunction(()=>document.getElementById('pim-calendar-status').textContent.includes('verified'));
 await page.selectOption('#pim-calendar-domain','tasks');await page.waitForFunction(()=>document.querySelectorAll('#calendar-todos tr').length===1);await page.click('#pim-calendar-new');await page.fill('#pim-cal-summary','New task');await page.fill('#pim-cal-end','2030-01-03T12:00');await page.locator('#pim-calendar-editor button[type="submit"]').click();await page.locator('#pim-calendar-apply:not([hidden])').waitFor();
 // Destructive privacy check: ordinary operation journal must contain no phone content.
 const log=fs.readFileSync(path.join(root,'build/symport/device-manager/operations.jsonl'),'utf8');if(/PRIVATE-SMS|123456789|987654321|Private appointment|private@example|Updated through/.test(log))throw Error('Private content in ordinary journal');
 await page.setViewportSize({width:390,height:844});for(const id of ['manager','updates','media','contacts','messages','calendar']){await page.evaluate(id=>location.hash='#'+id,id);await page.locator('#'+id+'.visible').waitFor();if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow: '+id);}
 await page.screenshot({path:path.join(shots,'device-workspace-mobile.png'),fullPage:true,animations:"disabled"});if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS: real thumbnails/ranged WAV/ZIP, dashboard unknown values, contact edit/preview/backup/readback, SMS search/thread/CSV/disabled send, calendar edit/task preview, privacy and mobile layout. Gammu is a stateful mock.');
}finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
