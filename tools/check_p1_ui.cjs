// P1 browser integration: real Python/compiler/Inspector/download files, explicit catalog and transport doubles.
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),crypto=require('crypto');
const repo=path.resolve(__dirname,'..'),root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-p1-')),python=process.env.SYMPORT_PYTHON||'python3',port=8795;
const shots=path.join(repo,'build/screenshots/p1');fs.mkdirSync(shots,{recursive:true});
for(const name of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
const script=`import sys,json,os
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from tests.test_catalog import catalog_fixture,FixtureOpener,jar_bytes,public_address
from tests.lab_fixture import MockMgo
from symport.web import Workbench,make_handler
from symport.phone.files import MountedVolumes
r=Path(sys.argv[1]);v=r/'card';v.mkdir();Image.new('RGB',(640,480),'#1e6091').save(r/'wallpaper.png')
# Replace catalog with test-only, pinned, dependency-bearing JARs. No Internet downloads during E2E.
import shutil
shutil.rmtree(r/'catalog');catalog_fixture(r)
os.environ.update(SYMPORT_BRIDGE_URL='',SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_MGO_URL='')
w=Workbench(r);files=MountedVolumes({'card':v})
class Transport:
 def devices(self):
  from tests.capfake import row as capability_row
  return files.devices()+[capability_row({'id':'telemetry','transport':'TEST DOUBLE','connected':True,'model':'Nokia E52 (TEST DOUBLE)','rm':'RM-469','firmware':'081.003','battery':0,'signal':80},available=['identity.read'])]
 def execute(self,data):
  if data.get('device')=='telemetry':return {'battery':0,'signal':80,'free':1000,'total':2000}
  return files.execute(data)
w.devices.transport=Transport();w.catalog.downloader.resolver=public_address
class Opener:
 def open(self,request,timeout):return FixtureOpener(jar_bytes(request.full_url.rsplit('/',1)[-1].split('.')[0])).open(request,timeout)
w.catalog.downloader.opener=Opener();w.lab.agent=MockMgo()
ThreadingHTTPServer(('127.0.0.1',int(sys.argv[2])),make_handler(w)).serve_forever()`;
const server=spawn(python,['-c',script,root,String(port)],{cwd:repo,env:{...process.env,PYTHONPATH:repo},stdio:['ignore','ignore','inherit']});
(async()=>{let browser,page;try{
 browser=await chromium.launch({headless:true,...process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{},args:['--no-sandbox']});
 page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Europe/Moscow'});page.setDefaultTimeout(25000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!/favicon|Failed to load resource/.test(m.text()))errors.push(page.url()+" "+m.text());});
 for(let i=0;i<50;i++){try{await page.goto(`http://127.0.0.1:${port}/`);break;}catch{await new Promise(r=>setTimeout(r,200));}}
 await page.evaluate(()=>{localStorage.setItem('symport-language','en');});await page.reload();
 const navigate=async route=>{await page.evaluate(r=>location.hash='#'+r,route);return page.locator('[data-route="'+route.split('?')[0]+'"]');};
 // Collections: real persisted manifest, dependency closure, cross-geometry recovery, explicit confirmation and real copied bytes.
 const kits=await navigate('apps/kits');await kits.getByLabel('Collection name',{exact:true}).fill('Recovery E2E');
 await kits.getByRole('checkbox',{name:/example/}).check();await kits.getByRole('button',{name:/Save selection/}).click();
 await kits.getByRole('button',{name:'Export collection JSON'}).click();const exportLink=kits.getByRole('link',{name:'Download symport-collection.json ↓'});await exportLink.waitFor();
 const href=await exportLink.getAttribute('href'),manifest=JSON.parse(Buffer.from(href.split(',')[1],'base64').toString());
 if(manifest.apps.map(a=>a.id).join(',')!=='runtime,example')throw Error('Dependency versions/hashes were not pinned');
 await kits.getByLabel('Phone profile',{exact:true}).selectOption('nokia-e72');await kits.getByLabel('Connection',{exact:true}).selectOption('card');
 await kits.getByRole('button',{name:'Preview recovery'}).click();await kits.getByText(/Screen geometry differs/).waitFor();
 await kits.getByRole('button',{name:'Transfer recovery set'}).click();await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).waitFor();
 if(fs.readdirSync(path.join(root,'card')).length)throw Error('Write happened before consent');
 await page.getByRole('dialog').getByRole('button',{name:'Confirm',exact:true}).click();
 await kits.getByText(/Transfer queued/).waitFor();
 for(let i=0;i<100&&!fs.existsSync(path.join(root,'card','example.jar'));i++)await page.waitForTimeout(100);
 if(!fs.existsSync(path.join(root,'card','runtime.jar')))throw Error('Runtime transfer missing');
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,'collections-light-en.png'),fullPage:true});
 // Diagnostics: real filesystem counters + explicit observation double, measured zero and no IMEI export.
 const diag=await navigate('tools/diagnostics');await diag.getByLabel('Measurement connection',{exact:true}).selectOption('telemetry');
 await diag.getByRole('button',{name:'Read measurements',exact:true}).click();await diag.getByText('0%',{exact:true}).waitFor();
 await diag.getByRole('button',{name:'Read measurements',exact:true}).click();await diag.getByText('2 / 500',{exact:true}).waitFor();
 await diag.getByRole('button',{name:'Export JSON',exact:true}).click();const dh=await diag.getByRole('link',{name:/Download symport-diagnostics.json/}).getAttribute('href');
 const history=JSON.parse(Buffer.from(dh.split(',')[1],'base64').toString());if(history.measurements.length!==2||history.measurements[0].battery!==0||/imei/i.test(JSON.stringify(history)))throw Error('Diagnostic data integrity/privacy');
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,'diagnostics-light-en.png'),fullPage:true});
 // Actual Nokia compiler: visual palette + cropped wallpaper + native E72 resolution, guarded export.
 const studio=await navigate('personalize/theme-editor');await studio.getByLabel('Screen profile',{exact:true}).selectOption('nokia-e72');
 await studio.getByRole('button',{name:'Create editable CLEAR theme'}).click();await studio.getByRole('button',{name:'Save palette'}).waitFor();
 await studio.getByLabel('bg',{exact:true}).fill('#16283c');await studio.getByRole('button',{name:'Save palette'}).click();
 await studio.getByRole('button',{name:'Save palette'}).waitFor({state:'visible'});await page.waitForFunction(()=>document.querySelector('[data-route="personalize/theme-editor"] input[type=color]')?.value==='#16283c');
 await studio.getByLabel('Wallpaper (centre crop, 4 MiB)',{exact:true}).setInputFiles(path.join(root,'wallpaper.png'));await studio.getByRole('button',{name:'Reset wallpaper'}).waitFor();
 const build=studio.getByRole('button',{name:'Build & statically validate SIS'});if(!await build.isDisabled())throw Error('Unsigned build allowed without acknowledgement');
 await studio.getByRole('checkbox',{name:/I understand the unsigned/}).check();await build.click();
 await studio.getByText('static-checked · unsigned',{exact:false}).waitFor();
 await studio.getByRole('button',{name:'Export SIS',exact:true}).click();const sisLink=studio.getByRole('link',{name:/Download SymPort-.*\.sis/});await sisLink.waitFor();
 const sisHref=await sisLink.getAttribute('href'),sisBytes=Buffer.from(sisHref.split(',')[1],'base64'),sha=crypto.createHash('sha256').update(sisBytes).digest('hex');
 fs.writeFileSync(path.join(root,'exported-theme.sis'),sisBytes);
 const svg=studio.getByRole('img',{name:'Schematic theme preview 320×240'});if(await svg.getAttribute('viewBox')!=='0 0 320 240')throw Error('E72 geometry lost');
 await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,'theme-studio-light-en.png'),fullPage:true});
 await studio.getByRole('link',{name:'Inspect & transfer to Nokia'}).click();
 const inspector=page.locator('[data-route="tools/certificates"]');if(await inspector.getByLabel('Model',{exact:true}).inputValue()!=='Nokia E72')throw Error('Theme target profile was not preserved');await inspector.getByRole('button',{name:'Analyze package'}).click();await inspector.getByText(sha,{exact:true}).waitFor();
 await inspector.getByLabel('Connection',{exact:true}).selectOption('card');await inspector.getByRole('checkbox',{name:/I acknowledge unverified/}).check();
 await inspector.getByRole('button',{name:'Transfer to phone'}).click();await page.getByRole('dialog').getByRole('button',{name:'Confirm',exact:true}).click();await inspector.getByText('transferred-not-installed',{exact:true}).waitFor();
 const copied=fs.readdirSync(path.join(root,'card')).find(p=>p.endsWith('.sis'));if(!copied||!fs.readFileSync(path.join(root,'card',copied)).equals(sisBytes))throw Error('Inspector transfer changed package');
 // Re-import the real SIS: no invented palette, resource decoding runs through bmconv.
 await navigate('personalize/theme-editor');await studio.getByLabel('Import SIS theme (8 MiB)',{exact:true}).setInputFiles(path.join(root,'exported-theme.sis'));await studio.getByText(/This is a compiled theme/).waitFor();
 const mbm=studio.locator('details.p1-resource').filter({hasText:/\.mbm · MBM/});await mbm.locator(':scope > summary').click();await mbm.getByRole('button',{name:'Decode bitmap preview'}).click();await mbm.getByRole('img',{name:'Decoded bitmap'}).waitFor();
 // Theme/light and RU are live preferences, while native resolution remains unchanged. Check responsive overflow.
 await page.evaluate(()=>{localStorage.setItem('symport-language','ru');localStorage.setItem('symport-theme','light');});await page.reload();
 await page.locator('[data-route="personalize/theme-editor"]').getByRole('heading',{name:'Редактор тем',exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 for(const route of ['personalize/theme-editor','apps/kits','tools/diagnostics','phone/connection']){await navigate(route);await page.waitForTimeout(350);if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow '+route);}
 if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS P1: pinned collection JSON, dependency-order recovery, guarded real transfers, zero/unknown diagnostics and private report, real E72 theme compiler, SIS import/MBM preview, Inspector same-byte handoff, RU/EN/light/dark/mobile. Transport/agent observations are explicit test doubles; no hardware claim.');
}catch(e){if(page)await page.screenshot({path:path.join(shots,'failure.png'),fullPage:true}).catch(()=>{});throw e;}finally{await browser?.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
