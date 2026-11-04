process.env.SYMPORT_FRONTEND = 'classic'; // Explicit rollback-interface regression coverage.
// Browser contract tests: genuine SDK certificate + mock phone volume, no phone jailbreak claim.
const {chromium}=require('playwright'),{spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-security-')),repo=path.resolve(__dirname,'..'),python=process.env.SYMPORT_PYTHON||'python3';
const shots=path.join(repo,'build/screenshots');fs.mkdirSync(shots,{recursive:true});
for(const name of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
const script=`import sys,os,json,base64
from pathlib import Path
from symport.web import main
from tests.test_security_workspace import archive_bytes
r=Path(sys.argv[1]);(r/'volume').mkdir();(r/'volume/original.txt').write_text('Keep this original file');(r/'fixture.zip').write_bytes(archive_bytes())
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'test-volume':str(r/'volume')}),SYMPORT_MGO_URL='',SYMPORT_MGO_TOKEN_FILE='',SYMPORT_BRIDGE_URL='',SYMPORT_GAMMU_CONFIG='')
main(['--repo',str(r),'--port','8776'])`;
const server=spawn(python,['-c',script,root],{cwd:repo,env:process.env,stdio:['ignore','ignore','inherit']});
async function checkSidebar(page){
 // Real long-page scrolling must keep the logo visible and the rail full-height.
 for(const height of [1100,600]){
  await page.setViewportSize({width:1440,height});
  await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
  const geometry=await page.evaluate(()=>{
   const rail=document.querySelector('.sidebar'),panel=document.querySelector('.sidebar-panel'),logo=document.querySelector('.brand-lockup'),main=document.querySelector('.main');
   return {railBottom:rail.getBoundingClientRect().bottom,mainBottom:main.getBoundingClientRect().bottom,panelTop:panel.getBoundingClientRect().top,panelHeight:panel.getBoundingClientRect().height,logoTop:logo.getBoundingClientRect().top,logoBottom:logo.getBoundingClientRect().bottom,height:innerHeight};
  });
  if(Math.abs(geometry.railBottom-geometry.mainBottom)>1||Math.abs(geometry.panelTop)>1||Math.abs(geometry.panelHeight-height)>1||geometry.logoTop<0||geometry.logoBottom>height)throw Error('Sidebar detached from document/viewport: '+JSON.stringify(geometry));
  await page.evaluate(()=>document.activeElement.blur());
  await page.locator('[data-nav="activity"]').focus();
  if(!await page.locator('[data-nav="activity"]').evaluate(n=>{const a=n.getBoundingClientRect(),b=n.closest('.sidebar-menu').getBoundingClientRect();return a.top>=b.top-1&&a.bottom<=b.bottom+1;}))throw Error('Last menu item inaccessible on short screen '+JSON.stringify(await page.locator('[data-nav="activity"]').evaluate(n=>({link:n.getBoundingClientRect().toJSON(),menu:n.closest('.sidebar-menu').getBoundingClientRect().toJSON(),scroll:n.closest('.sidebar-menu').scrollTop}))));
  if(height===600&&!await page.locator('.sidebar-menu').evaluate(n=>n.scrollTop>0))throw Error('Menu did not scroll independently');
 }
 await page.setViewportSize({width:1440,height:1100});
 await page.evaluate(()=>{document.activeElement.blur();document.querySelector('.sidebar-menu').scrollTop=0;window.scrollTo(0,0);});
}
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8776/#inspector');break;}catch{await new Promise(r=>setTimeout(r,200));}}
 await page.waitForFunction(()=>Object.keys(uiTranslations.en).length>100);await page.selectOption('#ui-language','en');await page.selectOption('#ui-theme','dark');await page.waitForFunction(()=>document.documentElement.lang==='en'&&document.documentElement.dataset.theme==='dark');
 await page.reload();await page.waitForFunction(()=>document.documentElement.lang==='en'&&document.documentElement.dataset.theme==='dark');
 if(await page.evaluate(()=>tr('Удалить Контакты.sis? Каталог должен быть пустым.'))!=='Delete Контакты.sis? The directory must be empty.')throw Error('Dialog translation changed filename or kept Russian UI');
 // Surface untranslated UI text for review. User content and raw evidence are intentionally excluded.
 const untranslated={};for(const id of ['manager','updates','contacts','calendar','messages','media','backups','catalog','installed','themes','apps','device','overview','activity','lab','inspector','jailbreak']){
  await page.evaluate(id=>location.hash='#'+id,id);await page.locator('#'+id+'.visible').waitFor();await page.waitForTimeout(80);
  const text=await page.locator('#'+id).evaluate(element=>{const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT),out=[];while(walker.nextNode()){const n=walker.currentNode;if(!n.parentElement.closest('pre,code,svg,script,[data-i18n-skip]')&&/[А-Яа-яЁё]/.test(n.nodeValue))out.push(n.nodeValue.trim());}return out.filter(Boolean);});if(text.length)untranslated[id]=text;
 }
 fs.writeFileSync(path.join(shots,'translation-review.json'),JSON.stringify(untranslated,null,2));
 await page.goto('http://127.0.0.1:8776/#inspector');await page.setInputFiles('#inspect-file',path.join(repo,'tests/fixtures/sdk_probe_package_signed.sis'));await page.click('#inspect-analyze');await page.waitForFunction(()=>!document.getElementById('inspect-result').hidden);
 if(!(await page.locator('#inspect-json').textContent()).includes('CN=SymPort test only'))throw Error('Public certificate missing');
 if(!await page.locator('#inspect-json').evaluate(n=>JSON.parse(n.textContent).signatures.status==='valid'))throw Error('Genuine SDK signature not verified');
 await page.fill('#inspect-message','expired certificate');await page.click('#inspect-diagnose');await page.waitForFunction(()=>document.getElementById('inspect-advice').textContent.includes('expired-certificate'));
 await checkSidebar(page);
 await page.screenshot({path:path.join(shots,'inspector-dark-en.png'),fullPage:true});
 await page.click('[data-nav="jailbreak"]');await page.setInputFiles('#jb-archive',path.join(root,'fixture.zip'));await page.click('#jb-import');await page.waitForFunction(()=>document.querySelectorAll('#jb-files input').length===4);
 if(await page.locator('#jb-files input:disabled').count()!==2)throw Error('Key or wrong-model patch can be selected');
 await page.locator('#jb-files input:not(:disabled)').first().check();await page.click('#jailbreak .suite-discover');await page.waitForFunction(()=>!!document.getElementById('jb-device').value);
 await page.fill('#jb-model','Nokia E52');await page.fill('#jb-rm','RM-469');await page.fill('#jb-firmware','unknown');await page.click('#jb-plan');await page.locator('#jb-workflow:not([hidden])').waitFor();
 if(!JSON.parse(await page.locator('#jb-json').textContent()).dry_run)throw Error('Plan not dry run');
 page.once('dialog',d=>d.accept());await page.click('#jb-backup');await page.waitForFunction(()=>JSON.parse(document.getElementById('jb-json').textContent).backup!==null);
 page.once('dialog',d=>d.accept());await page.click('#jb-stage');await page.waitForFunction(()=>JSON.parse(document.getElementById('jb-json').textContent).staged.length===1);
 const run=JSON.parse(await page.locator('#jb-json').textContent()),staged=path.join(root,'volume',run.staged[0].path);if(!fs.existsSync(staged))throw Error('Staging did not copy bytes');if(run.installation!=='not-tested')throw Error('False installation claim');
 await page.click('#jb-rollback-plan');await page.waitForFunction(()=>!document.getElementById('jb-rollback').disabled);page.once('dialog',d=>d.accept());await page.click('#jb-rollback');await page.waitForFunction(()=>!!JSON.parse(document.getElementById('jb-json').textContent).rollback);
 if(fs.existsSync(staged)||!fs.existsSync(path.join(root,'volume/original.txt')))throw Error('Rollback failed or removed original data');
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'jailbreak-dark-en.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});for(const id of ['inspector','jailbreak','manager','contacts','lab']){await page.evaluate(id=>location.hash='#'+id,id);await page.locator('#'+id+'.visible').waitFor();if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)){await page.screenshot({path:path.join(shots,'security-overflow.png'),fullPage:true});throw Error('Mobile overflow '+id+' '+JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('.page.visible *')].map(n=>({id:n.id,tag:n.tagName,cls:n.className,right:n.getBoundingClientRect().right,width:n.getBoundingClientRect().width})).filter(n=>n.right>innerWidth+1).slice(0,20))));}}
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(shots,'workspace-dark-mobile.png'),fullPage:true});
 await page.selectOption('#ui-language','ru');await page.waitForFunction(()=>document.documentElement.lang==='ru');await page.selectOption('#ui-theme','light');if(await page.locator('#ui-theme').inputValue()!=='light')throw Error('Theme switch failed');
 await page.goto('http://127.0.0.1:8776/#inspector');await page.locator('#inspector.visible').waitFor();await checkSidebar(page);
 if(errors.length)throw Error(errors.join('\n'));if(Object.keys(untranslated).length)throw Error('Untranslated interface text: '+JSON.stringify(untranslated));
 console.log('PASS: genuine signature, diagnosis, archive/key exclusions, dry-run, backup, staged bytes/rollback, English/Russian persistence, Nimbus dark/light and responsive UI. No system patch or hardware installation claimed.');
 }finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
