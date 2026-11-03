"use strict";
// Read-only calendar/to-do view through Gammu. Data lives only in this page's memory.
const cal=id=>document.getElementById(id);
let calendarData=null;
function calStatus(text,error){const n=cal('calendar-status');n.textContent=text;n.classList.toggle('error-text',!!error);}
function fmtWhen(v){return v?String(v).replace('T',' ').replace(/:00(?:\+00:00)?$/,''):'—';}
function calFilter(){
  if(!calendarData)return;
  const q=cal('calendar-search').value.toLocaleLowerCase();
  const hit=o=>Object.values(o).filter(v=>typeof v==='string').join(' ').toLocaleLowerCase().includes(q);
  const events=calendarData.events.filter(hit),todos=calendarData.todos.filter(hit);
  const eb=cal('calendar-events');eb.replaceChildren();
  for(const e of events){const tr=el('tr');tr.append(el('td','',fmtWhen(e.start)),el('td','',e.summary||'(без названия)'),el('td','',e.location||''));eb.append(tr);}
  const tb=cal('calendar-todos');tb.replaceChildren();
  for(const t of todos){const tr=el('tr');tr.append(el('td','',fmtWhen(t.due)),el('td','',t.summary||'(без названия)'),el('td','',t.status||''));tb.append(tr);}
  cal('calendar-count').textContent=`${events.length} / ${calendarData.events.length} событий · ${todos.length} / ${calendarData.todos.length} задач`;
}
function calButtons(){
  cal('calendar-read').disabled=!cal('calendar-device').value;
  cal('calendar-ics').disabled=!(calendarData&&calendarData.raw_ics);
  cal('calendar-json').disabled=!calendarData;
}
cal('calendar-read').onclick=async()=>{
  cal('calendar-read').disabled=true;calStatus('Чтение календаря через Gammu…');
  try{
    const r=await dmCall({action:'calendar-read',device:cal('calendar-device').value});
    calendarData=r;cal('calendar-workspace').hidden=false;calFilter();
    calStatus(r.status==='read'?`Прочитано: ${r.events.length} событий, ${r.todos.length} задач. Данные прочитаны с телефона.`
      :'Записей нет: пустой календарь или он не поддерживается этим телефоном/драйвером (отличить нельзя).',r.status!=='read');
  }catch(e){calendarData=null;cal('calendar-workspace').hidden=true;calStatus(e.message,true);}
  finally{calButtons();}
};
cal('calendar-ics').onclick=()=>{if(calendarData&&calendarData.raw_ics)saveBase64(calendarData.raw_ics,'e52-calendar.ics','text/calendar');};
cal('calendar-json').onclick=()=>{
  if(!calendarData)return;
  const {events,todos}=calendarData;
  const raw=btoa(unescape(encodeURIComponent(JSON.stringify({events,todos},null,1))));
  saveBase64(raw,'e52-calendar.json','application/json');
};
cal('calendar-search').oninput=calFilter;
cal('calendar-device').addEventListener('change',calButtons);
window.addEventListener('symport-devices',()=>setTimeout(calButtons,0));
calButtons();
