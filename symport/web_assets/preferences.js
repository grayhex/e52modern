"use strict";
let uiLanguage='ru',uiTheme='system',uiTranslations={en:{},ru:{},patterns:[]};
try{uiLanguage=localStorage.getItem('symport-language')==='en'?'en':'ru';uiTheme=localStorage.getItem('symport-theme')||'system';}catch{}
if(!['system','light','dark'].includes(uiTheme))uiTheme='system';
const uiMedia=matchMedia('(prefers-color-scheme: dark)'),uiOriginal=new WeakMap();
function uiApplyTheme(){document.documentElement.dataset.theme=uiTheme==='system'?(uiMedia.matches?'dark':'light'):uiTheme;}
uiApplyTheme();uiMedia.addEventListener('change',uiApplyTheme);
function tr(text){
 if(typeof text!=='string')return text;
 const leading=text.match(/^\s*/)[0],trailing=text.match(/\s*$/)[0],key=text.trim().replace(/\s+/g,' ');
 let translated=uiTranslations[uiLanguage]?.[key];
 if(translated===undefined&&uiLanguage==='en')for(const pattern of uiTranslations.patterns||[]){
  const bits=pattern.source.split(/(ZXVAR\d+XZ)/),order=[];
  const regex='^'+bits.map(bit=>/^ZXVAR\d+XZ$/.test(bit)?(order.push(bit),'(.*?)'):bit.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('')+'$';
  const match=key.match(new RegExp(regex));if(match){translated=pattern.en;for(let i=0;i<order.length;i++)translated=translated.replace(order[i],({'Офлайн':'Offline','Онлайн':'Online','Сеть + кэш':'Network + cache'})[match[i+1]]||match[i+1]);break;}
 }
 if(translated===undefined&&uiLanguage==='en'){
  const unit=key.match(/^(\d+(?:\.\d+)?) (ГиБ|МиБ|КиБ|шт\.|проект\(ов\))$/);
  if(unit)translated=unit[1]+' '+({'ГиБ':'GiB','МиБ':'MiB','КиБ':'KiB','шт.':'items','проект(ов)':'projects'})[unit[2]];
  else if(key.includes(': ')&&uiTranslations.en[key.split(': ')[0]]){const index=key.indexOf(': ');translated=uiTranslations.en[key.slice(0,index)]+key.slice(index);}
  else if(key.includes(' · ')){const pieces=key.split(' · '),known=pieces.map(p=>uiTranslations.en[p]||p);if(known.some((p,i)=>p!==pieces[i]))translated=known.join(' · ');}
 }
 return translated===undefined?text:leading+translated+trailing;
}
function uiTranslateNode(node){
 if(node.nodeType===Node.TEXT_NODE){
  if(!node.parentElement||node.parentElement.closest('script,style,pre,code,[data-i18n-skip],textarea,svg,#inspect-facts dd,#calendar-events,#calendar-todos,#inspect-reports,#jb-history'))return;
  const value=node.nodeValue;let record=uiOriginal.get(node);
  if(!record||record.last!==value)record={source:value,last:value};
  const next=tr(record.source);record.last=next;uiOriginal.set(node,record);if(next!==value)node.nodeValue=next;
 }else if(node.nodeType===Node.ELEMENT_NODE){
  if(node.matches('script,style,pre,code,[data-i18n-skip],textarea,svg,#inspect-facts dd,#calendar-events,#calendar-todos,#inspect-reports,#jb-history'))return;
  for(const attribute of ['placeholder','title','aria-label','alt'])if(node.hasAttribute(attribute)){
   const holder=node.getAttributeNode(attribute),value=holder.value;let record=uiOriginal.get(holder);
   if(!record||record.last!==value)record={source:value,last:value};const next=tr(record.source);record.last=next;uiOriginal.set(holder,record);if(value!==next)holder.value=next;
  }
  for(const child of node.childNodes)uiTranslateNode(child);
 }
}
function uiApplyLanguage(){document.documentElement.lang=uiLanguage;uiTranslateNode(document.body);window.dispatchEvent(new CustomEvent('symport-language',{detail:uiLanguage}));}
const uiConfirm=window.confirm.bind(window),uiAlert=window.alert.bind(window);
window.confirm=message=>uiConfirm(tr(message));window.alert=message=>uiAlert(tr(message));
const uiObserver=new MutationObserver(records=>{for(const record of records){if(record.type==='childList')for(const n of record.addedNodes)uiTranslateNode(n);else uiTranslateNode(record.target);}});
uiObserver.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label','alt']});
document.getElementById('ui-language').value=uiLanguage;document.getElementById('ui-theme').value=uiTheme;
document.getElementById('ui-language').onchange=e=>{uiLanguage=e.target.value;try{localStorage.setItem('symport-language',uiLanguage);}catch{}uiApplyLanguage();};
document.getElementById('ui-theme').onchange=e=>{uiTheme=e.target.value;try{localStorage.setItem('symport-theme',uiTheme);}catch{}uiApplyTheme();};
fetch('/translations.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('Translation catalog unavailable');return r.json();}).then(data=>{uiTranslations=data;uiApplyLanguage();}).catch(()=>{});
