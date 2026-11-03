"use strict";
const connection=id=>document.getElementById('connection-'+id);
let connectionBusy=false;
async function connectionStatus(){const s=await request('POST','/api/connection',{action:'status'});connection('badge').textContent=tr(s.mode==='direct'?'Local transports':s.connected?'Connected':'Disconnected');connection('badge').classList.toggle('success',!!s.connected);return s;}
async function connectionAction(fn){if(connectionBusy)return;connectionBusy=true;connection('pair').disabled=true;try{await fn();}catch(error){connection('result').textContent=error.message;notify(error.message);}finally{connectionBusy=false;connection('pair').disabled=false;await connectionStatus();}}
connection('status').onclick=()=>connectionAction(connectionStatus);
connection('pair').onclick=()=>connectionAction(async()=>{
 connection('result').textContent=tr('Approve access in the Windows Bridge window.');
 const lease=await request('POST','/api/connection',{action:'enable'});
 try{
  const r=await fetch('http://127.0.0.1:24652/api/bridge/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({origin:location.origin,token:lease.relay_token}),credentials:'omit',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(90000)});
  const result=await r.json();if(!r.ok||!result.paired)throw Error(result.error||tr('Access was declined.'));
  connection('result').textContent=tr('Bridge access granted. Connect your phone and choose Find phone.');
 }catch(error){await request('POST','/api/connection',{action:'disconnect'});throw Error(tr('Could not connect to Bridge. Start SymPortBridge.exe, allow local network access in the browser and approve the Windows confirmation.')+' '+error.message);}
});
for(const id of ['disconnect','direct'])connection(id).onclick=()=>connectionAction(async()=>{await request('POST','/api/connection',{action:'disconnect'});dmDevices=[];dmSelection();connection('result').textContent=tr('Bridge access revoked. Local SymPort transports are selected.');});
for(const id of ['find','refresh'])connection(id).onclick=()=>dm('discover').click();
function connectionDiagnostics(devices){const root=connection('list');root.replaceChildren();for(const d of devices){const card=el('div','card');const row=el('div','card-head');row.append(el('strong','',d.name||d.id),el('span','chip',tr(d.connected?'Connected':d.configured?'Configured':'Disconnected')));card.append(row,el('p','',d.connection_kind||d.transport),el('p','note',d.evidence||''));const caps=el('div','form-row');for(const cap of d.capabilities||[])caps.append(el('span','chip',cap));card.append(caps);if(d.platform_info)card.append(el('p','note','Nokia '+d.platform_info.model+' · S60 '+d.platform_info.s60+' · '+tr('Documented model profile')));const test=el('button','btn ghost','Diagnose connection');test.onclick=()=>connectionAction(async()=>{const r=await dmCall({action:'connection-diagnose',device:d.id});connection('result').textContent=r.connection?.evidence||tr('Connection checked');});test.disabled=!d.connection_kind;card.append(test);root.append(card);}if(!devices.length)root.append(el('p','note',tr('No enrolled connections. Connect Nokia USB or configure a transport in Bridge settings.')));}
window.addEventListener('symport-devices',event=>connectionDiagnostics(event.detail));
connectionStatus().catch(()=>{});

connection('host').onclick=()=>connectionAction(async()=>{const result=await dmCall({action:'connection-host'});const root=connection('candidates');root.replaceChildren();for(const kind of ['serial','bluetooth','volumes'])for(const candidate of result[kind]||[])root.append(el('p','',kind+' · '+(candidate.name||candidate.port||candidate.root)+' · '+(candidate.address||candidate.source)));for(const diagnostic of result.diagnostics||[])root.append(el('p','note',tr(diagnostic)));root.append(el('p','note',tr('Host records are candidates. Choose an enrolled connection to verify phone capabilities.')));});
