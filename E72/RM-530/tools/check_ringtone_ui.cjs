process.env.SYMPORT_FRONTEND = 'classic'; // Explicit rollback-interface regression coverage.
// Real FFmpeg + local WaveSurfer + actual mounted folder. E72 identity is an explicit test fixture.
const {chromium}=require('playwright'),{spawn,spawnSync}=require('child_process'),fs=require('fs'),os=require('os'),path=require('path');
const repo=path.resolve(__dirname,'..'),root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-ringtone-')),python=process.env.SYMPORT_PYTHON||'python3';
for(const name of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
const script=`import sys,os,json,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench,make_handler
from symport.phone.local import LocalTransports
from tests.test_ringtone import audio_bytes
r=Path(sys.argv[1]);v=r/'volume';v.mkdir();(v/'sample.wav').write_bytes(audio_bytes(8));
import wave,math,struct
with wave.open(str(v/'sample.wav'),'rb') as w: params=w.getparams();frames=w.readframes(w.getnframes())
values=struct.unpack('<'+'h'*(len(frames)//2),frames);shaped=[int(x*(.12+.88*(.5+.5*math.sin((i//2)/44100*2.3)))) for i,x in enumerate(values)]
with wave.open(str(v/'sample.wav'),'wb') as w:w.setparams(params);w.writeframes(struct.pack('<'+'h'*len(shaped),*shaped))
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'card':str(v)}),SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_BRIDGE_URL='')
w=Workbench(r);original=w.devices.transport.devices
from tests.capfake import row as capability_row
w.devices.transport.devices=lambda:original()+[capability_row({'id':'e72-fixture','model':'Nokia E72 (RM-530)','firmware':'091.004','connected':True,'transport':'test-fixture'})]
ThreadingHTTPServer(('127.0.0.1',8782),make_handler(w)).serve_forever()`;
const server=spawn(python,['-c',script,root],{cwd:repo,env:process.env,stdio:['ignore','ignore','inherit']});
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],external=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith('http://127.0.0.1:8782/'))external.push(r.url());});
 for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8782');break;}catch{await new Promise(r=>setTimeout(r,200));}}
 await page.waitForFunction(()=>Object.keys(uiTranslations.en).length>100);await page.selectOption('#ui-language','en');
 await page.click('[data-nav="connection"]');await page.click('#dm-discover');await page.waitForFunction(()=>dmDevices.length===2);await page.selectOption('#dm-device','e72-fixture');await page.click('[data-nav="manager"]');await page.locator('#manager.visible').waitFor();await page.waitForFunction(()=>{const i=document.querySelector('.dashboard-phone');return i.complete&&i.naturalWidth>0;});
 if(!(await page.locator('#dm-info').innerText()).includes('320 × 240')||!(await page.locator('.dashboard-phone').getAttribute('src')).includes('e72'))throw Error('E72 profile/presentation not detected');if(await page.locator('#manager input,#manager select,#manager .mini-tile').count())throw Error('Active controls remain on dashboard');
 const proportions=await page.locator('.dashboard-phone').evaluate(n=>({ratio:n.getBoundingClientRect().height/n.getBoundingClientRect().width,natural:n.naturalHeight/n.naturalWidth}));if(Math.abs(proportions.ratio-proportions.natural)>.02)throw Error('Phone illustration stretched by layout');
 const shots=path.join(repo,'build/screenshots');fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,'e72-dashboard-light.png'),fullPage:true,animations:'disabled'});
 await page.click('[data-nav="media"]');await page.click('#gallery-read');await page.locator('.media-item .btn').click();await page.locator('#ringtone.visible').waitFor();await page.waitForFunction(()=>!document.querySelector('#rt-editor').hidden&&!document.querySelector('#rt-export').disabled&&document.querySelector('#rt-wave').querySelector('div'));
 await page.selectOption('#rt-preset','notification');await page.fill('#rt-start','1');await page.locator('#rt-start').blur();await page.fill('#rt-end','5');await page.locator('#rt-end').blur();await page.locator('#rt-advanced summary').click();await page.fill('#rt-fade-in','0.2');await page.fill('#rt-fade-out','0.4');await page.selectOption('#rt-rate','22050');await page.click('#rt-play');await page.waitForTimeout(300);await page.click('#rt-stop');await page.locator('#rt-zoom').fill('100');
 await page.click('#rt-export');await page.waitForFunction(()=>!document.querySelector('#rt-output').hidden&&!document.querySelector('#rt-export').disabled);await page.waitForFunction(()=>document.querySelector('#rt-processed').readyState>=1);
 const info=await page.locator('#rt-output-meta').innerText();if(!info.includes('1 ch')||!info.includes('22050'))throw Error('Processed output metadata missing');
 const audioUrl=await page.locator('#rt-processed').getAttribute('src');if(audioUrl.endsWith('preview'))throw Error('Output player uses source instead of export');
 const download=page.waitForEvent('download');await page.click('#rt-download');const saved=await download;const dest=path.join(root,'export.mp3');await saved.saveAs(dest);
 const probe=spawnSync('ffprobe',['-v','error','-show_entries','format=duration:stream=channels,sample_rate','-of','json',dest],{encoding:'utf8'});const meta=JSON.parse(probe.stdout);if(meta.streams[0].channels!==1||Math.abs(Number(meta.format.duration)-4)>.15)throw Error('Wrong real MP3 output');
 page.once('dialog',d=>d.accept());await page.click('#rt-send');await page.waitForFunction(()=>document.querySelector('#rt-transfer-status').textContent.length>0);const phone=fs.readdirSync(path.join(root,'volume')).find(n=>n.endsWith('.mp3'));if(!phone||!fs.readFileSync(path.join(root,'volume',phone)).equals(fs.readFileSync(dest)))throw Error('Ringtone transfer differs from processed download');
 await page.setViewportSize({width:1366,height:768});await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(100);await page.evaluate(()=>document.getElementById('rt-advanced').open=false);await page.screenshot({path:path.join(shots,'ringtone-studio-light-en.png'),fullPage:true,animations:'disabled'});
 await page.selectOption('#ui-language','ru');await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(100);await page.screenshot({path:path.join(shots,'ringtone-studio-light-ru.png'),fullPage:true,animations:'disabled'});
 await page.setViewportSize({width:1366,height:768});await page.evaluate(()=>window.scrollTo(0,0));const compact=await page.evaluate(()=>({bottom:document.getElementById('rt-editor').getBoundingClientRect().bottom,logo:document.querySelector('.brand-lockup').getBoundingClientRect().top}));if(compact.bottom>768||compact.logo<0||compact.logo>32)throw Error('Studio exceeds laptop viewport or logo is not top anchored: '+JSON.stringify(compact));
 await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Studio mobile overflow');
 await page.click('#rt-clear');await page.waitForFunction(()=>document.querySelector('#rt-editor').hidden);if(fs.readdirSync(path.join(root,'build/symport/ringtone-temp')).length)throw Error('Temporary source not deleted');
 if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));console.log('PASS: actual FFmpeg/WaveSurfer, gallery source, preset/edit/zoom/play, normalized mono MP3/fades, exact download/confirmed transfer, cleanup, E72, Nimbus RU/EN/mobile; no external services.');
}finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
