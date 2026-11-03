"use strict";
const dw=id=>document.getElementById(id),humanBytes=n=>Number.isFinite(n)?(n>=1024**3?(n/1024**3).toFixed(1)+' GiB':n>=1024**2?(n/1024**2).toFixed(1)+' MiB':n>=1024?(n/1024).toFixed(1)+' KiB':n+' B'):'unknown';
let imeiTimer;
window.renderPhoneDashboard=function(device){
 clearTimeout(imeiTimer);const host=dm('info');host.replaceChildren();
 const d=device||{},card=el('div','phone-dashboard'),phone=el('img','dashboard-phone');phone.src='/phones/nokia-e52-silver.png';phone.alt='Nokia E52';phone.width=76;phone.height=174;
 const content=el('div'),title=el('div','dashboard-title');title.append(el('h2','',d.model||'Symbian phone'),el('span','chip',d.connected?'Connected':'Disconnected'));content.append(title);
 const metrics=el('dl','dashboard-grid');
 for(const [label,value,percent] of [['RM',d.rm],['Firmware',d.firmware],['Battery',d.battery===null||d.battery===undefined?'unknown':d.battery+'%',d.battery],['Signal',d.signal===null||d.signal===undefined?'unknown':d.signal+'%',d.signal],['Transport',[d.transport,d.connection].filter(Boolean).join(' · ')||'unknown'],['USB mode',d.usb_mode],[(d.storage_scope==='enrolled-filesystem'?'Enrolled filesystem free':'Phone filesystem free'),humanBytes(d.free)],['Capacity',humanBytes(d.total)]]){
  const box=el('div','dashboard-metric'),v=el('dd','',String(value??'unknown'));v.dataset.i18nSkip='';box.append(el('dt','',label),v);
  if(Number.isFinite(percent)&&percent>=0&&percent<=100){const bar=el('progress');bar.max=100;bar.value=percent;bar.setAttribute('aria-label',tr(label));box.append(bar);}metrics.append(box);
 }
 const privateRow=el('div','dashboard-private'),imei=el('code','',d.imei||'unknown');imei.dataset.i18nSkip='';privateRow.append(el('span','muted','IMEI'),imei);
 if(d.capabilities?.includes('device-details')){const reveal=el('button','btn ghost','Reveal IMEI');reveal.onclick=()=>dmRun(async()=>{if(!confirm(tr('Reveal the private IMEI for 30 seconds?')))return;const result=await dmCall({action:'device-imei',device:d.id,confirm:true});imei.textContent=result.imei||'unknown';reveal.disabled=true;imeiTimer=setTimeout(()=>{imei.textContent=d.imei||'unknown';reveal.disabled=false;},30000);window.addEventListener('blur',()=>{imei.textContent=d.imei||'unknown';reveal.disabled=false;},{once:true});});privateRow.append(reveal);}
 const capabilities=el('div','dashboard-capabilities');for(const c of d.capabilities||[])capabilities.append(el('span','chip',c));
 const services=el('details'),summary=el('summary','','Connection services');services.append(summary);for(const [name,status]of Object.entries(d.capability_status||{}))services.append(el('p','',name+' · '+status.status+' · '+(status.reason||'')));content.append(metrics,privateRow,capabilities,services);card.append(phone,content);host.append(card);
};
renderPhoneDashboard(dmDevices.find(d=>d.id===dm('device').value));
let galleryVideoObserver;
let galleryItems=[],gallerySelected=new Set(),galleryPage=1,galleryGeneration=0,galleryRenderGeneration=0,galleryContext=null;
const gallerySize=48;
function galleryVisible(){const query=dw('gallery-search').value.toLocaleLowerCase(),kind=dw('gallery-kind').value,sort=dw('gallery-sort').value;return galleryItems.filter(i=>(!kind||i.kind===kind)&&i.path.toLocaleLowerCase().includes(query)).sort((a,b)=>sort==='name'?a.path.localeCompare(b.path):sort==='size'?b.size-a.size:b.modified-a.modified);}
function mediaUrl(item,download=false){return '/api/media/file?'+new URLSearchParams({device:galleryContext.device,path:item.path,revision:item.revision,...(download?{download:'1'}:{})});}
function galleryCount(){dw('gallery-count').replaceChildren(document.createTextNode(gallerySelected.size+' / '+galleryItems.length+' · '),el('span','','Selected'));dw('gallery-download').disabled=!gallerySelected.size;}
function galleryPreview(item){
 const dialog=dw('gallery-preview');dw('gallery-preview-title').textContent=item.name;const player=dw('gallery-player');player.replaceChildren();
 const media=el(item.kind==='photo'?'img':item.kind==='video'?'video':'audio');media.src=mediaUrl(item);if(item.kind==='photo')media.alt=item.name;else{media.controls=true;media.preload='metadata';}player.append(media);
 dw('gallery-metadata').textContent=item.path+' · '+humanBytes(item.size)+' · '+new Date(item.modified*1000).toLocaleString()+' · '+item.mime+(item.dimensions?' · '+item.dimensions:'');media.addEventListener('loadedmetadata',()=>{if(Number.isFinite(media.duration))dw('gallery-metadata').textContent+=' · '+media.duration.toFixed(1)+' s';if(media.videoWidth)dw('gallery-metadata').textContent+=' · '+media.videoWidth+'×'+media.videoHeight;},{once:true});dw('gallery-original').href=mediaUrl(item,true);dw('gallery-original').download=item.name;dialog.showModal();
}
function galleryRender(){
 galleryVideoObserver?.disconnect();const generation=galleryGeneration,render=++galleryRenderGeneration,items=galleryVisible(),visible=items.slice(0,galleryPage*gallerySize);dw('gallery-grid').replaceChildren();dw('gallery-more').hidden=visible.length>=items.length;
 const thumbs=[];galleryVideoObserver=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){const video=e.target;video.src=video.dataset.preview;video.preload='metadata';galleryVideoObserver.unobserve(video);}},{rootMargin:'100px'});
 for(const item of visible){
  const card=el('article','media-item'+(gallerySelected.has(item.path)?' selected':'')),check=el('input');check.type='checkbox';check.checked=gallerySelected.has(item.path);check.setAttribute('aria-label',tr('Select')+' '+item.name);check.onchange=()=>{check.checked?gallerySelected.add(item.path):gallerySelected.delete(item.path);card.classList.toggle('selected',check.checked);galleryCount();};
  const open=el('button','media-open'),art=el('div','media-art',item.kind==='photo'?'▧':item.kind==='video'?'▷':'♫'),copy=el('span','media-copy',item.name);copy.append(el('small','',humanBytes(item.size)+' · '+new Date(item.modified*1000).toLocaleDateString()));open.append(art,copy);open.onclick=()=>galleryPreview(item);card.append(check,open);dw('gallery-grid').append(card);if(item.kind==='photo')thumbs.push({item,art,copy});else if(item.kind==='video'){const poster=el('video','media-art');poster.muted=true;poster.playsInline=true;poster.preload='none';poster.dataset.preview=mediaUrl(item);poster.setAttribute('aria-hidden','true');poster.onloadedmetadata=()=>{if(poster.videoWidth){item.dimensions=poster.videoWidth+'×'+poster.videoHeight;copy.querySelector('small').append(document.createTextNode(' · '+item.dimensions));}if(Number.isFinite(poster.duration)&&poster.duration>0)poster.currentTime=Math.min(.1,poster.duration/2);};poster.onerror=()=>{poster.removeAttribute('src');art.title=tr('This browser cannot generate a video thumbnail. Download the original file.');poster.replaceWith(art);};art.replaceWith(poster);galleryVideoObserver.observe(poster);}
 }
 galleryCount();
 // Four concurrent thumbnail requests; originals stay on the PC and are never
 // downloaded into the grid. A new folder/device invalidates outstanding results.
 let index=0;async function worker(){while(index<thumbs.length&&generation===galleryGeneration&&render===galleryRenderGeneration){const {item,art,copy}=thumbs[index++];try{const result=await dmCall({action:'media-thumbnail',device:galleryContext.device,path:item.path,revision:item.revision});if(result.status==='available'&&generation===galleryGeneration&&art.isConnected){const image=el('img','media-art');image.alt=item.name;image.loading='lazy';image.src='data:image/jpeg;base64,'+result.content;item.dimensions=result.width+'×'+result.height;art.replaceWith(image);copy.querySelector('small').append(document.createTextNode(' · '+item.dimensions));}else if(art.isConnected){art.title=tr(result.reason||'Thumbnail unavailable. Download the original file.');}}catch{if(art.isConnected)art.title=tr('Thumbnail unavailable. Download the original file.');}}}for(let i=0;i<4;i++)worker();
}
function galleryReset(){galleryVideoObserver?.disconnect();galleryGeneration++;galleryItems=[];gallerySelected.clear();galleryContext=null;dw('gallery-grid').replaceChildren();galleryCount();dw('gallery-preview').close();}
dw('gallery-read').onclick=()=>suiteBusy(dw('gallery-read'),dw('gallery-status'),async()=>{
 galleryReset();const context={device:dw('media-device').value,path:dw('media-path').value};if(!context.device)throw Error(tr('Select a connected volume first'));const generation=galleryGeneration;const r=await dmCall({action:'media-list',...context});if(generation!==galleryGeneration)return;galleryContext=context;galleryItems=r.items;galleryPage=1;galleryRender();dw('gallery-status').textContent=tr(r.truncated?'Search limit reached. Choose a narrower folder to see more files.':r.skipped?'Some folders were inaccessible. Only accessible media are shown.':'Media loaded. Select files to download, or open a preview.');
});
for(const id of ['gallery-search','gallery-kind','gallery-sort'])dw(id).oninput=()=>{galleryPage=1;galleryRender();};
dw('gallery-more').onclick=()=>{galleryPage++;galleryRender();};
dw('gallery-select').onclick=()=>{for(const i of galleryVisible().slice(0,galleryPage*gallerySize))gallerySelected.add(i.path);galleryRender();};
dw('gallery-download').onclick=()=>suiteBusy(dw('gallery-download'),dw('gallery-status'),async()=>{if(!galleryContext)return;const items=galleryItems.filter(i=>gallerySelected.has(i.path)).map(({path,revision})=>({path,revision}));const result=await request('POST','/api/media/export',{device:galleryContext.device,items});const a=el('a');a.href=result.url;a.download='symport-media.zip';a.click();dw('gallery-status').textContent=tr('Your private ZIP download is ready.');});
dw('gallery-close').onclick=()=>dw('gallery-preview').close();dw('gallery-preview').addEventListener('close',()=>{const media=dw('gallery-player').querySelector('video,audio');if(media){media.pause();media.removeAttribute('src');media.load();}dw('gallery-player').replaceChildren();});
dw('media-device').addEventListener('change',galleryReset);dw('media-path').addEventListener('change',galleryReset);

// Personal data stays in this tab and in private, explicitly created backups.
let phoneContacts=null,phoneSms=null,phoneCalendars={},contactPlan=null,calendarPlan=null,calendarEditing=null,smsPage=1;
const deviceById=id=>dmDevices.find(d=>d.id===id),hasPersonal=id=>deviceById(id)?.capabilities.includes('personal-data');
function pimAction(device,action,data={}){return dmCall({action,device,...data});}
function pimPreview(host,plan){host.hidden=false;host.replaceChildren();const list=el('ul');for(const change of plan.changes){const before=change.before,after=change.after;const entry=el('li','',tr(change.operation==='add'?'Add':'Update')+' · '+(after.name||after.summary));entry.append(el('pre','',JSON.stringify({before,after},null,2)));list.append(entry);}for(const conflict of plan.conflicts)list.append(el('li','error-text',(conflict.summary||'')+' · '+tr(conflict.reason)));host.append(list,el('p','',tr('Skipped')+': '+plan.skipped+' · '+tr('Deletions')+': 0'));}
async function pimExport(device,snapshot,format){const file=await pimAction(device,'personal-export',{snapshot,format});saveBase64(file.content,file.name,file.mime);}
async function pimBackup(device,snapshot){const result=await pimAction(device,'personal-backup',{snapshot});const file=await pimAction(device,'personal-backup-download',{backup:result.backup});saveBase64(file.content,file.name,'application/json');}
async function backupAfterWrite(device,result){if(result.backup){const file=await pimAction(device,'personal-backup-download',{backup:result.backup});saveBase64(file.content,file.name,'application/json');}}
function updatePimAvailability(){
 const contacts=dw('contacts-device').value,personal=hasPersonal(contacts);dw('contacts-sync-preview').hidden=!personal;dw('contacts-backup').hidden=!phoneContacts||phoneContacts.device!==contacts;dw('contacts-phone-vcard').hidden=dw('contacts-backup').hidden;dw('contacts-duplicates').hidden=!phoneContacts?.duplicates?.length;dw('contacts-send').hidden=!!personal;
 const device=deviceById(dw('sms-device').value),status=device?.capability_status?.sms;
 dw('sms-read').disabled=!hasPersonal(device?.id)||status?.status!=='available';
 dw('sms-send').disabled=!phoneSms||phoneSms.device!==device?.id||!device?.sms_send_verified;
 dw('sms-send-reason').textContent=tr(device?.sms_send_verified?'Each SMS requires confirmation. Your operator may charge for sending. Delivery is reported separately.':'Sending is disabled until an operator validates this phone and connection on the PC Bridge.');
 if(!phoneSms)dw('sms-status').textContent=status?.status==='unavailable'?'Gammu: '+status.reason+' · '+tr('Export messages with Nokia Suite instead.'):tr('Select a Gammu connection. Mass Storage does not expose SMS. For other connections, export messages with Nokia Suite.');
 dw('calendar-editor-card').hidden=!hasPersonal(dw('calendar-device').value);
}
window.addEventListener('symport-devices',()=>{setTimeout(updatePimAvailability,0);});
for(const id of ['contacts-device','sms-device','calendar-device'])dw(id).addEventListener('change',()=>{if(id==='contacts-device'){if(phoneContacts){setContacts([]);dw('contacts-workspace').hidden=true;}phoneContacts=null;contactPlan=null;dw('contacts-sync-plan').hidden=true;dw('contacts-sync-apply').hidden=true;}if(id==='sms-device')clearSms();if(id==='calendar-device'){phoneCalendars={};calendarPlan=null;dw('pim-calendar-plan').hidden=true;dw('pim-calendar-apply').hidden=true;calendarData=null;dw('calendar-workspace').hidden=true;}updatePimAvailability();});
const legacyContactRead=dw('contacts-read').onclick;
dw('contacts-read').onclick=()=>{
 const device=dw('contacts-device').value;if(!hasPersonal(device))return legacyContactRead();
 return suiteBusy(dw('contacts-read'),dw('contacts-result'),async()=>{const result=await pimAction(device,'personal-read',{domain:'contacts'});phoneContacts={...result,device};contactPlan=null;window.contactDuplicateIndexes=null;setContacts(result.rows,[]);dw('contacts-result').replaceChildren(el('span','','Read from phone'),document.createTextNode(' · '+result.rows.length+' · '),el('span','','Duplicate groups'),document.createTextNode(': '+result.duplicates.length));dw('contacts-sync-apply').hidden=true;updatePimAvailability();});
};
dw('contacts-sync-preview').onclick=()=>suiteBusy(dw('contacts-sync-preview'),dw('contacts-result'),async()=>{
 const device=dw('contacts-device').value;if(!phoneContacts||phoneContacts.device!==device){const result=await pimAction(device,'personal-read',{domain:'contacts'});phoneContacts={...result,device};}
 const result=await pimAction(device,'personal-preview',{snapshot:phoneContacts.snapshot,rows:selectedRows()});contactPlan=result;pimPreview(dw('contacts-sync-plan'),result);dw('contacts-sync-apply').hidden=!result.changes.length||!!result.conflicts.length;
});
dw('contacts-sync-apply').onclick=()=>suiteBusy(dw('contacts-sync-apply'),dw('contacts-result'),async()=>{
 if(!contactPlan||!confirm(tr('Apply the displayed contact changes? A private backup is saved first; no entries will be deleted.')))return;
 const plan=contactPlan;contactPlan=null;dw('contacts-sync-apply').hidden=true;const device=phoneContacts.device;const result=await pimAction(device,'personal-apply',{snapshot:phoneContacts.snapshot,plan:plan.plan,confirm:true});dw('contacts-result').textContent=tr(result.status==='verified-by-readback'?'Changes verified by reading the phone again.':'Some changes could not be verified. Read the phone before retrying.')+' · '+result.verified;await backupAfterWrite(device,result);phoneContacts=null;updatePimAvailability();
});
dw('contacts-backup').onclick=()=>suiteBusy(dw('contacts-backup'),dw('contacts-result'),()=>pimBackup(phoneContacts.device,phoneContacts.snapshot));
dw('contacts-clear').addEventListener('click',()=>{phoneContacts=null;contactPlan=null;dw('contacts-sync-plan').hidden=true;dw('contacts-sync-apply').hidden=true;updatePimAvailability();});
// Existing normalized contact export/import remains the cloud/file workspace.
function clearSms(){phoneSms=null;smsPage=1;dw('sms-rows').replaceChildren();dw('sms-workspace').hidden=true;dw('sms-text').value='';dw('sms-number').value='';}
dw('sms-clear').onclick=()=>{clearSms();updatePimAvailability();};
dw('sms-read').onclick=()=>suiteBusy(dw('sms-read'),dw('sms-status'),async()=>{
 const device=dw('sms-device').value;clearSms();const result=await pimAction(device,'personal-read',{domain:'sms'});phoneSms={...result,device};dw('sms-workspace').hidden=false;dw('sms-thread').replaceChildren(new Option(tr('All conversations'),''));
 const names=new Map();if(phoneContacts?.device===device&&phoneContacts.fingerprint===result.fingerprint)for(const c of phoneContacts.rows)for(const p of c.phones)names.set(p.replace(/\D/g,''),c.name);
 for(const number of [...new Set(result.rows.map(r=>r.number))].sort())dw('sms-thread').append(new Option(names.get(number.replace(/\D/g,''))||number,number));smsRender();dw('sms-status').textContent=tr('SMS read from phone. Multipart messages retain their segment numbers.');updatePimAvailability();
});
function smsRender(){if(!phoneSms)return;const q=dw('sms-search').value.toLocaleLowerCase(),direction=dw('sms-filter').value,number=dw('sms-thread').value;const rows=phoneSms.rows.filter(r=>(!direction||r.direction===direction)&&(!number||r.number===number)&&(r.number+' '+r.text).toLocaleLowerCase().includes(q));dw('sms-rows').replaceChildren();for(const row of rows.slice(0,smsPage*100)){const article=el('article','pim-thread'),head=el('header');head.append(el('strong','',row.number),el('span','muted',row.date),el('span','muted',tr(row.direction)+' · '+row.state+(row.parts>1?' · '+row.part+'/'+row.parts:'')));article.append(head,el('p','',row.text));dw('sms-rows').append(article);}dw('sms-count').textContent=Math.min(rows.length,smsPage*100)+' / '+rows.length;dw('sms-more').hidden=rows.length<=smsPage*100;}
for(const id of ['sms-search','sms-filter','sms-thread'])dw(id).oninput=()=>{smsPage=1;smsRender();};dw('sms-more').onclick=()=>{smsPage++;smsRender();};
for(const format of ['json','csv'])dw('sms-'+format).onclick=()=>suiteBusy(dw('sms-'+format),dw('sms-status'),()=>pimExport(phoneSms.device,phoneSms.snapshot,format));
dw('sms-backup').onclick=()=>suiteBusy(dw('sms-backup'),dw('sms-status'),()=>pimBackup(phoneSms.device,phoneSms.snapshot));
dw('sms-send').onclick=()=>suiteBusy(dw('sms-send'),dw('sms-status'),async()=>{
 const number=dw('sms-number').value.trim(),text=dw('sms-text').value;if(!phoneSms||!confirm(tr('Send this SMS? Charges may apply.')+'\n'+number+'\n\n'+text))return;
 const snapshot=phoneSms;phoneSms=null;updatePimAvailability();const result=await pimAction(snapshot.device,'sms-send',{snapshot:snapshot.snapshot,number,text,confirm:true});dw('sms-status').textContent=tr('Submitted to the network. Delivery status is unknown. Read SMS again before sending another message.');await backupAfterWrite(snapshot.device,result);
});
const legacyCalendarRead=dw('calendar-read').onclick;
function calendarDomain(){return dw('pim-calendar-domain').value;}
async function nativeCalendarRead(){
 const device=dw('calendar-device').value,domain=calendarDomain();const result=await pimAction(device,'personal-read',{domain});phoneCalendars[domain]={...result,device};calendarPlan=null;calendarData={events:domain==='calendar'?result.rows:[],todos:domain==='tasks'?result.rows:[]};dw('calendar-workspace').hidden=false;calFilter();dw('calendar-json').disabled=false;dw('calendar-ics').disabled=false;dw('pim-calendar-editor').hidden=true;dw('pim-calendar-plan').hidden=true;dw('pim-calendar-apply').hidden=true;calStatus(tr('Read from phone')+' · '+result.rows.length);calendarEditButtons();
}
dw('calendar-read').onclick=()=>hasPersonal(dw('calendar-device').value)?suiteBusy(dw('calendar-read'),dw('calendar-status'),nativeCalendarRead):legacyCalendarRead();
function calendarEditButtons(){if(!hasPersonal(dw('calendar-device').value))return;const rows=phoneCalendars[calendarDomain()]?.rows||[],q=dw('calendar-search').value.toLocaleLowerCase();for(const [i,trNode]of [...dw(calendarDomain()==='calendar'?'calendar-events':'calendar-todos').children].entries()){const row=rows.filter(r=>Object.values(r).filter(v=>typeof v==='string').join(' ').toLocaleLowerCase().includes(q))[i];if(!row)continue;const cell=el('td'),button=el('button','btn ghost small','Edit');button.disabled=!!row.recurrence;button.title=row.recurrence?tr('Recurring entries require manual editing on the phone'):'';button.onclick=()=>calendarEditor(row);cell.append(button);trNode.append(cell);}}
dw('calendar-search').addEventListener('input',calendarEditButtons);
function calendarEditor(row){calendarEditing=row||null;dw('pim-calendar-editor').hidden=false;for(const [id,key]of [['summary','summary'],['location','location'],['description','description'],['start','start'],['end',calendarDomain()==='tasks'?'due':'end']])dw('pim-cal-'+id).value=row?.[key]||'';dw('pim-cal-completed').checked=!!row?.completed;}
dw('pim-calendar-new').onclick=()=>calendarEditor(null);
dw('pim-calendar-domain').onchange=()=>{calendarEditing=null;calendarPlan=null;dw('pim-calendar-plan').hidden=true;dw('pim-calendar-apply').hidden=true;dw('pim-calendar-editor').hidden=true;suiteBusy(dw('calendar-read'),dw('calendar-status'),nativeCalendarRead);};
async function previewCalendar(rows){const domain=calendarDomain(),snapshot=phoneCalendars[domain];if(!snapshot)throw Error(tr('Read this calendar store before previewing changes'));const result=await pimAction(snapshot.device,'personal-preview',{snapshot:snapshot.snapshot,rows});calendarPlan={...result,domain};pimPreview(dw('pim-calendar-plan'),result);dw('pim-calendar-apply').hidden=!result.changes.length||!!result.conflicts.length;}
dw('pim-calendar-editor').onsubmit=event=>{event.preventDefault();suiteBusy(dw('pim-calendar-new'),dw('pim-calendar-status'),async()=>{const row={...(calendarEditing||{}),kind:calendarDomain(),summary:dw('pim-cal-summary').value,location:dw('pim-cal-location').value,description:dw('pim-cal-description').value,start:dw('pim-cal-start').value,[calendarDomain()==='tasks'?'due':'end']:dw('pim-cal-end').value,completed:dw('pim-cal-completed').checked};await previewCalendar([row]);});};
dw('pim-calendar-import').onclick=()=>suiteBusy(dw('pim-calendar-import'),dw('pim-calendar-status'),async()=>{const file=dw('pim-calendar-file').files[0];if(!file||file.size>4*1024*1024)throw Error(tr('Choose an iCalendar file up to 4 MiB'));const result=await pimAction(dw('calendar-device').value,'personal-calendar-import',{text:await file.text()});await previewCalendar(result.rows.filter(r=>r.kind===calendarDomain()));});
dw('pim-calendar-apply').onclick=()=>suiteBusy(dw('pim-calendar-apply'),dw('pim-calendar-status'),async()=>{if(!calendarPlan||!confirm(tr('Apply the displayed calendar changes? A private backup is saved first; no entries will be deleted.')))return;const plan=calendarPlan;calendarPlan=null;dw('pim-calendar-apply').hidden=true;const snapshot=phoneCalendars[plan.domain],result=await pimAction(snapshot.device,'personal-apply',{snapshot:snapshot.snapshot,plan:plan.plan,confirm:true});dw('pim-calendar-status').textContent=tr(result.status==='verified-by-readback'?'Changes verified by reading the phone again.':'Some changes could not be verified. Read the phone before retrying.')+' · '+result.verified;await backupAfterWrite(snapshot.device,result);delete phoneCalendars[plan.domain];});
dw('pim-calendar-backup').onclick=()=>suiteBusy(dw('pim-calendar-backup'),dw('pim-calendar-status'),async()=>{const snapshot=phoneCalendars[calendarDomain()];if(!snapshot)throw Error(tr('Read this calendar store before previewing changes'));await pimBackup(snapshot.device,snapshot.snapshot);});
for(const format of ['json','ics']){const button=dw('calendar-'+format),legacy=button.onclick;button.onclick=()=>hasPersonal(dw('calendar-device').value)?suiteBusy(button,dw('calendar-status'),async()=>{const snapshot=phoneCalendars[calendarDomain()];if(!snapshot)throw Error(tr('Read this calendar store before previewing changes'));await pimExport(snapshot.device,snapshot.snapshot,format);}):legacy();}
updatePimAvailability();

window.addEventListener('symport-language',()=>{renderPhoneDashboard(dmDevices.find(d=>d.id===dm('device').value));smsRender();});

dw('contacts-phone-vcard').onclick=()=>suiteBusy(dw('contacts-phone-vcard'),dw('contacts-result'),()=>pimExport(phoneContacts.device,phoneContacts.snapshot,'vcf'));
dw('contacts-duplicates').onclick=()=>{window.contactDuplicateIndexes=window.contactDuplicateIndexes?null:new Set(phoneContacts.duplicates.flat());dw('contacts-duplicates').textContent=tr(window.contactDuplicateIndexes?'Show all contacts':'Show duplicates');contactPage=0;renderContacts();};

window.addEventListener('symport-devices',()=>setTimeout(()=>{
 if(galleryContext&&galleryContext.device!==dw('media-device').value)galleryReset();
 if(phoneContacts&&(phoneContacts.device!==dw('contacts-device').value||deviceById(phoneContacts.device)?.fingerprint!==phoneContacts.fingerprint)){phoneContacts=null;contactPlan=null;window.contactDuplicateIndexes=null;dw('contacts-workspace').hidden=true;dw('contacts-sync-plan').hidden=true;dw('contacts-sync-apply').hidden=true;}
 if(phoneSms&&(phoneSms.device!==dw('sms-device').value||deviceById(phoneSms.device)?.fingerprint!==phoneSms.fingerprint))clearSms();
 for(const [domain,snapshot]of Object.entries(phoneCalendars))if(snapshot.device!==dw('calendar-device').value||deviceById(snapshot.device)?.fingerprint!==snapshot.fingerprint){delete phoneCalendars[domain];calendarData=null;calendarPlan=null;dw('calendar-workspace').hidden=true;dw('pim-calendar-editor').hidden=true;dw('pim-calendar-plan').hidden=true;dw('pim-calendar-apply').hidden=true;}
 updatePimAvailability();
},0));
