"use strict";
const cat=id=>document.getElementById('catalog-'+id);
let catState={apps:[],sets:{},jobs:[],research:[]},catSelected=new Set(),catCollection='',catPlan=null,catBusy=false;
const catStatuses={'verified-on-e52':'Проверено на E52','verified-on-s60':'Автор сообщает: S60','likely-compatible':'Подходит по профилю','untested':'Не проверено','unsupported':'Не поддерживается','unavailable':'Недоступно'};
const catStages={queued:'В очереди',downloading:'Загружается',downloaded:'Скачано',validated:'Проверено',transferred:'Передано','awaiting-installation':'Ожидает установки на Nokia','user-confirmed-installed':'Установлено · подтверждено пользователем',failed:'Ошибка',interrupted:'Прервано'};
const catNames={maps:'Карты и GPS',communication:'Общение',internet:'Интернет',system:'Система',documents:'Книги',multimedia:'Мультимедиа',games:'Игры',development:'Разработка','high-risk':'Повышенный риск'};
const catApi=data=>request('POST','/api/catalog',data);
function catError(e){cat('status').textContent=e.message;notify(e.message);}
async function catRefresh(){try{catState=await catApi({action:'list'});catRender();}catch(e){catError(e);}}
function catInvalidate(){catPlan=null;cat('download').disabled=true;cat('transfer').disabled=true;cat('plan-result').replaceChildren();catRenderSelection();}
function catEnableActions(){const blocked=catBusy||!catPlan||catPlan.problems.length||catState.jobs.some(j=>j.state==='running');cat('download').disabled=!!blocked;cat('transfer').disabled=!!blocked||!cat('device').value;}
window.addEventListener('symport-devices',catEnableActions);
cat('device').addEventListener('change',catEnableActions);
function catRenderSelection(){
 cat('selected').textContent=`${catSelected.size} ВЫБРАНО`;cat('selection').textContent=catState.apps.filter(a=>catSelected.has(a.id)).map(a=>a.name).join(' · ')||'Выберите программы в каталоге.';
}
function catVisible(){
 const query=cat('query').value.toLocaleLowerCase();
 return catState.apps.filter(a=>(a.category!=='high-risk'||cat('category').value==='high-risk')&&(a.name+' '+a.description).toLocaleLowerCase().includes(query)
 &&['category','compatibility','network','delivery'].every(k=>!cat(k).value||a[k]===cat(k).value)
 &&(!cat('format').value||a.format.startsWith(cat('format').value))
 &&(!catCollection||a.collection.includes(catCollection))
 &&(cat('profile').value==='all'||!['unsupported','unavailable'].includes(a.compatibility)));
}
function catSafeLink(url,text){const a=el('a','text-link',text);const parsed=new URL(url);if(parsed.protocol!=='https:')throw Error('Источник должен использовать HTTPS');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function catDetails(app){
 const content=cat('detail-content');content.replaceChildren(el('span','eyebrow',catNames[app.category]||app.category),el('h2','',app.name),el('p','',app.description));
 const facts=el('dl','device-details');for(const [label,value] of [['Версия',app.version],['Дата релиза',app.release_date||'Не опубликована'],['Разработчик',app.developer],['Платформы',app.platforms.join(', ')],['Совместимость',catStatuses[app.compatibility]],['Основание',app.compatibility_basis],['Проверка на E52',app.e52_evidence||'Не проводилась'],['Лицензия',app.license],['Распространение',app.redistribution],['Зависимости',app.dependencies.join(', ')||'Нет автоматических runtime-зависимостей'],['Внешние требования',app.backend],['TLS / сеть',app.tls],['Подпись',app.signature],['Проверено',app.checked_at]])facts.append(el('dt','muted',label),el('dd','',value));content.append(facts);
 for(const artifact of app.distribution||[]){const p=el('p','muted',`${artifact.name} · ${artifact.size} B · SHA-256: ${artifact.sha256}${artifact.publisher_sha256?' (опубликован источником)':' (вычислен при проверке источника)'}`);content.append(p);}
 for(const artifact of app.contained_packages||[])content.append(el('p','muted',`В архиве: ${artifact.name} · ${artifact.size} B · SHA-256: ${artifact.sha256}`));
 if(app.delivery_reason)content.append(el('p','note',app.delivery_reason));
 for(const url of app.sources){const p=el('p');p.append(catSafeLink(url,url));content.append(p);}
 content.append(el('p','note','После передачи откройте SIS/JAR на Nokia. Для JAR/JAD выбирайте дескриптор только при наличии связанного JAR. Успех установки фиксируется вашим подтверждением.'));
 cat('detail').showModal();
}
function catRenderGrid(){
 const visible=catVisible();cat('found').textContent=`${visible.length} приложений · ${visible.filter(a=>a.delivery==='automatic').length} с загрузкой`;
 cat('grid').replaceChildren();for(const app of visible){
  const card=el('article','catalog-app');const head=el('div','catalog-app-head');const icon=el('span','catalog-app-icon',app.name.slice(0,2).toUpperCase());icon.setAttribute('aria-hidden','true');head.append(icon);
  const checkbox=el('input');checkbox.type='checkbox';checkbox.checked=catSelected.has(app.id);checkbox.disabled=app.delivery!=='automatic'||app.category==='high-risk';checkbox.setAttribute('aria-label','Выбрать '+app.name);checkbox.onchange=()=>{if(checkbox.checked)catSelected.add(app.id);else catSelected.delete(app.id);catInvalidate();};head.append(checkbox);
  card.append(head,el('span','eyebrow',catNames[app.category]||app.category),el('h3','',app.name),el('p','catalog-description',app.description),el('p','muted',`${app.version} · ${app.format.toUpperCase()} · ${app.network==='offline'?'Офлайн':app.network==='mixed'?'Сеть + кэш':'Онлайн'}`),el('span','chip',catStatuses[app.compatibility]));
  const actions=el('div','form-row');const detail=el('button','btn ghost','Подробнее');detail.onclick=()=>catDetails(app);actions.append(detail);
  if(app.delivery==='manual'){actions.append(catSafeLink(app.manual_url,'Скачать вручную ↗'));const transfer=el('a','text-link','Передать свой пакет →');transfer.href='#installed';card.append(el('p','muted',app.delivery_reason),transfer);}
  const test=el('button','btn ghost','Проверить в эмуляторе');test.onclick=()=>labChoose(app.delivery==='automatic'?'catalog':'upload',app.id,'app');actions.append(test);
  card.append(actions);cat('grid').append(card);
 }
}
function catRenderJobs(){
 cat('jobs').replaceChildren();if(!catState.jobs.length){cat('jobs').textContent='Операций ещё не было.';return;}
 for(const job of catState.jobs){const box=el('div','catalog-job');box.append(el('h3','',`${job.action==='transfer'?'Передача':'Загрузка'} · ${new Date(job.created).toLocaleString('ru-RU')}`));if(job.error)box.append(el('p','error-text',job.error));
 for(const item of job.items){const row=el('div','catalog-result');row.append(el('strong','',catState.apps.find(a=>a.id===item.id)?.name||item.id),el('span','chip',catStages[item.stage]||item.stage));if(item.error)row.append(el('span','error-text',item.error));if(item.events?.length){const details=el('details');details.append(el('summary','muted','Этапы'));for(const event of item.events)details.append(el('p','muted',`${catStages[event.stage]||event.stage} · ${new Date(event.at).toLocaleTimeString('ru-RU')}`));row.append(details);}
 if(item.stage==='awaiting-installation'){const button=el('button','btn ghost','Я установил на телефоне');button.onclick=async()=>{if(!confirm('Вы вручную установили это приложение на Nokia и проверили запуск?'))return;try{await catApi({action:'confirm-installed',job:job.id,app:item.id,confirm:true});await catRefresh();}catch(e){catError(e);}};row.append(button);}box.append(row);}
 if(job.state==='completed'){const download=el('a','text-link','Скачать проверенный набор ZIP ↓');download.href='/api/catalog/archive?id='+encodeURIComponent(job.id);box.append(download);}
 box.append(el('p','muted',job.state==='running'?'Операция выполняется…':job.state==='completed'?'Операция завершена. Установка на телефоне проверяется отдельно.':'Есть ошибки или прерывание. Проверьте файлы на телефоне перед повтором.'));
 const retry=job.items.filter(i=>['failed','interrupted'].includes(i.stage)).map(i=>i.id);if(retry.length){const button=el('button','btn secondary','Выбрать неудачные для повтора');button.onclick=()=>{catSelected=new Set(retry);catInvalidate();catRenderGrid();cat('plan').scrollIntoView({block:'center'});notify('Проверьте зависимости, телефон и папку перед повтором');};box.append(button);}
 cat('jobs').append(box);
 }
}
function catRender(){
 catRenderGrid();catRenderSelection();catRenderJobs();catEnableActions();const current=cat('sets').value;cat('sets').replaceChildren(el('option','','Выберите набор'));cat('sets').firstChild.value='';for(const name of Object.keys(catState.sets)){const o=el('option','',name);o.value=name;cat('sets').append(o);}cat('sets').value=current;
 cat('research').replaceChildren(...catState.research.map(r=>{const p=el('p');p.append(el('strong','',r.name+': '),document.createTextNode(r.reason+' '),catSafeLink(r.source,'Источник ↗'));return p;}));
}
for(const id of ['query','category','compatibility','network','format','delivery','profile'])cat(id).addEventListener(id==='query'?'input':'change',catRenderGrid);
for(const button of document.querySelectorAll('[data-catalog-collection]'))button.onclick=()=>{catCollection=button.dataset.catalogCollection;catRenderGrid();};
cat('reset').onclick=()=>{catCollection='';for(const id of ['query','category','compatibility','network','format','delivery'])cat(id).value='';catRenderGrid();};
cat('select-visible').onclick=()=>{for(const a of catVisible())if(a.delivery==='automatic'&&a.category!=='high-risk')catSelected.add(a.id);catInvalidate();catRenderGrid();};
cat('clear').onclick=()=>{catSelected.clear();catInvalidate();catRenderGrid();};
cat('sets').onchange=()=>{if(!catState.sets[cat('sets').value])return;catSelected=new Set(catState.sets[cat('sets').value]);catInvalidate();catRenderGrid();};
cat('save').onclick=async()=>{try{await catApi({action:'save-set',name:cat('set-name').value,ids:[...catSelected]});await catRefresh();notify('Набор сохранён в вашей среде SymPort');}catch(e){catError(e);}};
cat('plan').onclick=async()=>{try{catPlan=await catApi({action:'plan',ids:[...catSelected],profile:'nokia-e52'});const result=cat('plan-result');result.replaceChildren(el('p','',`Пакетов с зависимостями: ${catPlan.ids.length} · ${(catPlan.bytes/1024/1024).toFixed(2)} МиБ`));for(const [id,requirements] of Object.entries(catPlan.requirements)){result.append(el('p','muted',(catState.apps.find(a=>a.id===id)?.name||id)+': '+requirements.join(' ')));}for(const problem of catPlan.problems)result.append(el('p','error-text',problem));cat('download').disabled=!!catPlan.problems.length;cat('transfer').disabled=!!catPlan.problems.length;catEnableActions();}catch(e){catError(e);}};
async function catStart(action){
 if(!catPlan||catBusy)return;const ids=[...catSelected];
 if(action==='transfer'&&!confirm(`Передать набор на ${cat('device').value}? Проверьте внешние требования. Это копирование файлов; установка выполняется на Nokia.`))return;
 catBusy=true;cat('download').disabled=true;cat('transfer').disabled=true;
 try{await catApi({action,ids,device:cat('device').value,path:cat('path').value,confirm:action==='transfer'});cat('status').textContent='Очередь запущена. Результаты появятся ниже.';await catRefresh();}catch(e){catError(e);}finally{catBusy=false;catEnableActions();}
}
cat('download').onclick=()=>catStart('download');cat('transfer').onclick=()=>catStart('transfer');
window.addEventListener('hashchange',()=>{if(location.hash==='#catalog')catRefresh();});
setInterval(()=>{if(catState.jobs.some(j=>j.state==='running'))catRefresh();},1500);
catRefresh();
