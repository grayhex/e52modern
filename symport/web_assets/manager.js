"use strict";
const dm = id => document.getElementById('dm-'+id);
const dmCall = async data => request('POST','/api/manager', data);
let dmDevices=[];
const dmPath = name => [dm('path').value.replace(/\/$/,''),name].filter(Boolean).join('/');
async function dmRun(fn){
  try { await fn(); } catch(e) {dm('status').textContent=e.message;notify(e.message);}
}
async function dmList(){
  const r=await dmCall({action:'list',device:dm('device').value,path:dm('path').value});
  dm('files').replaceChildren();
  for(const item of r.entries){
    const row=el('div','form-row');
    row.append(el('span','grow',`${item.directory?'▸':'·'} ${item.name} ${item.size===null?'':item.size+' B'}`));
    const open=el('button','btn ghost',item.directory?'Открыть':'Скачать');
    open.onclick=()=>dmRun(async()=>{
      if(item.directory){dm('path').value=dmPath(item.name);await dmList();return;}
      const file=await dmCall({action:'download',device:dm('device').value,path:dmPath(item.name)});
      const bytes=Uint8Array.from(atob(file.content),c=>c.charCodeAt(0));
      const url=URL.createObjectURL(new Blob([bytes]));
      const a=el('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    const del=el('button','btn ghost','Удалить');
    del.onclick=()=>dmRun(async()=>{if(!confirm('Удалить '+item.name+'? Каталог должен быть пустым.'))return;
      await dmCall({action:'delete',device:dm('device').value,path:dmPath(item.name),confirm:true});await dmList();});
    if(!item.directory&&/\.sisx?$/i.test(item.name)){const inspect=el('button','btn ghost','Certificate Inspector');inspect.onclick=()=>inspectChoose('device',null,null,dm('device').value,dmPath(item.name));row.append(inspect);}
    row.append(open,del);dm('files').append(row);
  }
}
dm('list').onclick=()=>dmRun(dmList);
dm('discover').onclick=()=>dmRun(async()=>{
  const previous=dm('device').value;const r=await dmCall({action:'discover'});dmDevices=r.devices;dm('device').replaceChildren();
  for(const d of r.devices){const opt=el('option','',d.id+(d.connected?' · подключён':' · отключён'));opt.value=d.id;dm('device').append(opt);}
  const preferred=r.devices.find(d=>d.id===previous)||r.devices.find(d=>d.connected&&d.capabilities.includes('personal-data'))||r.devices[0];if(preferred)dm('device').value=preferred.id;
  dm('status').textContent=r.devices.length?'Список обновлён.':'Телефон не подключён. Подключите карту памяти или настройте PC Bridge на ПК с телефоном по инструкции подключения.';
  dmSelection();
  dm('capabilities').replaceChildren();
  const descriptions={contacts:['Контакты','Нужен проверенный адаптер Gammu, SyncML или E52 Agent.'],sms:['SMS','Нужен транспорт с подтверждённым чтением и отправкой SMS.'],applications:['Приложения','Режим накопителя не предоставляет реестр установленных приложений.'],backup:['Копии файлов','Полная копия накопителя — раздел «Резервные копии»; контакты, сообщения и прошивка не входят.'],calendar:['Календарь','Чтение и экспорт через Gammu; доступ зависит от выбранного драйвера.'],bluetooth:['Bluetooth','Сопряжение и проверка доступных сервисов выполняются на ПК с телефоном.']};
  for(const name of Object.keys(r.limitations)){const item=descriptions[name];if(!item)continue;const p=el('p');p.append(el('strong','',item[0]+': '),document.createTextNode(item[1]));dm('capabilities').append(p);}
});
async function dmUpload(action){
 const file=dm('upload').files[0];if(!file)throw new Error('Выберите файл');
 if(file.size>8*1024*1024)throw new Error('Максимальный размер — 8 МиБ');
 if(!confirm('Передать '+file.name+'? Это не установка приложения.'))return;
 const bytes=new Uint8Array(await file.arrayBuffer());let raw='';for(const b of bytes)raw+=String.fromCharCode(b);
 const r=await dmCall({action,device:dm('device').value,path:dmPath(file.name),content:btoa(raw),confirm:true});
 dm('status').textContent=r.status;await dmList();
}
dm('send').onclick=()=>dmRun(()=>dmUpload('upload'));
dm('sis').onclick=()=>dmRun(()=>dmUpload('transfer'));
dm('mkdir').onclick=()=>dmRun(async()=>{if(!confirm('Создать каталог?'))return;await dmCall({action:'mkdir',device:dm('device').value,path:dmPath(dm('dir').value),confirm:true});await dmList();});
dm('history').onclick=()=>dmRun(async()=>{const r=await dmCall({action:'history'});dm('log').replaceChildren(...r.operations.reverse().map(x=>el('p','',`${x.time} · ${x.action} · ${x.status}`)));});
let dmRestore=null;
dm('backup').onclick=()=>dmRun(async()=>{
 const file=await dmCall({action:'backup',device:dm('device').value,path:dm('path').value});
 const url=URL.createObjectURL(new Blob([Uint8Array.from(atob(file.content),c=>c.charCodeAt(0))],{type:'application/zip'}));
 const link=el('a');link.href=url;link.download=file.name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
dm('preview').onclick=()=>dmRun(async()=>{
 dmRestore=null;dm('restore').disabled=true;
 const file=dm('archive').files[0];if(!file||file.size>8*1024*1024)throw new Error('Выберите ZIP до 8 МиБ');
 let raw='';for(const b of new Uint8Array(await file.arrayBuffer()))raw+=String.fromCharCode(b);
 const data={device:dm('device').value,path:dm('path').value,content:btoa(raw)};
 const preview=await dmCall({...data,action:'restore-preview'});
 dm('changes').textContent=JSON.stringify(preview.changes,null,2);
 dmRestore={...data,preview_sha256:preview.sha256};
 dm('restore').disabled=preview.changes.some(x=>x.conflict)||!preview.changes.length;
});
dm('restore').onclick=()=>dmRun(async()=>{
 if(!dmRestore||!confirm('Восстановить показанные файлы в '+dmRestore.device+'/'+dmRestore.path+'?'))return;
 await dmCall({...dmRestore,action:'restore',confirm:true});dmRestore=null;dm('restore').disabled=true;await dmList();
});

function dmSelection(){
 window.dispatchEvent(new CustomEvent('symport-devices',{detail:dmDevices}));
 const device=dmDevices.find(d=>d.id===dm('device').value);
 for(const name of ['list','send','sis','mkdir','backup','preview'])dm(name).disabled=!device?.capabilities.includes('files');
 dm('info').replaceChildren();
 if(window.renderPhoneDashboard){renderPhoneDashboard(device);return;}
 if(!device)return;
 const details=el('div','kv-row');
 const fields=[['Подключение',device.connected?'Доступно':'Отключено'],['Транспорт',device.transport],['Модель',device.model||'не определена'],['RM',device.rm||'не определён'],['Прошивка',device.firmware||'не определена'],['Батарея',device.battery??'нет данных'],['Свободно',device.free===null||device.free===undefined?'нет данных':(device.free/1024/1024).toFixed(0)+' МиБ']];
 for(const [label,value] of fields){const item=el('span');item.append(el('b','',label+':'),document.createTextNode(String(value)));details.append(item);}
 dm('info').append(details);dm('files').replaceChildren();
}
dm('device').onchange=dmSelection;
dmSelection();
