// Browser -> SymPort -> authenticated mock MGO contract -> persistent reports -> mounted test volume.
// Synthetic success pipeline only; this does not test an E52 ROM or EKA2L1 compatibility.
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),crypto=require('crypto');
const repo=path.resolve(__dirname,'..'),python=process.env.SYMPORT_PYTHON||'python3';
const shots=process.env.SYMPORT_SCREENSHOTS_DIR||path.join(repo,'build','screenshots');fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-lab-browser-'));
 for(const name of ['theme','tools','profiles'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
 const script=`import sys,os,json,hashlib,base64
from pathlib import Path
from tests.lab_fixture import MockMgo,serve_mock,sis,TOKEN
from tests.test_catalog import catalog_fixture,artifact
from symport.web import main
from symport.catalog.service import save
root=Path(sys.argv[1]); (root/'volume').mkdir(); (root/'firmware.rom').write_bytes(b'TEST ONLY NOT A ROM'); (root/'app.sis').write_bytes(sis()); (root/'theme.sis').write_bytes(sis(True)); (root/'game.jar').write_bytes(b'TEST ONLY')
(root/'build/symport/theme/light').mkdir(parents=True); (root/'build/symport/theme/light/fixture-theme.sis').write_bytes(sis(True))
project=root/'workspace/Fixture';(project/'.symbian/package').mkdir(parents=True);(project/'symbian.toml').write_text('');(project/'.symbian/package/fixture-app.sis').write_bytes(sis())
catalog_fixture(root); entry=root/'catalog/apps/example.json'; data=json.loads(entry.read_text());data.update(name='Lab contract game fixture',format='sis',dependencies=[],category='games');entry.write_text(json.dumps(data));sources=json.loads((root/'catalog/sources.json').read_text());a=artifact(sis(),'fixture-game.sis');sources['example']={'artifacts':[a]};(root/'catalog/sources.json').write_text(json.dumps(sources));cache=root/'build/symport/app-catalog/cache'/a['sha256'];cache.mkdir(parents=True);(cache/a['name']).write_bytes(sis())
agent=MockMgo(installed=False); original=agent.request
def record(*args,**kwargs):
 result=original(*args,**kwargs);save(root/'calls.json',agent.calls);return result
agent.request=record
server=serve_mock(agent,8774);os.environ.update(SYMPORT_MGO_URL='http://127.0.0.1:8774',SYMPORT_MGO_TOKEN=TOKEN,SYMPORT_MGO_TOKEN_FILE='',SYMPORT_DEVICE_ROOTS=json.dumps({'test-volume':str(root/'volume')}),SYMPORT_GAMMU_CONFIG='',SYMPORT_BRIDGE_URL='')
main(['--repo',str(root),'--port','8773'])`;
 const server=spawn(python,['-c',script,root],{cwd:repo,env:process.env,stdio:['ignore','ignore','inherit']});let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(let i=0;i<40;i++){try{await page.goto('http://127.0.0.1:8773/#lab');break;}catch(e){await new Promise(r=>setTimeout(r,200));}}
  await page.locator('#lab.visible').waitFor();await page.waitForFunction(()=>document.getElementById('lab-status').textContent.includes('CONTRACT DOUBLE'));await page.evaluate(()=>document.fonts.ready);
  if(!await page.locator('#lab-start').isDisabled())throw Error('Start allowed without firmware');
  await page.setInputFiles('#lab-rom',path.join(root,'firmware.rom'));await page.click('#lab-upload-firmware');await page.waitForFunction(()=>!document.getElementById('lab-install-firmware').disabled);
  page.once('dialog',d=>d.accept());await page.click('#lab-install-firmware');await page.waitForFunction(()=>document.querySelector('#lab-reports .status.installed'),null,{timeout:15000});
  await page.waitForFunction(()=>[...document.getElementById('lab-device').options].some(o=>o.value==='mock-device'));await page.selectOption('#lab-device','mock-device');await page.waitForFunction(()=>!document.getElementById('lab-start').disabled);await page.click('#lab-start');await page.locator('#lab-screen:not([hidden])').waitFor();
  await page.locator('#lab-controls').focus();await page.keyboard.press('F3');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');await page.evaluate(async()=>{await labInput;});
  await page.locator('.lab-e52-body').waitFor();
  if(!await page.locator('.lab-e52-mail').isDisabled())throw Error('Unsupported Mail key enabled');
  // A pointer and keyboard can hold the same physical key without an early up.
  await page.locator('#lab-controls').focus();await page.keyboard.down('ArrowLeft');
  const keyBox=await page.locator('.lab-e52-left').boundingBox();await page.mouse.move(keyBox.x+keyBox.width/2,keyBox.y+keyBox.height/2);await page.mouse.down();await page.keyboard.up('ArrowLeft');await page.evaluate(async()=>{await labInput;});
  const held=JSON.parse(fs.readFileSync(path.join(root,'calls.json'),'utf8')).filter(c=>c[1]==='/v1/input/key'&&c[2].key==='left');if(!held.length||held.at(-1)[2].action!=='down')throw Error('Shared key released too early');
  await page.mouse.up();await page.evaluate(async()=>{await labInput;});
  const released=JSON.parse(fs.readFileSync(path.join(root,'calls.json'),'utf8')).filter(c=>c[1]==='/v1/input/key'&&c[2].key==='left');if(!released.length||released.at(-1)[2].action!=='up')throw Error('Pointer key stuck');
  const calls=JSON.parse(fs.readFileSync(path.join(root,'calls.json'),'utf8'));if(!calls.some(([m,p,b])=>p==='/v1/input/key'&&b.key==='applications'&&b.action==='down'))throw Error('Menu key did not reach agent');
  await page.selectOption('#lab-source','upload');await page.setInputFiles('#lab-package',path.join(root,'app.sis'));page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>document.querySelector('#lab-reports .status.launched'),null,{timeout:15000});
  await page.waitForFunction(()=>document.getElementById('lab-report-summary').textContent.includes('launched'));await page.click('#lab-shot');await page.waitForFunction(()=>document.querySelectorAll('#lab-report-shots img').length===2);
  const exported=page.waitForEvent('download');await page.click('#lab-report-export');const file=await exported;const reportFile=path.join(root,'report.json');await file.saveAs(reportFile);const report=JSON.parse(fs.readFileSync(reportFile,'utf8'));if(report.package.sha256!==crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'app.sis'))).digest('hex')||report.physical_device!=='not-tested')throw Error('Report integrity');
  await page.click('#lab-transfer-panel .suite-discover');await page.waitForFunction(()=>!!document.getElementById('lab-phone').value);page.once('dialog',d=>d.accept());await page.click('#lab-transfer');await page.waitForFunction(()=>document.getElementById('lab-transfer-result').textContent.includes('передан'));
  if(!fs.readFileSync(path.join(root,'volume','app.sis')).equals(fs.readFileSync(path.join(root,'app.sis'))))throw Error('Transferred bytes differ');
  // Build/theme link selects the theme workflow and never calls the launch UID endpoint.
  await page.goto('http://127.0.0.1:8773/#themes');await page.locator('#theme-packages button',{hasText:'Проверить в эмуляторе'}).click();await page.waitForFunction(()=>document.getElementById('lab-kind').value==='theme');
  const before=JSON.parse(fs.readFileSync(path.join(root,'calls.json'),'utf8')).filter(c=>c[1].endsWith('/launch')).length;
  page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>!document.getElementById('lab-theme-review').hidden&&document.getElementById('lab-report-summary').textContent.includes('installed'),null,{timeout:15000});await page.waitForFunction(()=>!document.getElementById('lab-observe').disabled);await page.click('#lab-observe');await page.waitForFunction(()=>document.getElementById('lab-report-summary').textContent.includes('Наблюдения пользователя'));
  const after=JSON.parse(fs.readFileSync(path.join(root,'calls.json'),'utf8')).filter(c=>c[1].endsWith('/launch')).length;if(after!==before)throw Error('Theme UID was launched');
  // Local theme library and own app builds have working entry points.
  await page.goto('http://127.0.0.1:8773/#themes');await page.setInputFiles('#library-upload',path.join(root,'theme.sis'));await page.click('#library-import');await page.waitForFunction(()=>!document.getElementById('library-publish').disabled);page.once('dialog',d=>d.accept());await page.click('#library-publish');await page.locator('#library-items button',{hasText:'Проверить в эмуляторе'}).click();if(await page.locator('#lab-source').inputValue()!=='library')throw Error('Library entry point');
  page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>document.getElementById('lab-report-title').textContent==='theme.sis'&&document.getElementById('lab-report-summary').textContent.includes('installed'),null,{timeout:15000});
  await page.goto('http://127.0.0.1:8773/#apps');await page.locator('#app-packages button',{hasText:'Проверить в эмуляторе'}).click();page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>document.getElementById('lab-report-title').textContent==='fixture-app.sis'&&document.getElementById('lab-report-summary').textContent.includes('launched'),null,{timeout:15000});
  // Catalog game -> approved cached bytes -> install and launch.
  await page.goto('http://127.0.0.1:8773/#catalog');await page.fill('#catalog-query','Lab contract game fixture');await page.locator('.catalog-app button',{hasText:'Проверить в эмуляторе'}).click();page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>document.getElementById('lab-report-title').textContent==='fixture-game.sis'&&document.getElementById('lab-report-summary').textContent.includes('launched'),null,{timeout:15000});
  await page.screenshot({path:path.join(shots,'emulator-lab-contract-desktop.png'),fullPage:true});
  await page.selectOption('#lab-source','upload');await page.setInputFiles('#lab-package',path.join(root,'game.jar'));page.once('dialog',d=>d.accept());await page.click('#lab-test');await page.waitForFunction(()=>document.getElementById('lab-report-title').textContent==='game.jar'&&document.getElementById('lab-report-summary').textContent.includes('unsupported'),null,{timeout:15000});if(!await page.locator('#lab-transfer-panel').isHidden())throw Error('Java passed as Symbian test');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(shots,'emulator-lab-contract-mobile.png'),fullPage:true});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Lab mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));console.log('Emulator Lab browser contract PASS: firmware stream, control, app/theme/build/library/catalog, evidence, SHA-256, phone transfer, Java unsupported. No hardware/ROM compatibility claim.');
 }finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
