// Real browser -> local pairing -> outbound relay -> shared filesystem adapter.
// Native confirmation is injected only in this isolated no-phone test process.
const {chromium}=require('playwright'),{spawn}=require('child_process'),fs=require('fs'),os=require('os'),path=require('path');
const repo=path.resolve(__dirname,'..'),root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-bridge-ui-')),python=process.env.SYMPORT_PYTHON||'python3';
for(const name of ['theme','tools','profiles','catalog'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
const script=`import sys,os,json,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench,make_handler
from symport.bridge.main import Agent
r=Path(sys.argv[1]);v=r/'enrolled';v.mkdir();(v/'hello.txt').write_text('actual filesystem bytes')
os.environ.update(SYMPORT_BRIDGE_URL='',SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_DEVICE_ROOTS='{}')
w=Workbench(r);srv=ThreadingHTTPServer(('127.0.0.1',8777),make_handler(w));threading.Thread(target=srv.serve_forever,daemon=True).start()
a=r/'agent';a.mkdir();(a/'settings.json').write_text(json.dumps({'schema':1,'auto_usb':False,'volumes':{'enrolled-folder':str(v)}}));agent=Agent(a,'x'*32,port=24652,approve=lambda data: True,auto=False);agent.start()
threading.Event().wait()
`;
const server=spawn(python,['-c',script,root],{cwd:repo,env:process.env,stdio:['ignore','ignore','inherit']});
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8777');break;}catch{await new Promise(r=>setTimeout(r,200));}}
 await page.waitForFunction(()=>Object.keys(uiTranslations.en).length>100);await page.selectOption('#ui-language','en');await page.selectOption('#ui-theme','dark');await page.click('[data-nav="connection"]');
 await page.click('#connection-pair');await page.waitForFunction(()=>document.getElementById('connection-result').textContent.includes('granted'));await page.click('#connection-find');await page.waitForFunction(()=>dmDevices.some(d=>d.id==='enrolled-folder'));
 const result=await page.evaluate(async()=>await dmCall({action:'download',device:'enrolled-folder',path:'hello.txt'}));if(atob(result.content)!=='actual filesystem bytes')throw Error('Outbound relay byte roundtrip failed');
 const write=await page.evaluate(async()=>await dmCall({action:'upload',device:'enrolled-folder',path:'new.txt',content:btoa('new bytes'),confirm:true}));if(fs.readFileSync(path.join(root,'enrolled/new.txt'),'utf8')!=='new bytes')throw Error('Relay write failed');
 await page.click('#connection-status');await page.waitForFunction(()=>document.getElementById('connection-badge').textContent==='Connected');
 const shots=path.join(repo,'build/screenshots');fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,'windows-bridge-dark-en.png'),fullPage:true,animations:'disabled'});
 await page.selectOption('#ui-language','ru');await page.selectOption('#ui-theme','light');await page.screenshot({path:path.join(shots,'windows-bridge-light-ru.png'),fullPage:true,animations:'disabled'});
 await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Connection page mobile overflow');
 await page.click('#connection-disconnect');await page.waitForFunction(()=>dmDevices.length===0);const status=await page.evaluate(()=>request('POST','/api/connection',{action:'status'}));if(status.mode!=='direct')throw Error('Revoke failed');
 if(errors.length)throw Error(errors.join('\n'));console.log('PASS: browser pairing, outbound HTTP relay, actual enrolled-folder read/write, revoke, RU/EN, dark/light and mobile. No physical phone; native approval is a test callback.');
}finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
