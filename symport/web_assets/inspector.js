"use strict";
const ix=id=>document.getElementById('inspect-'+id),jb=id=>document.getElementById('jb-'+id);
const inspectApi=data=>request('POST','/api/inspector',data),jbApi=data=>request('POST','/api/jailbreak',data);
let inspected=null,inspectionExtra={},unlockState={},unlockRun=null;
async function securityDo(fn){try{await fn();}catch(e){notify(e.message);(location.hash==='#jailbreak'?jb('status'):ix('status')).textContent=e.message;}}
function inspectSources(){
 const previous=ix('reference').value,source=ix('source').value;ix('file').hidden=source!=='upload';ix('reference').hidden=['upload','device'].includes(source);
 const list=source==='build'?state.packages:source==='library'?(state.library||[]):source==='catalog'?catState.apps.filter(a=>a.delivery==='automatic'):[];
 ix('reference').replaceChildren(...list.map(p=>new Option(p.name,p.id)));if(list.some(p=>p.id===previous))ix('reference').value=previous;
}
function inspectChoose(source,reference,file,device,path){
 if(source==='lab'){inspectionExtra={source,reference};ix('source').value='upload';}
 else{inspectionExtra={};ix('source').value=source;}
 inspectSources();if(reference&&source!=='lab')ix('reference').value=reference;if(file)ix('file').files=file;
 if(device)ix('device').value=device;if(path)ix('path').value=path;location.hash='#inspector';
}
ix('source').onchange=()=>{inspectionExtra={};inspectSources();};
function inspectRender(report){
 inspected=report;ix('result').hidden=false;ix('status').textContent=report.name+' · '+report.compatibility+' · '+report.signatures.status;
 const facts=ix('facts');facts.replaceChildren();const dl=el('dl','device-details');
 for(const [k,v] of Object.entries({UID:'0x'+report.package.uid.toString(16),Version:report.package.version.join('.'),Publisher:report.package.vendor_names.join(', '),Signature:report.signatures.status,Trust:report.signatures.trust,Compatibility:report.compatibility,Capabilities:report.capabilities.join(', ')||'No capabilities declared',SHA256:report.sha256}))dl.append(el('dt','muted',k),el('dd','lab-value',v));facts.append(dl);
 ix('issues').replaceChildren();for(const [code,items] of Object.entries(report.recommendations)){const box=el('div','note');box.append(el('strong','',code));for(const advice of items)box.append(el('p','',advice));ix('issues').append(box);}
 ix('json').textContent=JSON.stringify(report,null,2);ix('destination').value=report.name;
 securityDo(async()=>{const s=await labApi({action:'state'});ix('emulator').replaceChildren(new Option('Select installed firmware',''),...(s.health?.firmware?.devices||[]).map(d=>new Option(d.model+' · '+d.code,d.code)));if(s.health?.defaults?.symbian)ix('emulator').value=s.health.defaults.symbian;});
}
ix('analyze').onclick=()=>securityDo(async()=>{
 const data={action:'analyze',source:ix('source').value,reference:ix('reference').value,device:ix('device').value,path:ix('path').value,...inspectionExtra,target:{model:ix('model').value,rm:ix('rm').value,firmware:ix('firmware').value,os:ix('os').value}};
 if(data.source==='upload'){const file=ix('file').files[0];if(!file||file.size>32*1024**2)throw Error('Choose a SIS/SISX up to 32 MiB');data.name=file.name;data.content=await readFileBase64(file);}
 if(ix('date').value)data.at=ix('date').value;const profile=ix('profile').files[0];if(profile){if(profile.size>1024**2)throw Error('Firmware profile exceeds 1 MiB');data.firmware_profile=JSON.parse(await profile.text());}
 inspectRender(await inspectApi(data));
});
ix('history').onclick=()=>securityDo(async()=>{const s=await inspectApi({action:'list'});ix('reports').replaceChildren();for(const r of s.reports){const b=el('button','btn ghost',r.name+' · '+r.compatibility);b.onclick=()=>inspectRender(r);ix('reports').append(b);}});
ix('export').onclick=()=>{if(inspected)saveBase64(btoa(unescape(encodeURIComponent(JSON.stringify(inspected,null,2)))),'certificate-inspection.json','application/json');};
ix('emulate').onclick=()=>securityDo(async()=>{if(!inspected||!ix('emulator').value)throw Error('Choose an installed emulator firmware');if(!confirm(tr('Install these inspected bytes in the emulator? This does not verify the physical phone.')))return;const r=await inspectApi({action:'emulate',id:inspected.id,code:ix('emulator').value,confirm:true});location.hash='#lab';await labShowReport(r,true);});
ix('transfer').onclick=()=>securityDo(async()=>{if(!inspected)throw Error('Analyze a package first');if(!confirm(tr('Transfer the inspected package? Installation must be completed on the phone.')))return;const r=await inspectApi({action:'transfer',id:inspected.id,device:ix('device').value,path:ix('destination').value,confirm:true,ack_unverified:ix('ack').checked});ix('status').textContent=r.status;});
ix('diagnose').onclick=()=>securityDo(async()=>{const r=await inspectApi({action:'diagnose',message:ix('message').value});ix('advice').replaceChildren(el('strong','',r.code),...r.recommendations.map(s=>el('p','note',s)));});
async function jbRefresh(){unlockState=await jbApi({action:'state'});const selected=jb('archives').value;jb('archives').replaceChildren(...unlockState.archives.map(a=>new Option(a.name+' · '+a.sha256.slice(0,12),a.id)));if(unlockState.archives.some(a=>a.id===selected))jb('archives').value=selected;jbFiles();jb('history').replaceChildren();for(const run of unlockState.runs){const b=el('button','btn ghost',run.identity.model+' · '+run.method+' · '+run.created);b.onclick=()=>jbRender(run);jb('history').append(b);}}
function jbFiles(){const a=unlockState.archives?.find(a=>a.id===jb('archives').value);jb('files').replaceChildren();for(const f of a?.entries||[]){const label=el('label','lab-upload-entry');const check=el('input');check.type='checkbox';check.value=f.sha256||'';check.disabled=!!f.excluded||f.analysis?.signature==='invalid'||f.e52==='incompatible-target-claim'||!['sis','patch','binary'].includes(f.kind);label.append(check,el('span','',f.name+' · '+(f.excluded||f.e52)+(f.analysis?.signature?' · signature: '+f.analysis.signature:'')+' · '+(f.sha256?.slice(0,12)||'')));jb('files').append(label);}}
function jbRender(run){unlockRun=run;jb('workflow').hidden=false;jb('summary').replaceChildren(el('p','note',run.rollback_scope),...run.blocking_reasons.map(s=>el('p','error-text',s)));jb('steps').replaceChildren(...run.manual_steps.map((s,i)=>el('p','',String(i+1)+'. '+s)));jb('json').textContent=JSON.stringify(run,null,2);jb('rollback').disabled=true;}
jb('archives').onchange=jbFiles;
jb('import').onclick=()=>securityDo(async()=>{const file=jb('archive').files[0];if(!file||file.size>16*1024**2)throw Error('Choose a ZIP up to 16 MiB');const r=await jbApi({action:'import',name:file.name,content:await readFileBase64(file)});await jbRefresh();jb('archives').value=r.id;jbFiles();jb('status').textContent='Archive inspected. Executables were not run; keys excluded.';});
jb('identify').onclick=()=>securityDo(async()=>{const s=await dmCall({action:'discover'});const d=s.devices.find(d=>d.id===jb('device').value);if(!d)throw Error('Select a connected device');jb('model').value=d.model||'';jb('rm').value=d.rm||'';jb('firmware').value=d.firmware||'';jb('status').textContent=d.evidence||'Mounted volume does not identify model or firmware. Record identity from the phone.';});
jb('plan').onclick=()=>securityDo(async()=>{const r=await jbApi({action:'plan',method:jb('method').value,archive:jb('archives').value,device:jb('device').value,model:jb('model').value,rm:jb('rm').value,firmware:jb('firmware').value,symbian:jb('symbian').value,settings:jb('settings').value,files:[...jb('files').querySelectorAll('input:checked')].map(c=>c.value)});jbRender(r);await jbRefresh();});
for(const action of ['backup','stage','manual-step','rollback']){
 const id={'manual-step':'observe'}[action]||action;
 jb(id).onclick=()=>securityDo(async()=>{if(!unlockRun)throw Error('Create a dry-run plan first');if(!confirm(tr(action==='stage'?'Stage unverified files? This only copies them to an isolated folder; it does not install or apply patches.':action==='rollback'?'Remove only unchanged files created by this workflow? System changes cannot be rolled back automatically.':action==='manual-step'?'Record a manual phone action? You are responsible for the separately confirmed system change.':'Back up accessible regular files? This is a partial data backup, not system recovery.')))return;
 const extra=action==='manual-step'?{step:jb('step').value,result:jb('observation').value,confirm_system:true}:action==='stage'?{ack_risk:true}:{};
 jbRender(await jbApi({action,id:unlockRun.id,confirm:true,...extra}));jb('status').textContent='Operation recorded. Review the report.';});
}
jb('backup-export').onclick=()=>securityDo(async()=>{const r=await jbApi({action:'backup-export',id:unlockRun?.id});saveBase64(r.content,r.name,'application/zip');});
jb('probe').onclick=()=>securityDo(async()=>{const r=await jbApi({action:'probe',id:unlockRun?.id});saveBase64(r.content,r.name,'application/vnd.symbian.install');notify(r.scope);});
jb('rollback-plan').onclick=()=>securityDo(async()=>{const r=await jbApi({action:'rollback-plan',id:unlockRun?.id});jb('rollback-preview').textContent=JSON.stringify(r,null,2);jb('rollback').disabled=false;});
jb('export').onclick=()=>{if(unlockRun)saveBase64(btoa(unescape(encodeURIComponent(JSON.stringify(unlockRun,null,2)))),'symport-experimental-workflow.json','application/json');};
window.addEventListener('hashchange',()=>{if(location.hash==='#inspector')inspectSources();if(location.hash==='#jailbreak')securityDo(jbRefresh);});

lab('inspect').onclick=()=>{if(labReport?.package)inspectChoose('lab',labReport.id);else notify('Choose a package test report');};
