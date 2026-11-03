"use strict";
// Full file backups (server-side jobs) and SIS inventory. All text goes through textContent.
const bk=id=>document.getElementById(id);
let backupJob=null,restoreId=null,lastPlan=null,backupRows=[];
const jobRunning=()=>(state.jobs||[]).some(j=>j.status==='running');
function fmtBytes(n){if(n===null||n===undefined)return '—';const u=['Б','КиБ','МиБ','ГиБ','ТиБ'];let i=0,v=Number(n);while(v>=1024&&i<u.length-1){v/=1024;i++;}return (i?v.toFixed(v<10?1:0):v)+' '+u[i];}
function fmtDate(iso){return iso?iso.replace('T',' ').replace(/\+00:00$/,'').slice(0,16):'—';}
function badge(text,kind){return el('span','badge '+kind,text);}
async function phoneJob(payload){
  const r=await request('POST','/api/run',payload);backupJob=r.id;await refresh();return r;
}
function backupBusy(fn){return async()=>{try{await fn();}catch(e){bk('backup-status').textContent=e.message;bk('backup-status').classList.add('error-text');notify(e.message);}};}
function updateBackupButtons(){
  const busy=jobRunning();
  bk('backup-create').disabled=busy||!bk('backup-device').value;
  const target=bk('restore-device').value;
  bk('restore-plan').disabled=busy||!restoreId||!target;
  bk('restore-apply').disabled=busy||!lastPlan||!lastPlan.ok||lastPlan.key!==planKey()||lastPlan.new<1;
  bk('inventory-scan').disabled=!bk('inventory-device').value;
  for(const b of document.querySelectorAll('#backup-rows button'))b.disabled=busy;
}
function planKey(){return [restoreId,bk('restore-device').value,bk('restore-only').value.trim()].join('|');}
function describe(job){
  const r=job.report,d=r&&r.data||{};
  if(job.status==='running')return 'Выполняется…';
  if(job.status!=='success'){
    const failed=(r&&r.checks||[]).filter(c=>c.status==='fail').map(c=>c.message);
    return 'Не удалось: '+(failed[0]||job.output.split('\n').filter(Boolean).slice(-1)[0]||job.status);
  }
  if(job.command.includes('backup create'))return `Копия создана: ${d.files} файл(ов), ${fmtBytes(d.bytes)}`+(d.complete?'. Проверена чтением обратно.':'. НЕПОЛНАЯ: часть элементов пропущена (см. отчёт в «Операциях»).');
  if(job.command.includes('backup verify'))return d.verify&&d.verify.ok?`Проверено: ${d.verify.checked} файл(ов), хеши совпадают.`:'Проверка выявила проблемы: '+JSON.stringify({missing:(d.verify||{}).missing,mismatched:(d.verify||{}).mismatched}).slice(0,200);
  if(job.command.includes('backup restore')){const x=d.restore;if(!x)return 'Готово';const p=x.plan;
    return x.applied?`Записано ${x.written}, проверено ${x.verified}`+(x.failed.length?`; ошибок: ${x.failed.length}`:'.'):`План: новых ${p.new}, совпадают ${p.identical}, конфликтов ${p.conflict}, заблокировано ${p.blocked}.`;}
  return 'Готово';
}
function renderBackups(snapshot){
  backupRows=snapshot.backups||[];
  bk('backup-free').textContent=fmtBytes(snapshot.backup_free);
  bk('backup-count').textContent=backupRows.length+' шт.';
  bk('backup-empty').hidden=backupRows.length>0;
  const tbody=bk('backup-rows');tbody.replaceChildren();
  for(const b of backupRows){
    const tr=el('tr');
    tr.append(el('td','',fmtDate(b.created)),el('td','',b.label||b.id),el('td','',b.files===null?'—':String(b.files)),el('td','',fmtBytes(b.bytes)));
    const st=el('td');
    if(b.state!=='ready')st.append(badge(b.state==='incomplete'?'Прервана':'Нечитаема','bad'));
    else{st.append(b.complete?badge('Полная','ok'):badge('Неполная ('+b.skipped+' пропущено)','warn'));if(!b.manifest_ok){st.append(' ',badge('манифест изменён','bad'));}}
    tr.append(st);
    const act=el('td','actions');
    if(b.state==='ready'){
      const v=el('button','btn ghost small','Проверить');v.onclick=backupBusy(async()=>{await phoneJob({action:'phone.backup.verify',id:b.id});});
      const r=el('button','btn ghost small','Восстановить…');r.onclick=()=>openRestore(b);
      act.append(v,r);
    }
    const d=el('button','btn ghost small','Удалить');d.onclick=backupBusy(async()=>{
      if(!confirm('Удалить копию '+b.id+' с сервера? Данные на телефоне не затрагиваются.'))return;
      await request('POST','/api/backups',{action:'delete',id:b.id,confirm:true});if(restoreId===b.id)closeRestore();await refresh();});
    act.append(d);tr.append(act);tbody.append(tr);
  }
  const running=(snapshot.jobs||[]).find(j=>j.status==='running'&&String(j.command).includes('backup'));
  const box=bk('backup-progress');box.hidden=!running;
  if(running){
    const p=running.progress;
    if(p&&p.bytes_total){bk('backup-bar').value=Math.min(100,100*p.bytes/p.bytes_total);bk('backup-progress-text').textContent=`${p.done} / ${p.total} файлов · ${fmtBytes(p.bytes)} из ${fmtBytes(p.bytes_total)}`;}
    else{bk('backup-bar').removeAttribute('value');bk('backup-progress-text').textContent='Выполняется…';}
  }
  const mine=backupJob&&(snapshot.jobs||[]).find(j=>j.id===backupJob);
  if(mine&&mine.status!=='running'){
    const text=describe(mine);const isRestore=mine.command.includes('backup restore');
    const out=isRestore?bk('restore-result'):bk('backup-status');
    out.textContent=text;out.classList.toggle('error-text',mine.status!=='success');
    if(isRestore&&mine.status==='success'&&mine.report&&mine.report.data.restore){
      const x=mine.report.data.restore;lastPlan=x.applied?null:{ok:true,new:x.plan.new,key:planKey()};
    }else if(isRestore)lastPlan=null;
    notify(text);backupJob=null;
  }
  updateBackupButtons();
}
function openRestore(b){restoreId=b.id;lastPlan=null;bk('restore-name').textContent=b.id;bk('backup-restore').hidden=false;
  bk('restore-result').textContent='Сначала покажите план: существующие файлы не перезаписываются и ничего не удаляется.';bk('restore-result').classList.remove('error-text');updateBackupButtons();bk('backup-restore').scrollIntoView({block:'nearest'});}
function closeRestore(){restoreId=null;lastPlan=null;bk('backup-restore').hidden=true;}
bk('backup-create').onclick=backupBusy(async()=>{
  bk('backup-status').classList.remove('error-text');
  if(!confirm('Создать полную копию файлов накопителя '+bk('backup-device').value+'? Копирование может занять много времени; пока оно идёт, другие операции недоступны.'))return;
  await phoneJob({action:'phone.backup.create',device:bk('backup-device').value});
});
bk('restore-close').onclick=closeRestore;
bk('restore-plan').onclick=backupBusy(async()=>{
  bk('restore-result').classList.remove('error-text');lastPlan=null;
  await phoneJob({action:'phone.backup.restore',id:restoreId,device:bk('restore-device').value,only:bk('restore-only').value.trim()||undefined});
});
bk('restore-apply').onclick=backupBusy(async()=>{
  if(!lastPlan||lastPlan.key!==planKey())throw new Error('Сначала покажите план для этих параметров');
  if(!confirm(`Записать ${lastPlan.new} новых файл(ов) на ${bk('restore-device').value}? Существующие файлы не изменяются.`))return;
  await phoneJob({action:'phone.backup.restore',id:restoreId,device:bk('restore-device').value,only:bk('restore-only').value.trim()||undefined,apply:true,confirm:true});
});
for(const id of ['backup-device','restore-device','inventory-device'])bk(id).addEventListener('change',updateBackupButtons);
bk('restore-only').addEventListener('input',updateBackupButtons);
window.addEventListener('symport-devices',()=>setTimeout(updateBackupButtons,0));

// ---- SIS inventory (files on the volume; installed state is not observable)
bk('inventory-scan').onclick=async()=>{
  const out=bk('inventory-status');out.classList.remove('error-text');out.textContent='Поиск…';bk('inventory-scan').disabled=true;
  try{
    const r=await dmCall({action:'apps-inventory',device:bk('inventory-device').value});
    const tbody=bk('inventory-rows');tbody.replaceChildren();
    for(const p of r.packages){
      const tr=el('tr');tr.append(el('td','',p.path),el('td','',p.name||'—'),el('td','',p.uid+(p.uid_class==='test'?' (тест)':'')),el('td','',p.version||'—'));
      const sig=el('td');sig.append(p.signed?badge('Подписан','ok'):badge('Не подписан','warn'));
      const chk=el('td');chk.append(p.checksums_ok?badge('CRC ✓','ok'):badge('CRC ✗','bad'));
      tr.append(sig,chk);tbody.append(tr);
    }
    const dups=Object.keys(r.duplicates_by_uid||{}).length;
    out.textContent=`Найдено пакетов: ${r.packages.length}`+(r.unreadable.length?`; нечитаемых: ${r.unreadable.length}`:'')+(dups?`; повторяющихся UID: ${dups}`:'')+'. Установленное состояние на телефоне отсюда не видно.';
  }catch(e){out.textContent=e.message;out.classList.add('error-text');}
  finally{updateBackupButtons();}
};
updateBackupButtons();
refresh();
