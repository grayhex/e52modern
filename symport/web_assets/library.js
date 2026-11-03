"use strict";
let libraryDraft=null;
const lib = name=>document.getElementById('library-'+name);
async function libPrepare(data){
 libraryDraft=await request('POST','/api/library',data);
 lib('preview').textContent=JSON.stringify(libraryDraft,null,2);lib('publish').disabled=false;
}
lib('import').onclick=()=>dmRun(async()=>{
 const file=lib('upload').files[0];if(!file||file.size>8*1024*1024)throw new Error('Выберите SIS/SISX до 8 МиБ');
 let raw='';for(const b of new Uint8Array(await file.arrayBuffer()))raw+=String.fromCharCode(b);
 await libPrepare({action:'import',name:file.name,content:btoa(raw)});
});
lib('prepare').onclick=()=>dmRun(()=>libPrepare({action:'prepare-build',package:lib('build').value}));
lib('publish').onclick=()=>dmRun(async()=>{
 if(!libraryDraft||!confirm('Опубликовать '+libraryDraft.name+' в локальной библиотеке? Совместимость с телефоном не подтверждена.'))return;
 await request('POST','/api/library',{action:'publish',id:libraryDraft.id,confirm:true});
 libraryDraft=null;lib('publish').disabled=true;await refresh();
});
function renderLibrary(snapshot){
 const selected=lib('build').value;lib('build').replaceChildren();
 for(const p of snapshot.packages.filter(p=>p.kind==='theme')){const o=el('option','',p.name);o.value=p.id;lib('build').append(o);}
 if([...lib('build').options].some(o=>o.value===selected))lib('build').value=selected;
 lib('items').replaceChildren();
 for(const p of snapshot.library||[]){
  const row=el('div','form-row');const a=el('a','text-link',p.name+' ↓');a.href='/api/library/download?id='+encodeURIComponent(p.id);
  row.append(a,el('span','muted',p.size+' B · На телефоне не проверено'));
  const send=el('button','btn secondary','Передать на телефон');send.onclick=()=>dmRun(async()=>{
   if(!confirm('Передать '+p.name+' на выбранный телефон? Это не установка.'))return;
   const response=await fetch(a.href);if(!response.ok)throw new Error('Не удалось скачать пакет');
   let raw='';for(const b of new Uint8Array(await response.arrayBuffer()))raw+=String.fromCharCode(b);
   await dmCall({action:'transfer',device:dm('device').value,path:dmPath(p.name),content:btoa(raw),confirm:true});notify('Пакет передан. Завершите установку на телефоне.');
  });const test=el('button','btn secondary','Проверить в эмуляторе');test.onclick=()=>labChoose('library',p.id,'theme');const inspect=el('button','btn ghost','Certificate Inspector');inspect.onclick=()=>inspectChoose('library',p.id);row.append(send,test,inspect);lib('items').append(row);
 }
}
