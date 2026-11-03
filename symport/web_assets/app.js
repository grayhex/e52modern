"use strict";
const token = document.querySelector('meta[name="symport-token"]').content;
const pages = {manager:"Телефон и файлы",catalog:"Каталог приложений",media:"Музыка и видео",contacts:"Контакты",calendar:"Календарь",messages:"Сообщения",backups:"Резервные копии",installed:"Приложения телефона",overview:"Обзор",themes:"Темы E52 CLEAR",apps:"Разработка",device:"Телефон и тесты",activity:"История операций"};
const checklistLabels = {
  identify:"Модель, RM-код и версия прошивки",
  backup:"Резервная копия и возврат к штатной теме",
  transfer:"SIS передан на телефон",
  install:"SIS успешно установлен",
  activate:"Тема применена",
  standby:"Active Standby, индикаторы и softkeys",
  menus:"Меню 3×4, выделение и навигация",
  dialogs:"Диалоги и поля ввода",
  apps:"Заметки, Календарь, Сообщения, Калькулятор",
  restart:"Перезагрузка и повторная проверка",
  uninstall:"Удаление темы и возврат к стандартной"
};
const statuses = [["pending","Не проверено"],["pass","Пройдено"],["fail","Ошибка"],["not-applicable","Не применимо"]];
let state = {packages:[],projects:[],jobs:[]};
let checklistInitialized = false;
let activeJob = null;
const expandedJobs = new Set();
let toastTimeout;

function el(tag, classes, text){
  const n = document.createElement(tag);
  if(classes) n.className = classes;
  if(text !== undefined) n.textContent = text;
  return n;
}
function clear(node){node.replaceChildren()}
function notify(message){
  const n=document.getElementById("toast");
  n.textContent=message;n.classList.add("visible");
  clearTimeout(toastTimeout);
  toastTimeout=setTimeout(()=>n.classList.remove("visible"),5300);
}
function navigate(){
  const requested=(location.hash||"#manager").slice(1);
  const current=pages[requested]?requested:"manager";
  for(const p of document.querySelectorAll(".page"))p.classList.toggle("visible",p.id===current);
  for(const n of document.querySelectorAll("[data-nav]"))n.classList.toggle("active",n.dataset.nav===current);
  document.getElementById("page-label").textContent=pages[current];
}
window.addEventListener("hashchange",navigate);
navigate();

async function request(method,url,body){
  const options={method,cache:"no-store"};
  if(body!==undefined){
    options.headers={"Content-Type":"application/json","X-Symport-Token":token};
    options.body=JSON.stringify(body);
  }
  const response=await fetch(url,options);
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||"Ошибка HTTP "+response.status);
  return data;
}
async function run(action,values={}){
  const btns=document.querySelectorAll("[data-action]");
  for(const b of btns)b.disabled=true;
  try{
    const result=await request("POST","/api/run",{action,...values});
    activeJob=result.id;
    notify("Запущено: "+action+". Результат появится в истории операций.");
    await refresh();
  }catch(err){notify(err.message)}
  finally{for(const b of btns)b.disabled=false}
}
function selectedPackage(){
  return document.getElementById("selected-package").value;
}
function selector(){
  return document.getElementById("device-selector").value.trim();
}
document.addEventListener("click",async event=>{
  const jump=event.target.closest("[data-jump]");
  if(jump){location.hash=jump.dataset.jump;return}
  const button=event.target.closest("button[data-action]");
  if(!button)return;
  const action=button.dataset.action;
  const values={};
  if(button.dataset.variant)values.variant=button.dataset.variant;
  if(button.dataset.project)values.project=button.dataset.project;
  if(action==="app.init")values.project=document.getElementById("new-project").value.trim();
  if(action==="theme.package"){
    values.backend=document.getElementById("backend-"+values.variant).value;
    if(values.backend==="native" && !confirm("Экспериментальный неподписанный SIS без зависимостей. Его установка и совместимость с E52 НЕ подтверждены. Продолжить?"))return;
  }
  if(["device.stage","device.info"].includes(action))values.selector=selector();
  if(["sis.inspect","device.stage","emulator.test"].includes(action)){
    values.package=selectedPackage();
    if(!values.package){notify("Сначала выбери пакет SIS");return}
  }
  if(action==="device.stage" && !confirm("Передача SIS на USB-устройство сервера. Это НЕ установка на Nokia. Продолжить?"))return;
  await run(action,values);
});
async function refresh(){
  try{
    state=await request("GET","/api/state");
    render();
    if(typeof renderLibrary === "function")renderLibrary(state);
    if(typeof renderBackups === "function")renderBackups(state);
  }catch(err){notify("Не удалось обновить данные: "+err.message)}
}
function downloadButton(item){
  const a=el("a","","Скачать ↓");
  a.href="/api/download?id="+encodeURIComponent(item.id);
  a.setAttribute("download",item.name);
  return a;
}
function itemRow(item){
  const row=el("div","package-row");
  const left=el("div");
  left.append(el("strong","",item.name),
              el("small","",item.source+" · "+(item.size/1024).toFixed(1)+" КБ · не проверено на E52"));
  row.append(left,downloadButton(item));
  return row;
}
function renderPackages(){
  const tp=document.getElementById("theme-packages");
  const ap=document.getElementById("app-packages");
  const all=document.getElementById("all-packages");
  for(const container of [tp,ap,all])clear(container);
  const theme=state.packages.filter(p=>p.kind==="theme");
  const apps=state.packages.filter(p=>p.kind==="app");
  if(!theme.length)tp.append(el("div","empty","Пока нет SIS. Собери и упакуй тему."));
  else theme.forEach(p=>tp.append(itemRow(p)));
  if(!apps.length)ap.append(el("div","empty","Пакеты приложений появятся после сборки."));
  else apps.forEach(p=>ap.append(itemRow(p)));
  if(!state.packages.length)all.append(el("div","empty","Готовых пакетов пока нет."));
  else state.packages.forEach(p=>all.append(itemRow(p)));
  const select=document.getElementById("selected-package");
  const previous=select.value;
  clear(select);
  select.append(new Option("Выбери пакет",""));
  for(const p of state.packages)select.append(new Option(p.name+" ("+p.source+")",p.id));
  if(state.packages.some(p=>p.id===previous))select.value=previous;
}
function renderProjects(){
  const box=document.getElementById("projects");
  const names=state.projects||[];
  clear(box);
  document.getElementById("project-count").textContent=names.length+" проект(ов)";
  if(!names.length){box.className="empty";box.textContent="Пока нет проектов. Создай первый выше.";return}
  box.className="project-list";
  for(const name of names){
    const row=el("div","project-row");
    const detail=el("div");
    detail.append(el("strong","",name),el("small","","workspace/"+name));
    const actions=el("div","project-actions");
    for(const [action,label] of [["app.build","Собрать"],["app.inspect","Инспектор"],["app.analyze","Совместимость"],["app.package","SIS"]]){
      const button=el("button","btn ghost",label);
      button.dataset.action=action;button.dataset.project=name;actions.append(button);
    }
    row.append(detail,actions);box.append(row);
  }
}
function renderDoctor(){
  const last=state.jobs.find(j=>j.action==="doctor"&&j.report);
  if(!last)return;
  const label=document.getElementById("doctor-status");
  label.textContent=last.status==="success"?"Проверено окружение":"Есть ограничения";
  const box=document.getElementById("doctor-detail");
  clear(box);box.className="";
  const tools=last.report?.data?.tools||[];
  if(tools.length){
    for(const tool of tools){
      const row=el("div","doctor-item");
      row.append(el("span","",tool.name||"?"),
                 el("span",tool.found?"ok":"bad",tool.found?"Обнаружен":"Не найден"));
      box.append(row);
    }
  }else box.append(el("div","empty","Подробности смотри в истории операций."));
}
function renderJobs(){
  const jobs=document.getElementById("jobs");
  clear(jobs);
  const running=state.jobs.some(j=>j.status==="running");
  document.getElementById("running").hidden=!running;
  if(!state.jobs.length){jobs.append(el("div","card empty","Операций пока не было."));return}
  for(const job of state.jobs){
    const card=el("article","job");
    const head=el("div","job-head");
    head.append(el("div","job-title",job.command),
                el("span","status "+job.status,job.status));
    card.append(head,el("p","",job.started+(job.exit_code===null?" · выполняется":" · код "+job.exit_code)));
    const details=el("details");
    details.open=expandedJobs.has(job.id)||(job.id===activeJob && job.status!=="running");
    details.addEventListener("toggle",()=>{if(details.open)expandedJobs.add(job.id);else expandedJobs.delete(job.id)});
    const summary=el("summary","",job.status==="running"?"Выполняется…":"Отчёт и вывод команды");
    const pre=el("pre","",job.output||"Нет сообщений от инструмента.");
    details.append(summary,pre);
    if(job.report){
      const reportStatus=job.report.verification||{};
      details.append(el("p","","Эмулятор: "+(reportStatus.emulator||"not-tested")+
                       " · Физический E52: "+(reportStatus.physical_device||"not-tested")));
    }
    card.append(details);jobs.append(card);
  }
  const latest=state.jobs[0];
  if(activeJob===latest?.id && latest.status!=="running"){
    notify(latest.status==="success"?"Операция завершена":"Результат: "+latest.status+
           ". Открой историю операций.");
    activeJob=null;
  }
}
function render(){
  renderPackages();renderProjects();renderDoctor();renderJobs();
  if(!checklistInitialized){buildChecklist(state.device_report);checklistInitialized=true}
}
function buildChecklist(report){
  const container=document.getElementById("device-steps");
  clear(container);
  document.getElementById("rm").value=report.rm||"";
  document.getElementById("firmware").value=report.firmware||"";
  document.getElementById("device-notes").value=report.notes||"";
  for(const [key,label] of Object.entries(checklistLabels)){
    const row=el("div","check-row");
    row.append(el("span","",label));
    const select=el("select");select.dataset.step=key;
    for(const [value,name] of statuses)select.append(new Option(name,value));
    select.value=report.steps?.[key]||"pending";
    row.append(select);container.append(row);
  }
}
document.getElementById("save-device-report").addEventListener("click",async ()=>{
  const steps={};
  for(const select of document.querySelectorAll("[data-step]"))steps[select.dataset.step]=select.value;
  try{
    await request("POST","/api/device-report",{
      rm:document.getElementById("rm").value.trim(),
      firmware:document.getElementById("firmware").value.trim(),
      notes:document.getElementById("device-notes").value,steps
    });
    notify("Ручной протокол сохранён. Это не автоматическая проверка телефона.");
  }catch(err){notify(err.message)}
});
refresh();
setInterval(refresh,1800);
