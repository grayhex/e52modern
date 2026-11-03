"use strict";
const suite=id=>document.getElementById(id);
let contactRows=[],selectedContacts=new Set(),contactPage=0;
const pageSize=50;
function readFileBase64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('Не удалось прочитать файл'));reader.onload=()=>resolve(reader.result.split(',')[1]);reader.readAsDataURL(file);});}
function saveBase64(data,name,type){const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type}));const a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function suiteBusy(button,output,fn){output.classList.remove('error-text');button.disabled=true;const original=button.textContent;button.textContent='Выполняется…';output.setAttribute('aria-busy','true');try{await fn();}catch(error){output.textContent=error.message;output.classList.add('error-text');notify(error.message);}finally{button.textContent=original;button.disabled=false;output.removeAttribute('aria-busy');suiteAvailability();}}
const discover=()=>dm('discover').click();
if(suite('suite-discover'))suite('suite-discover').onclick=discover;
for(const button of document.querySelectorAll('.suite-discover'))button.onclick=discover;
function suiteDevices(devices){
 for(const select of document.querySelectorAll('.suite-device')){
  const value=select.value;select.replaceChildren();
  const placeholder=el('option','','Выберите подключённый телефон');placeholder.value='';select.append(placeholder);
  for(const device of devices.filter(d=>(d.connected||(d.configured&&select.dataset.transferOnly))&&(!select.dataset.filesOnly||d.capabilities.includes('files'))&&(!select.dataset.transferOnly||d.capabilities.includes('transfer'))&&(!select.dataset.mediaOnly||d.capabilities.includes('media-read'))&&(!select.dataset.capability||(d.capabilities.includes(select.dataset.capability)||(select.dataset.capability==='calendar-read'&&d.capabilities.includes('tasks-read')))))){
   const option=el('option','',(device.name||device.model||device.id)+' · '+tr(device.configured&&!device.connected?'Configured':device.connection_kind||device.transport));option.value=device.id;option.dataset.capabilities=JSON.stringify(device.capabilities);select.append(option);
  }
  if([...select.options].some(o=>o.value===value))select.value=value;
  if(!select.value&&select.options.length===2)select.selectedIndex=1;
 }
 suiteAvailability();
}
function chosenCapabilities(){const option=suite('contacts-device').selectedOptions[0];return JSON.parse(option?.dataset.capabilities||'[]');}
function suiteAvailability(){
 const caps=chosenCapabilities();
 suite('contacts-send').disabled=!selectedContacts.size||!caps.some(c=>['contacts-stage','contacts-import'].includes(c));
 suite('contacts-read').disabled=!caps.includes('contacts-read');
 for(const kind of ['media','software']){const d=dmDevices.find(d=>d.id===suite(kind+'-device').value);suite(kind+'-send').disabled=!d?.capabilities.includes('transfer');const opp=d?.capabilities.includes('opp-push');suite(kind+'-path').disabled=!!opp;if(opp)suite(kind+'-path').value='';}
 const catalogDevice=dmDevices.find(d=>d.id===suite('catalog-device').value);if(suite('catalog-path')){const opp=catalogDevice?.capabilities.includes('opp-push');suite('catalog-path').disabled=!!opp;if(opp)suite('catalog-path').value='';}if(suite('catalog-transport-note'))suite('catalog-transport-note').textContent=tr(catalogDevice?.capabilities.includes('opp-push')?'OPP reports receiver acceptance only. Open the package in the phone inbox to install it.':catalogDevice?.capabilities.includes('files-stage')?'FTP transfers are saved in a new SymPort folder and checked by SHA-256 read-back.':'Available free space and file SHA-256 are checked where the transport supports them. Installation is confirmed on the phone.');
 const mediaDevice=dmDevices.find(d=>d.id===suite('media-device').value);if(suite('gallery-read'))suite('gallery-read').disabled=!mediaDevice?.capabilities.includes('media-read');if(mediaDevice&&!mediaDevice.capabilities.includes('media-read'))suite('gallery-status').textContent=tr('Gallery is unavailable through this transport. Use File Manager to download exposed files.');
}
window.addEventListener('symport-devices',event=>suiteDevices(event.detail));
for(const select of document.querySelectorAll('.suite-device'))select.onchange=suiteAvailability;
suiteDevices(dmDevices);
function selectedRows(){return contactRows.filter((_,i)=>selectedContacts.has(i));}
function contactCount(){suite('contacts-count').textContent=`${selectedContacts.size} / ${contactRows.length} ВЫБРАНО`;suiteAvailability();}
function renderContacts(){
 const query=suite('contacts-search').value.toLocaleLowerCase();
 const visible=contactRows.map((row,index)=>({row,index})).filter(({row,index})=>(!window.contactDuplicateIndexes||window.contactDuplicateIndexes.has(index))&&[row.name,...row.phones,...row.emails].join(' ').toLocaleLowerCase().includes(query));
 const pages=Math.max(1,Math.ceil(visible.length/pageSize));contactPage=Math.min(contactPage,pages-1);
 const tbody=suite('contacts-rows');tbody.replaceChildren();
 for(const {row,index} of visible.slice(contactPage*pageSize,(contactPage+1)*pageSize)){
  const tr=el('tr');const td=el('td');const checkbox=el('input');checkbox.type='checkbox';checkbox.checked=selectedContacts.has(index);checkbox.setAttribute('aria-label','Выбрать '+row.name);checkbox.onchange=()=>{if(checkbox.checked)selectedContacts.add(index);else selectedContacts.delete(index);contactCount();};td.append(checkbox);tr.append(td);
  for(const key of ['name','phones','emails']){
   const cell=el('td');const input=el('input');input.value=key==='name'?row.name:row[key].join('; ');input.setAttribute('aria-label',`${key==='name'?'Имя':key==='phones'?'Телефоны':'Email'}: ${row.name}`);
   input.onchange=()=>{if(key==='name'){row.name=input.value;row.given=input.value;row.family='';}else row[key]=input.value.split(';').map(x=>x.trim()).filter(Boolean);};cell.append(input);tr.append(cell);
  }
  tbody.append(tr);
 }
 const footer=suite('contacts-pagination')||el('div','form-row');footer.id='contacts-pagination';footer.replaceChildren();
 const prev=el('button','btn ghost','← Назад'),next=el('button','btn ghost','Далее →');prev.disabled=contactPage===0;next.disabled=contactPage===pages-1;prev.onclick=()=>{contactPage--;renderContacts();};next.onclick=()=>{contactPage++;renderContacts();};footer.append(prev,el('span','muted',`Страница ${contactPage+1} из ${pages} · Найдено ${visible.length}`),next);suite('contacts-rows').closest('.table-scroll').after(footer);contactCount();
}
function setContacts(rows,warnings=[]){window.contactDuplicateIndexes=null;contactRows=rows;selectedContacts=new Set(rows.map((_,i)=>i));contactPage=0;suite('contacts-workspace').hidden=false;suite('contacts-warnings').textContent=warnings.join(' ');renderContacts();}
suite('contacts-preview').onclick=()=>suiteBusy(suite('contacts-preview'),suite('contacts-status'),async()=>{
 const file=suite('contacts-file').files[0];if(!file||file.size>4*1024*1024)throw new Error('Выберите CSV или vCard до 4 МиБ');
 const result=await request('POST','/api/contacts',{action:'preview',name:file.name,content:await readFileBase64(file)});
 setContacts(result.contacts,result.warnings);suite('contacts-status').textContent=`Файл прочитан: ${result.contacts.length} контактов. Проверьте выбор перед переносом.`;
});
suite('contacts-clear').onclick=()=>{contactRows=[];selectedContacts.clear();suite('contacts-rows').replaceChildren();suite('contacts-workspace').hidden=true;suite('contacts-file').value='';suite('contacts-result').textContent='';suite('contacts-status').textContent='Контакты удалены из текущего просмотра.';suiteAvailability();};
suite('contacts-search').oninput=()=>{contactPage=0;renderContacts();};
suite('contacts-select-all').onclick=()=>{if(selectedContacts.size===contactRows.length)selectedContacts.clear();else selectedContacts=new Set(contactRows.map((_,i)=>i));renderContacts();};
for(const [id,key,name,type] of [['contacts-export','vcard','contacts.vcf','text/vcard'],['contacts-zip','zip','contacts-vcards.zip','application/zip']]){
 suite(id).onclick=()=>suiteBusy(suite(id),suite('contacts-status'),async()=>{const data=await request('POST','/api/contacts',{action:'export',contacts:selectedRows()});saveBase64(data[key],name,type);});
}
suite('contacts-read').onclick=()=>suiteBusy(suite('contacts-read'),suite('contacts-result'),async()=>{
 const result=await dmCall({action:'contacts-read',device:suite('contacts-device').value});
 setContacts(result.contacts,['Получено через Gammu с телефона. Этот просмотр не выполняет синхронизацию.']);suite('contacts-result').textContent=`Прочитано контактов: ${result.contacts.length}`;
});
suite('contacts-send').onclick=()=>suiteBusy(suite('contacts-send'),suite('contacts-result'),async()=>{
 const direct=chosenCapabilities().includes('contacts-import');const contacts=selectedRows();
 if(!confirm(direct?`Добавить ${contacts.length} контактов в телефонную книгу? Сначала сохраните резервную копию. Существующие записи не удаляются.`:`Передать ${contacts.length} vCard на карту? После передачи откройте их на Nokia и сохраните в Контакты.`))return;
 const result=await dmCall({action:direct?'contacts-import':'contacts-stage',device:suite('contacts-device').value,path:'',contacts,confirm:true});
 suite('contacts-result').textContent=direct?(result.status==='verified-in-phonebook'?`Подтверждено чтением с телефона: ${result.verified} контактов. Пропущено: ${result.skipped}.`:result.status==='already-present'?'Выбранные контакты уже найдены в телефонной книге.':`Результат требует проверки: подтверждено ${result.verified} из ${result.requested}. Не повторяйте импорт автоматически.`):`Передано vCard: ${result.count}. Папка: ${result.folder}. Откройте файлы на телефоне и сохраните контакты — импорт в книгу ещё не подтверждён.`;
});
for(const kind of ['media','software'])suite(kind+'-send').onclick=()=>suiteBusy(suite(kind+'-send'),suite(kind+'-result'),async()=>{
 const files=[...suite(kind+'-files').files];if(!files.length)throw new Error('Выберите файлы для передачи');
 const limit=(kind==='media'?64:32)*1024*1024;for(const file of files)if(file.size>limit)throw new Error(`Файл ${file.name} превышает лимит`);
 if(!confirm(`Передать файлов: ${files.length} на ${suite(kind+'-device').value}? ${kind==='software'?'Установка будет выполнена на телефоне.':'Назначение мелодии и воспроизведение выполняются на телефоне.'}`))return;
 let completed=0;const destinations=[];
 for(const file of files){
  suite(kind+'-result').textContent=`Передача ${completed+1} / ${files.length}: ${file.name}`;
  try{const sent=await dmCall({action:kind==='media'?'media-upload':'software-transfer',device:suite(kind+'-device').value,path:[suite(kind+'-path').value.replace(/\/$/,''),file.name].filter(Boolean).join('/'),content:await readFileBase64(file),kind:kind==='media'?suite('media-kind').value:undefined,confirm:true});completed++;if(sent.destination)destinations.push(sent.destination);}
  catch(error){throw new Error(`Передано ${completed} из ${files.length}. ${error.message}`);}
 }
 suite(kind+'-result').textContent=kind==='software'?`Передано пакетов: ${completed}. Откройте их на Nokia и подтвердите установку. Подтвердите установку на телефоне.`:`Передано файлов: ${completed}. Проверьте воспроизведение на телефоне.`;if(destinations.length)suite(kind+'-result').append(document.createTextNode(' '+destinations.join(' · ')));
});
for(const zone of document.querySelectorAll('.upload-zone')){
 const input=zone.querySelector('input[type=file]');if(!input)continue;
 const prompt=el('span','upload-prompt','Выберите файл или перетащите сюда');input.before(prompt);
 input.onchange=()=>{prompt.textContent=[...input.files].map(f=>f.name).join(', ')||'Выберите файл или перетащите сюда';};
 zone.addEventListener('dragover',event=>{event.preventDefault();zone.classList.add('dragging');});
 zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));
 zone.addEventListener('drop',event=>{event.preventDefault();zone.classList.remove('dragging');const files=event.dataTransfer.files;if(!input.multiple&&files.length>1){notify('Выберите один файл экспорта');return;}input.files=files;input.dispatchEvent(new Event('change'));});
}
