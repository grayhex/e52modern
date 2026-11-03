// Real browser -> SymPort -> pinned MGO/EKA2L1. Fresh disposable service only, no ROM.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
const shots=process.env.SYMPORT_SCREENSHOTS_DIR||path.resolve(__dirname,'../build/screenshots');fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Europe/Moscow'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let loaded=false;for(let i=0;i<50;i++){try{await page.goto('http://127.0.0.1:8775/#lab');loaded=true;break;}catch(e){await new Promise(r=>setTimeout(r,200));}}if(!loaded)throw Error('Runtime UI unavailable');
  await page.waitForFunction(()=>document.getElementById('lab-status').textContent.includes('EKA2L1 master-'),null,{timeout:45000});await page.evaluate(()=>document.fonts.ready);
  const state=await page.evaluate(()=>labApi({action:'state'}));if(state.health.firmware.devices.length)throw Error('Refusing negative test on user firmware');
  if(!await page.locator('#lab-start').isDisabled())throw Error('Start available without firmware');
  if(await page.locator('.nav-link .asset-icon').count()!==18)throw Error('Supplied navigation graphics not integrated');
  if(!await page.locator('.brand-lockup').evaluate(img=>img.complete&&img.naturalWidth>0))throw Error('Logo missing');
  if(!await page.locator('.lab-e52-body').evaluate(img=>img.complete&&img.naturalWidth===831))throw Error('Silver E52 body missing');
  await page.screenshot({path:path.join(shots,'emulator-lab-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(shots,'emulator-lab-mobile.png'),fullPage:true});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
  await page.setViewportSize({width:1440,height:1100});
  await page.selectOption('#lab-format','vpl');
  await page.setInputFiles('#lab-factory',[{name:'synthetic.vpl',mimeType:'application/octet-stream',buffer:Buffer.from('<not-a-vpl/>')},{name:'synthetic.fpsx',mimeType:'application/octet-stream',buffer:Buffer.from('INVALID TEST DATA')}]);
  await page.click('#lab-upload-firmware');await page.waitForFunction(()=>!document.getElementById('lab-install-firmware').disabled);
  page.once('dialog',d=>d.accept());await page.click('#lab-install-firmware');
  await page.waitForFunction(()=>document.querySelector('#lab-reports .status.failed'),null,{timeout:150000});
  await page.waitForFunction(()=>!document.getElementById('lab-report').hidden&&document.getElementById('lab-report-summary').textContent.includes('failed'));
  const report=await page.evaluate(async()=>{const s=await labApi({action:'state'});return labApi({action:'report',id:s.reports[0].id});});
  if(report.install!=='failed'||report.agent_job?.errorCode!=='vpl_invalid'||report.physical_device!=='not-tested')throw Error('Real installer failure was not preserved: '+JSON.stringify(report));
  if(report.screenshots.length)throw Error('Fabricated screen without firmware');
  const after=await page.evaluate(()=>labApi({action:'state'}));if(after.health.firmware.devices.length)throw Error('Invalid manifest unexpectedly installed firmware');
  fs.writeFileSync(path.join(shots,'emulator-runtime-negative.json'),JSON.stringify({engine:after.health.emulator,install:report.install,launch:report.launch,errorCode:report.agent_job.errorCode,physical_device:report.physical_device,screenshots:report.screenshots.length,firmware_devices:after.health.firmware.devices.length},null,2));
  await page.screenshot({path:path.join(shots,'emulator-lab-firmware-error.png'),fullPage:true});
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS real browser/SymPort/MGO/EKA2L1: graphics, no-ROM disabled state, VPL/FPSX upload, real vpl_invalid, persistent report, no fake screenshot. Successful E52 boot remains not-tested.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
