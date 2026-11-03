// Real catalog UI + offline batch fixture. Test devices/apps are never shipped as catalog data.
const {chromium}=require('playwright');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const repo=path.resolve(__dirname,'..'),python=process.env.SYMPORT_PYTHON||'python3';
const shots=process.env.SYMPORT_SCREENSHOTS_DIR||path.join(repo,'build','screenshots');fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-catalog-ui-'));
 for(const dir of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,dir),path.join(root,dir),{recursive:true});
 const volume=path.join(root,'test-volume');fs.mkdirSync(volume);
 let server,browser,page;
 function start(script){return spawn(python,['-c',script,root],{cwd:repo,env:{...process.env,SYMPORT_DEVICE_ROOTS:JSON.stringify({'test-volume':volume}),SYMPORT_BRIDGE_URL:'',SYMPORT_GAMMU_CONFIG:''},stdio:['ignore','ignore','inherit']});}
 async function load(page){for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8772/?run='+Date.now()+'#catalog');await page.locator('.catalog-app').first().waitFor({timeout:3000});return;}catch(e){await new Promise(r=>setTimeout(r,200));}}throw Error('Catalog server not ready');}
 try{
  server=start("import sys; from symport.web import main; main(['--repo',sys.argv[1],'--port','8772'])");
  browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
  page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await load(page);await page.evaluate(()=>document.fonts.ready);
  if(await page.locator('.catalog-app').count()<30)throw Error('Missing curated entries');
  await page.screenshot({path:path.join(shots,'app-catalog-desktop.png')});
  await page.fill('#catalog-query','hotpants');if(await page.locator('.catalog-app').count()!==1)throw Error('Search failed');await page.locator('.catalog-app button').click();await page.locator('#catalog-detail[open]').waitFor();await page.screenshot({path:path.join(shots,'app-catalog-details.png')});await page.locator('#catalog-detail form button').click();await page.fill('#catalog-query','');
  await page.selectOption('#catalog-delivery','manual');if(!await page.locator('.catalog-app input').first().isDisabled())throw Error('Manual app queued');if(!await page.locator('.catalog-app a').first().getAttribute('href'))throw Error('Missing manual author link');
  await page.selectOption('#catalog-delivery','automatic');await page.selectOption('#catalog-network','offline');await page.click('#catalog-select-visible');await page.fill('#catalog-set-name','Browser offline set');await page.click('#catalog-save');await page.waitForFunction(()=>[...document.getElementById('catalog-sets').options].some(o=>o.value==='Browser offline set'));await page.reload();await page.waitForFunction(()=>[...document.getElementById('catalog-sets').options].some(o=>o.value==='Browser offline set'));
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(shots,'app-catalog-mobile.png')});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Catalog mobile overflow');
  // Replace only this temporary test catalog with fixtures; screenshot evidence above uses real data.
  server.kill();await new Promise(r=>server.once('exit',r));
  fs.rmSync(path.join(root,'catalog'),{recursive:true,force:true});fs.rmSync(path.join(root,'build'),{recursive:true,force:true});
  const setup=spawnSync(python,['-c',`import sys,json; from pathlib import Path; from tests.test_catalog import catalog_fixture,jar_bytes,artifact
root=Path(sys.argv[1]); catalog_fixture(root); directory=root/'catalog'; base=json.loads((directory/'apps/example.json').read_text())
for p in (directory/'apps').glob('*.json'): p.unlink()
sources={}
for i in range(10):
 key='fixture-'+str(i); entry=dict(base,id=key,name='Fixture '+str(i),source_id=key,dependencies=[])
 (directory/'apps'/(key+'.json')).write_text(json.dumps(entry)); sources[key]={'artifacts':[artifact(jar_bytes(key),key+'.jar')]}
(directory/'sources.json').write_text(json.dumps(sources))`,root],{cwd:repo});if(setup.status!==0)throw Error(setup.stderr.toString());
  server=start(`import sys,io
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench,make_handler
from tests.test_catalog import jar_bytes
import symport.catalog.download as download
state=Workbench(Path(sys.argv[1]))
class FixtureOpener:
 def open(self,request,timeout):
  key=request.full_url.rsplit('/',1)[-1].removesuffix('.jar'); raw=jar_bytes(key); response=io.BytesIO(raw); response.headers={'Content-Length':str(len(raw))}; response.geturl=lambda:request.full_url; return response
state.catalog.downloader.opener=FixtureOpener(); download.public_https=lambda url:None
ThreadingHTTPServer(('127.0.0.1',8772),make_handler(state)).serve_forever()`);
  await page.setViewportSize({width:1440,height:1100});await load(page);await page.click('#catalog-select-visible');await page.click('#catalog-plan');await page.waitForFunction(()=>!document.getElementById('catalog-download').disabled);await page.click('#catalog-download');await page.waitForFunction(()=>document.querySelectorAll('.catalog-job:first-child .catalog-result').length===10&&document.querySelector('.catalog-job:first-child').textContent.includes('Операция завершена'),{timeout:15000});
  const zipPromise=page.waitForEvent('download');await page.locator('.catalog-job:first-child a').click();if((await zipPromise).suggestedFilename()!=='symport-apps.zip')throw Error('Batch export failed');
  await page.locator('#catalog .suite-discover').click();await page.waitForFunction(()=>!!document.getElementById('catalog-device').value);page.once('dialog',d=>d.accept());await page.click('#catalog-transfer');await page.waitForFunction(()=>[...document.querySelectorAll('.catalog-job:first-child .catalog-result')].filter(r=>r.textContent.includes('Ожидает установки')).length===10,{timeout:15000});
  if(fs.readdirSync(volume).filter(f=>f.endsWith('.jar')).length!==10)throw Error('Batch did not transfer 10 fixture JARs');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS: real 30-entry UI, filters/details/manual mode/saved sets/mobile; offline 10-app fixture queue, ZIP and mock-volume transfer. No handset installation claimed.');
 }catch(error){if(page){console.error(await page.locator('#catalog').innerText());await page.screenshot({path:path.join(shots,'catalog-failure.png'),fullPage:true});}throw error;}finally{if(browser)await browser.close();if(server)server.kill();fs.rmSync(root,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
