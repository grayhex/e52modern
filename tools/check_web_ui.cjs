const {chromium}=require('playwright');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const repo=path.resolve(__dirname,'..');
const python=process.env.SYMPORT_PYTHON||'python3';
const shots=process.env.SYMPORT_SCREENSHOTS_DIR||path.join(repo,'build','screenshots');
fs.mkdirSync(shots,{recursive:true});
(async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'symport-browser-'));
 for(const name of ['theme','tools','profiles'])fs.cpSync(path.join(repo,name),path.join(root,name),{recursive:true});
 const volume=path.join(root,'test-volume');fs.mkdirSync(volume);
 // Synthetic Gammu: answers `identify` and writes a tiny iCalendar for `backup <file>.ics -yes`. Not a phone.
 const bindir=path.join(root,'bin');fs.mkdirSync(bindir);
 const fake=path.join(bindir,'gammu');
 fs.writeFileSync(fake,[`#!/usr/bin/env ${python}`,'import sys',
  'a = sys.argv[1:]',
  "NL = chr(10)",
  "if a[2:3] == ['identify']:",
  "    print(NL.join(['Manufacturer : Nokia', 'Model        : E52 (RM-346)', 'Firmware     : synthetic']))",
  "elif a[2:3] == ['backup']:",
  "    open(a[3], 'w').write(NL.join(['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VEVENT', 'SUMMARY:Browser event', 'DTSTART:20300102T090000Z', 'LOCATION:Room 1', 'END:VEVENT', 'BEGIN:VTODO', 'SUMMARY:Browser todo', 'END:VTODO', 'END:VCALENDAR', '']))",
  'else:',
  '    sys.exit(2)',''].join('\n'));fs.chmodSync(fake,0o755);
 const server=spawn(python,['-m','symport.web','--repo',root,'--port','8771'],{env:{...process.env,PATH:bindir+path.delimiter+process.env.PATH,SYMPORT_DEVICE_ROOTS:JSON.stringify({'test-volume':volume}),SYMPORT_BRIDGE_URL:'',SYMPORT_GAMMU_CONFIG:path.join(root,'gammu.cfg'),SYMPORT_BACKUP_ROOT:path.join(root,'backup-store')},stdio:'ignore'});
 let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.SYMPORT_BROWSER_EXECUTABLE?{executablePath:process.env.SYMPORT_BROWSER_EXECUTABLE}:{}),args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(let i=0;i<30;i++){try{await page.goto('http://127.0.0.1:8771');break;}catch(e){await new Promise(r=>setTimeout(r,200));}}
  await page.locator('#manager.visible').waitFor();await page.evaluate(()=>document.fonts.ready);
  if(await page.locator('.nav-link .asset-icon').count()!==17)throw Error('Uploaded navigation icons missing');
  if(!await page.locator('.brand-lockup').evaluate(img=>img.complete&&img.naturalWidth>0))throw Error('Uploaded logo not loaded');
  await page.screenshot({path:path.join(shots,'workspace-desktop.png'),fullPage:true});
  await page.click('[data-nav="contacts"]');await page.locator('#contacts.visible').waitFor();
  await page.screenshot({path:path.join(shots,'contacts-desktop.png'),fullPage:true});
  await page.click('[data-nav="media"]');await page.locator('#media.visible').waitFor();
  await page.screenshot({path:path.join(shots,'media-desktop.png'),fullPage:true});
  await page.click('[data-nav="backups"]');await page.locator('#backups.visible').waitFor();
  await page.screenshot({path:path.join(shots,'backups-desktop.png'),fullPage:true});
  await page.click('[data-nav="calendar"]');await page.locator('#calendar.visible').waitFor();
  await page.screenshot({path:path.join(shots,'calendar-desktop.png'),fullPage:true});
  await page.click('[data-nav="themes"]');await page.locator('#themes.visible').waitFor();
  await page.screenshot({path:path.join(shots,'themes-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:8771/#contacts');await page.locator('#contacts.visible').waitFor();
  await page.screenshot({path:path.join(shots,'contacts-mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile horizontal overflow');
  await page.setViewportSize({width:1440,height:1100});
  const csv=path.join(root,'test-google.csv');fs.writeFileSync(csv,'Name,Phone 1 - Value,E-mail 1 - Value\nBrowser test,+123456789,test@example.test\n');
  await page.setInputFiles('#contacts-file',csv);await page.click('#contacts-preview');await page.locator('#contacts-workspace:not([hidden])').waitFor();
  if(await page.locator('#contacts-rows tr').count()!==1)throw Error('Contacts preview missing');
  await page.fill('#contacts-search','absent');if(await page.locator('#contacts-rows tr').count()!==0)throw Error('Search failed');await page.fill('#contacts-search','');
  const downloadPromise=page.waitForEvent('download');await page.click('#contacts-export');const download=await downloadPromise;if(download.suggestedFilename()!=='contacts.vcf')throw Error('Export filename');
  await page.click('#contacts .suite-discover');await page.waitForFunction(()=>!!document.querySelector('#contacts-device option[value="test-volume"]'));await page.selectOption('#contacts-device','test-volume');
  page.once('dialog',d=>d.accept());await page.click('#contacts-send');await page.waitForFunction(()=>document.getElementById('contacts-result').textContent.includes('Передано vCard: 1'));
  const folder=fs.readdirSync(volume).find(x=>x.startsWith('Contacts-import-'));if(!folder||!fs.readFileSync(path.join(volume,folder,'contact-0001.vcf'),'utf8').includes('Browser test'))throw Error('Contacts not transferred: ');
  const log=fs.readFileSync(path.join(root,'build/symport/device-manager/operations.jsonl'),'utf8');if(log.includes('Browser test')||log.includes('+123456789'))throw Error('Private contacts in journal');
  await page.click('[data-nav="media"]');const audio=path.join(root,'test.mp3');fs.writeFileSync(audio,'synthetic test bytes; not a playable codec fixture');await page.setInputFiles('#media-files',audio);page.once('dialog',d=>d.accept());await page.click('#media-send');await page.waitForFunction(()=>document.getElementById('media-result').textContent.includes('Передано файлов: 1'));
  if(fs.readFileSync(path.join(volume,'test.mp3'),'utf8')!==fs.readFileSync(audio,'utf8'))throw Error('Audio bytes changed');
  await page.click('[data-nav="installed"]');const jar=path.join(root,'test.jar');const result=spawnSync(python,['-c',"import zipfile,sys; z=zipfile.ZipFile(sys.argv[1],'w');z.writestr('Main.class',bytes.fromhex('cafebabe'));z.writestr('META-INF/MANIFEST.MF','MIDlet-Name: Test\\nMIDlet-Version: 1.0\\nMIDlet-Vendor: Test\\nMIDlet-1: Test,,Main\\n');z.close()",jar]);if(result.status!==0)throw Error(result.stderr.toString());await page.setInputFiles('#software-files',jar);page.once('dialog',d=>d.accept());await page.click('#software-send');await page.waitForFunction(()=>document.getElementById('software-result').textContent.includes('Передано пакетов: 1'));
  if(!fs.existsSync(path.join(volume,'test.jar')))throw Error('JAR transfer failed');
  await page.click('[data-nav="backups"]');await page.locator('#backups details.card > summary').click();
  const backupPromise=page.waitForEvent('download');await page.click('#dm-backup');const backup=await backupPromise;const archive=path.join(root,'backup.zip');await backup.saveAs(archive);
  await page.click('[data-nav="manager"]');await page.fill('#dm-dir','restored');page.once('dialog',d=>d.accept());await page.click('#dm-mkdir');await page.waitForFunction(()=>document.getElementById('dm-files').textContent.includes('restored'));
  await page.fill('#dm-path','restored');await page.click('[data-nav="backups"]');await page.setInputFiles('#dm-archive',archive);await page.click('#dm-preview');await page.waitForFunction(()=>!document.getElementById('dm-restore').disabled);page.once('dialog',d=>d.accept());await page.click('#dm-restore');await page.waitForFunction(()=>document.getElementById('dm-restore').disabled);
  if(!fs.existsSync(path.join(volume,'restored','test.mp3')))throw Error('Restore failed');

  // Full backup: create -> verify -> restore (plan, apply) -> delete, all through the UI
  await page.click('[data-nav="backups"]');await page.click('#backups .suite-discover');await page.waitForFunction(()=>!!document.getElementById('backup-device').value);
  page.once('dialog',d=>d.accept());await page.click('#backup-create');
  await page.waitForFunction(()=>document.getElementById('backup-status').textContent.includes('Копия создана'),null,{timeout:60000});
  if(await page.locator('#backup-rows tr').count()!==1)throw Error('Backup row missing');
  await page.locator('#backup-rows button',{hasText:'Проверить'}).click();
  await page.waitForFunction(()=>document.getElementById('backup-status').textContent.includes('Проверено'),null,{timeout:60000});
  fs.unlinkSync(path.join(volume,'test.jar'));
  await page.locator('#backup-rows button',{hasText:'Восстановить'}).click();
  await page.waitForFunction(()=>!!document.getElementById('restore-device').value);
  if(!await page.locator('#restore-apply').isDisabled())throw Error('Restore apply must wait for a plan');
  await page.click('#restore-plan');await page.waitForFunction(()=>document.getElementById('restore-result').textContent.includes('новых 1'),null,{timeout:60000});
  page.once('dialog',d=>d.accept());await page.click('#restore-apply');
  await page.waitForFunction(()=>document.getElementById('restore-result').textContent.includes('Записано 1'),null,{timeout:60000});
  if(!fs.existsSync(path.join(volume,'test.jar')))throw Error('Full restore did not recreate the deleted file');
  const store=path.join(root,'backup-store');if(JSON.stringify(await page.evaluate(()=>document.body.innerText)).includes(root))throw Error('Server path leaked into the page');
  page.once('dialog',d=>d.accept());await page.locator('#backup-rows button',{hasText:'Удалить'}).click();
  await page.waitForFunction(()=>document.querySelectorAll('#backup-rows tr').length===0);
  if(fs.readdirSync(store).some(x=>!x.startsWith('.')&&fs.statSync(path.join(store,x)).isDirectory()&&x!=='.progress'))throw Error('Backup directory not removed');

  // Calendar through the synthetic Gammu (read-only)
  await page.click('[data-nav="calendar"]');await page.click('#calendar .suite-discover');await page.waitForFunction(()=>!!document.getElementById('calendar-device').value);
  await page.click('#calendar-read');await page.waitForFunction(()=>document.querySelectorAll('#calendar-events tr').length===1);
  if(!(await page.locator('#calendar-events').innerText()).includes('Browser event'))throw Error('Calendar event missing');
  if(await page.locator('#calendar-todos tr').count()!==1)throw Error('Calendar to-do missing');
  await page.fill('#calendar-search','absent');if(await page.locator('#calendar-events tr').count()!==0)throw Error('Calendar search failed');await page.fill('#calendar-search','');
  const icsPromise=page.waitForEvent('download');await page.click('#calendar-ics');if((await icsPromise).suggestedFilename()!=='e52-calendar.ics')throw Error('ICS filename');
  await page.click('[data-nav="themes"]');
  const sis=path.join(root,'test-theme.sis');const generated=spawnSync(python,['-c',"from pathlib import Path; from symport.sis import writer; from tests.test_sis import pkg; import sys; Path(sys.argv[1]).write_bytes(writer.build(pkg()))",sis],{cwd:repo});if(generated.status!==0)throw Error(generated.stderr.toString());
  await page.setInputFiles('#library-upload',sis);await page.click('#library-import');await page.waitForFunction(()=>!document.getElementById('library-publish').disabled);page.once('dialog',d=>d.accept());await page.click('#library-publish');await page.locator('#library-items a').waitFor();
  const themeDownloadPromise=page.waitForEvent('download');await page.locator('#library-items a').click();const themeDownload=await themeDownloadPromise;if(themeDownload.suggestedFilename()!=='test-theme.sis')throw Error('Published download failed');
  // SIS inventory (files on the volume only)
  fs.copyFileSync(sis,path.join(volume,'inventory-test.sis'));
  await page.click('[data-nav="installed"]');await page.click('#installed .suite-discover');await page.waitForFunction(()=>!!document.getElementById('inventory-device').value);
  await page.click('#inventory-scan');await page.waitForFunction(()=>document.querySelectorAll('#inventory-rows tr').length>=1);
  if(!(await page.locator('#inventory-rows').innerText()).includes('inventory-test.sis'))throw Error('Inventory row missing');
  // Compact layout: pages stay close to one screen; no horizontal overflow on a phone-sized viewport
  await page.setViewportSize({width:1440,height:900});
  for(const id of ['manager','backups','calendar','installed','themes','contacts','media']){
    await page.evaluate(i=>{location.hash='#'+i},id);await page.locator('#'+id+'.visible').waitFor();
    const h=await page.evaluate(()=>document.documentElement.scrollHeight);
    if(h>900*1.3)throw Error(`Page ${id} is not compact: ${h}px at 900px viewport`);
  }
  await page.setViewportSize({width:390,height:844});
  for(const id of ['manager','backups','calendar','installed','themes','device']){
    await page.evaluate(i=>{location.hash='#'+i},id);await page.locator('#'+id+'.visible').waitFor();
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile horizontal overflow on '+id);
  }
  await page.setViewportSize({width:1440,height:1100});
  await page.click('[data-nav="contacts"]');await page.click('#contacts-clear');if(!await page.locator('#contacts-workspace').isHidden())throw Error('Clear contacts failed');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('Chromium passed (including theme publication, ZIP and full backup create/verify/restore/delete, synthetic-Gammu calendar, SIS inventory, compact layout): desktop/mobile, Google CSV preview/search/export, confirmed vCard staging, audio/JAR transfer, contact privacy and clear. Screenshots show empty states, not simulated hardware.');
 }finally{if(browser)await browser.close();server.kill();fs.rmSync(root,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1)});
