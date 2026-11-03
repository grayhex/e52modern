"use strict";
const lab=id=>document.getElementById('lab-'+id);
const labApi=data=>request('POST','/api/lab',data);
let labState={},labReport=null,labBusy=false,labFirmwareIds=[],labPolling=false,labFrameBusy=false,labInput=Promise.resolve(),labHeld=new Map(),labReportSignature='';
const labLabels={installed:'Установлен',launched:'Запущен',failed:'Ошибка',unsupported:'Недоступно','not-tested':'Не проверено'};
function labError(e){lab('status').textContent=e.message;notify(e.message);}
async function labDo(fn){if(labBusy)return;labBusy=true;labEnable();try{await fn();}catch(e){labError(e);}finally{labBusy=false;await labRefresh();}}
function labEnable(){
 const available=!!labState.available,active=!!labState.active,running=!!labState.health?.instance?.running,code=!!lab('device').value;
 for(const id of ['start','reboot','test'])lab(id).disabled=!available||!code||active||labBusy;
 lab('stop').disabled=!running||labBusy||!!labState.reports?.find(r=>r.id===labState.active&&r.kind==='firmware');
 lab('upload-firmware').disabled=!available||active||labBusy;lab('install-firmware').disabled=!available||active||labBusy||!labFirmwareIds.length;
 lab('device').disabled=!available||active||labBusy;
 for(const b of document.querySelectorAll('[data-lab-key]'))b.disabled=!running||!!labState.control_reason||!!labState.keys&&!Object.hasOwn(labState.keys.keys||{},b.dataset.labKey);
 const current=labReport&&labReport.id===labState.current&&!labReport.running&&running&&labReport.events?.some(e=>e.stage==='firmware-booted');
 lab('shot').disabled=!current;lab('observe').disabled=!current;lab('logs').disabled=!current;
 lab('transfer').disabled=!lab('phone').value||labBusy;
}
async function labRefresh(){
 if(labPolling)return;labPolling=true;
 try{
  labState=await labApi({action:'state'});const h=labState.health||{},devices=h.firmware?.devices||[];
  lab('service-badge').textContent=labState.available?'MGO · подключён':'MGO · недоступен';lab('service-badge').classList.toggle('lab-online',!!labState.available);
  lab('status').textContent=(labState.reason?labState.reason+' · Включение: docker compose --profile emulator up -d --build':null)||`${h.emulator||'EKA2L1'} · ${devices.length} прошивок · ${h.instance?.running?'сеанс запущен':'сеанс остановлен'}${labState.active?' · выполняется операция':''}`;
  const old=lab('device').value;lab('device').replaceChildren(new Option(devices.length?'Выберите прошивку':'Нет установленной прошивки',''));
  for(const d of devices)lab('device').append(new Option(`${d.manufacturer||''} ${d.model||''} · ${d.code}`,d.code));
  lab('device').value=devices.some(d=>d.code===old)?old:(h.defaults?.symbian||'');
  const d=devices.find(d=>d.code===lab('device').value);lab('firmware-info').textContent=d?`${d.manufacturer||''} ${d.model||''} · ${d.code}. Реальная E52: not-tested.`:'Установите собственную прошивку и выберите устройство. Имя E52 само по себе не подтверждает совместимость.';
  labFirmwareIds=labFirmwareIds.filter(id=>labState.uploads?.[id]&&!labState.uploads[id].consumed);labRenderUploads();labRenderReports();labEnable();
  if(labReport){const updated=labState.reports.find(r=>r.id===labReport.id);if(updated&&updated.updated!==labReportSignature)await labShowReport(updated,false);}
  if(!h.instance?.running){lab('screen').hidden=true;lab('screen-empty').hidden=false;lab('screen-empty').textContent='Сеанс остановлен. Загрузите прошивку и нажмите «Запустить».';lab('screen-status').textContent='Нет активного экрана.';}
 }catch(e){labError(e);}finally{labPolling=false;}
}
function labRenderUploads(){
 const box=lab('uploads');box.replaceChildren();
 for(const u of Object.values(labState.uploads||{}).slice(-30).reverse()){
  const row=el('label','lab-upload-entry');const c=el('input');c.type='checkbox';c.checked=labFirmwareIds.includes(u.id);c.disabled=labBusy||!!labState.active||!!u.consumed;c.onchange=()=>{labFirmwareIds=c.checked?[...labFirmwareIds,u.id]:labFirmwareIds.filter(id=>id!==u.id);labEnable();};
  row.append(c,el('span','',`${u.slot.toUpperCase()} · ${u.name} · ${(u.size/1024/1024).toFixed(1)} МиБ${u.consumed?' · использован':''}`));box.append(row);
 }
}
function labRenderReports(){
 const box=lab('reports');box.replaceChildren();if(!labState.reports?.length){box.textContent='Отчёты появятся после первого запуска или теста.';return;}
 for(const r of labState.reports){const b=el('button','lab-report-row');b.append(el('strong','',r.package?.name||(r.kind==='firmware'?'Установка прошивки':'Сеанс Symbian')),el('span','status '+(r.running?'running':r.status),r.running?'В работе':r.state==='running'?'Сеанс готов':labLabels[r.status]||r.status),el('small','muted',new Date(r.created).toLocaleString('ru-RU')));b.onclick=()=>labDo(()=>labShowReport(r,true));box.append(b);}
}
async function labShowReport(report,scroll){
 report=await labApi({action:'report',id:report.id});labReport=report;labReportSignature=report.updated;lab('report').hidden=false;lab('report-title').textContent=report.package?.name||'Отчёт сеанса';
 const summary=lab('report-summary');summary.replaceChildren();
 const facts=[['Статус',report.running?'Операция выполняется':report.state==='running'?'Сеанс готов (ПО не проверялось)':report.status],['Движок',report.engine],['Установка',report.install],['Запуск приложения',report.launch],['Физическая Nokia',report.physical_device],['Прошивка',report.firmware?JSON.stringify(report.firmware):'Не выбрана'],['SHA-256',report.package?.sha256||'Нет пакета']];
 const dl=el('dl','device-details');for(const [key,value] of facts)dl.append(el('dt','muted',key),el('dd','lab-value',value));summary.append(dl);
 for(const field of ['error','launch_reason','screen_reason','instructions'])if(report[field])summary.append(el('p',field==='error'?'error-text':'note',report[field]));
 if(report.observations?.length)summary.append(el('p','note','Наблюдения пользователя: '+report.observations.map(o=>`${o.step}: ${o.result}`).join(' · ')));
 lab('report-summary').dataset.install=report.install;lab('report-summary').dataset.launch=report.launch;lab('report-summary').dataset.report=report.id;
 lab('report-logs').textContent=JSON.stringify({events:report.events,job:report.agent_job,install:report.install_evidence,launch:report.launch_evidence,logs:report.logs,log_error:report.log_error,limitations:report.limitations,physical_transfer:report.physical_transfer},null,2);
 lab('theme-review').hidden=report.kind!=='theme'||report.install!=='installed';lab('transfer-panel').hidden=!['app','theme'].includes(report.kind)||report.install!=='installed';
 lab('phone-path').value=report.package?.name||'';lab('transfer-result').textContent=report.physical_transfer?'Пакет передан. Установка на Nokia: not-tested.':'';
 const gallery=lab('report-shots');gallery.replaceChildren();
 for(const shot of report.screenshots||[]){const data=await labApi({action:'saved-shot',id:report.id,name:shot.name});const a=el('a');a.href='data:image/png;base64,'+data.png;a.download=shot.name;const image=el('img');image.src=a.href;image.alt=`Снимок EKA2L1 · ${shot.width}×${shot.height} · ${shot.at}`;image.width=120;a.append(image,el('span','muted','Скачать PNG ↓'));gallery.append(a);}
 labEnable();if(scroll)lab('report').scrollIntoView({block:'start',behavior:'smooth'});
}
async function labFrame(){
 if(labFrameBusy||document.hidden||location.hash!=='#lab'||!labState.health?.instance?.running)return;
 labFrameBusy=true;try{const f=await labApi({action:'frame'});lab('screen').src='data:image/png;base64,'+f.png;lab('screen').hidden=false;lab('screen-empty').hidden=true;lab('screen-status').textContent=`EKA2L1 · ${f.width} × ${f.height}${f.width!==240||f.height!==320?' · разрешение этой прошивки отличается от E52':''}`;}
 catch(e){lab('screen-status').textContent=e.message;lab('screen').hidden=true;lab('screen-empty').hidden=false;lab('screen-empty').textContent=e.message;}finally{labFrameBusy=false;}
}
lab('refresh').onclick=()=>labRefresh();
lab('device').onchange=()=>labDo(async()=>{if(lab('device').value)await labApi({action:'select',code:lab('device').value});});
for(const action of ['start','reboot','stop'])lab(action).onclick=()=>labDo(async()=>{
 if(action==='reboot'&&!confirm('Перезапустить виртуальный телефон? Текущая программа будет остановлена.'))return;
 await labRelease();const r=await labApi({action,code:lab('device').value});if(r.id)await labShowReport(r,false);
});
lab('format').onchange=()=>{for(const mode of ['rom','archive','vpl'])lab(mode+'-fields').hidden=lab('format').value!==mode;labFirmwareIds=[];labRenderUploads();labEnable();};
function labUpload(file,slot,bundle){
 return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST','/api/lab/firmware?'+new URLSearchParams({slot,name:file.name,...(bundle?{bundle}:{})}));xhr.setRequestHeader('X-Symport-Token',token);xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.timeout=3600000;
 xhr.upload.onprogress=e=>{if(e.lengthComputable)lab('upload-progress').value=100*e.loaded/e.total;};
 xhr.onload=()=>{try{const data=JSON.parse(xhr.responseText);if(xhr.status!==200)throw Error(data.error||'Загрузка не принята');resolve(data);}catch(e){reject(e);}};
 xhr.onerror=()=>reject(Error('Загрузка прервана. Повторите комплект файлов.'));xhr.ontimeout=()=>reject(Error('Истекло время загрузки'));xhr.send(file);});
}
lab('upload-firmware').onclick=()=>labDo(async()=>{
 const format=lab('format').value;let files=[],bundle;
 if(format==='rom'){if(lab('rom').files[0])files.push(['rom',lab('rom').files[0]]);if(lab('rpkg').files[0])files.push(['rpkg',lab('rpkg').files[0]]);if(!files.some(([s])=>s==='rom'))throw Error('Выберите ROM');}
 else if(format==='archive'){if(lab('archive').files[0])files=[['archive',lab('archive').files[0]]];}
 else {files=[...lab('factory').files].map(f=>[f.name.toLowerCase().endsWith('.vpl')?'vpl':'fpsx',f]);if(files.filter(([s])=>s==='vpl').length!==1)throw Error('Выберите один VPL и связанные FPSX');bundle=(await labApi({action:'bundle'})).bundle;}
 if(!files.length)throw Error('Выберите файлы прошивки');
 if(files.some(([slot,f])=>f.size===0||f.size>2*1024**3||(slot==='vpl'&&f.size>4*1024**2)))throw Error('Превышен лимит файла прошивки');
 labFirmwareIds=[];lab('upload-progress').hidden=false;
 try{for(const [slot,file] of files){lab('upload-status').textContent='Загружается '+file.name;const result=await labUpload(file,slot,bundle);labFirmwareIds.push(result.id);}lab('upload-status').textContent='Файлы сохранены в MGO. Проверьте комплект и нажмите «Установить прошивку».';}
 finally{lab('upload-progress').hidden=true;}
});
lab('install-firmware').onclick=()=>labDo(async()=>{
 if(!confirm('Установить выбранный комплект вашей прошивки? Текущий сеанс остановится. Нужен полный комплект, поддерживаемый EKA2L1.'))return;
 const variant=lab('variant').value;const r=await labApi({action:'install-firmware',uploads:labFirmwareIds,confirm:true,...(lab('format').value==='vpl'&&variant!==''?{variant:Number(variant)}:{})});await labShowReport(r,false);
});
function labSources(){
 const source=lab('source').value;lab('file-field').hidden=source!=='upload';lab('reference-field').hidden=source==='upload';const previous=lab('reference').value;lab('reference').replaceChildren();
 const list=source==='build'?state.packages:source==='library'?(state.library||[]):source==='catalog'?catState.apps.filter(a=>a.delivery==='automatic'):[];
 for(const p of list)lab('reference').append(new Option(p.name,p.id));if(list.some(p=>p.id===previous))lab('reference').value=previous;
 if(source==='library')lab('kind').value='theme';
}
lab('source').onchange=labSources;
function labChoose(source,reference,kind){
 lab('source').value=source;labSources();if(source!=='upload')lab('reference').value=reference;lab('kind').value=kind==='theme'?'theme':'app';
 location.hash='#lab';lab('test-status').textContent=source==='upload'?'Скачайте пакет по ссылке автора и выберите файл здесь.':'Пакет выбран. Проверьте прошивку и подтвердите тест.';labRefresh();
}
lab('test').onclick=()=>labDo(async()=>{
 const source=lab('source').value,data={action:'test',source,reference:lab('reference').value,kind:lab('kind').value,code:lab('device').value,confirm:true};
 if(source==='upload'){const file=lab('package').files[0];if(!file||file.size>32*1024**2)throw Error('Выберите пакет до 32 МиБ');data.name=file.name;data.content=await readFileBase64(file);}
 else if(!data.reference)throw Error('Выберите пакет');
 if(!confirm('Установить пакет в выбранную прошивку эмулятора? Для темы затем примените её через системное меню. Это не проверка на физической Nokia.'))return;
 const r=await labApi(data);await labShowReport(r,false);lab('test-status').textContent='Тест запущен. Состояние и результат появятся в отчёте.';
});
for(const action of ['shot','observe'])lab(action).onclick=()=>labDo(async()=>{await labApi({action,id:labReport.id,...(action==='observe'?{step:lab('observe-step').value,result:lab('observe-result').value}:{})});await labShowReport(await labApi({action:'report',id:labReport.id}),false);});
lab('logs').onclick=()=>labDo(async()=>{lab('report-logs').textContent=JSON.stringify(await labApi({action:'logs'}),null,2);});
lab('report-export').onclick=()=>{if(labReport)saveBase64(btoa(unescape(encodeURIComponent(JSON.stringify(labReport,null,2)))),'emulator-'+labReport.id+'.json','application/json');};
lab('phone').onchange=labEnable;window.addEventListener('symport-devices',labEnable);
lab('transfer').onclick=()=>labDo(async()=>{if(!confirm('Передать проверенный пакет на выбранную Nokia? После передачи установите его и проверьте работу на телефоне.'))return;const result=await labApi({action:'transfer',id:labReport.id,device:lab('phone').value,path:lab('phone-path').value,confirm:true});lab('transfer-result').textContent=result.status||'Пакет передан; установка на Nokia не проверена.';await labShowReport(await labApi({action:'report',id:labReport.id}),false);});
function labSendKey(key,event){labInput=labInput.catch(()=>{}).then(()=>labApi({action:'key',key,event})).catch(e=>{lab('screen-status').textContent=e.message;});return labInput;}
function labPress(source,key){
 if(labHeld.has(source))return;
 const already=[...labHeld.values()].includes(key);labHeld.set(source,key);
 for(const b of document.querySelectorAll('[data-lab-key]'))if(b.dataset.labKey===key)b.classList.add('is-held');
 if(!already)labSendKey(key,'down');
}
function labLift(source){
 const key=labHeld.get(source);if(!key)return;labHeld.delete(source);
 if(![...labHeld.values()].includes(key)){
  for(const b of document.querySelectorAll('[data-lab-key]'))if(b.dataset.labKey===key)b.classList.remove('is-held');
  labSendKey(key,'up');
 }
}
function labRelease(){labHeld.clear();for(const b of document.querySelectorAll('[data-lab-key]'))b.classList.remove('is-held');labInput=labInput.catch(()=>{}).then(()=>labState.health?.instance?.running?labApi({action:'release'}):null).catch(()=>{});return labInput;}
const keyboard={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',Enter:'ok',F1:'lsk',F2:'rsk',F3:'applications',Backspace:'clear',Escape:'end','*':'star','#':'hash',...Object.fromEntries([...Array(10).keys()].map(x=>[String(x),String(x)]))};
for(const b of document.querySelectorAll('[data-lab-key]')){
 b.onpointerdown=e=>{if(b.disabled)return;e.preventDefault();lab('controls').focus({preventScroll:true});b.setPointerCapture(e.pointerId);labPress('pointer:'+e.pointerId,b.dataset.labKey);};
 b.onpointerup=b.onpointercancel=b.onlostpointercapture=e=>labLift('pointer:'+e.pointerId);
 // Keyboard and assistive-technology activation (pointer clicks already sent down/up).
 b.onclick=e=>{if(e.detail===0&&!b.disabled){labSendKey(b.dataset.labKey,'down');labSendKey(b.dataset.labKey,'up');}};
}
lab('controls').onkeydown=e=>{
 if(e.target.closest('[data-lab-key]')&&['Enter',' '].includes(e.key))return;
 const key=keyboard[e.key];if(!key||e.ctrlKey||e.altKey||e.metaKey||!labState.health?.instance?.running)return;const b=document.querySelector(`[data-lab-key="${key}"]`);if(b?.disabled)return;
 e.preventDefault();labPress('keyboard:'+e.code,key);
};
lab('controls').onkeyup=e=>{const source='keyboard:'+e.code;if(labHeld.has(source)){e.preventDefault();labLift(source);}};
lab('controls').addEventListener('focusout',e=>{if(!lab('controls').contains(e.relatedTarget))labRelease();});
window.addEventListener('blur',labRelease);document.addEventListener('visibilitychange',()=>{if(document.hidden)labRelease();});
window.addEventListener('hashchange',()=>{if(location.hash==='#lab'){labSources();labRefresh();}else labRelease();});
setInterval(()=>{if(location.hash==='#lab'&&!document.hidden)labRefresh();},2500);setInterval(labFrame,250);labRefresh();
