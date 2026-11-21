// Schedule and Settings pages.
const DAYS=['S','M','T','W','T','F','S'],DAYN=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const sw=(on,fn)=>H('label',{class:'sw'},H('input',{type:'checkbox',checked:on?'':null,onchange:e=>fn(e.target.checked)}),H('i'));
const hhmm=m=>{const h=Math.floor(m/60),mm=m%60;return(h%12||12)+':'+String(mm).padStart(2,'0')+(h<12?' AM':' PM')};
const daysText=d=>d==127?'Every day':d==62?'Weekdays':d==65?'Weekends':DAYN.filter((_,k)=>d>>k&1).join(' ')||'Never';
async function loadCfg(){C=await api('cfg');return C}
const saveSched=(i,s)=>act('sched',{i,on:s.on,days:s.days,mask:s.mask,min:s.min,tilt:s.tilt});
const TZ={'America/New_York':'EST5EDT,M3.2.0,M11.1.0','America/Detroit':'EST5EDT,M3.2.0,M11.1.0','America/Chicago':'CST6CDT,M3.2.0,M11.1.0','America/Denver':'MST7MDT,M3.2.0,M11.1.0','America/Phoenix':'MST7','America/Los_Angeles':'PST8PDT,M3.2.0,M11.1.0','America/Anchorage':'AKST9AKDT,M3.2.0,M11.1.0','Pacific/Honolulu':'HST10','Europe/London':'GMT0BST,M3.5.0/1,M10.5.0','Europe/Berlin':'CET-1CEST,M3.5.0,M10.5.0/3','Europe/Paris':'CET-1CEST,M3.5.0,M10.5.0/3'};
function phoneTz(){const n=Intl.DateTimeFormat().resolvedOptions().timeZone||'';if(TZ[n])return[n,TZ[n]];const o=new Date().getTimezoneOffset(),a=Math.abs(o);return[n||'Phone time',`<${o>0?'-':'+'}${String(Math.floor(a/60)).padStart(2,'0')}>${o>0?'':'-'}${Math.floor(a/60)}${a%60?':'+a%60:''}`]}

async function drawSched(){const el=$('v-sched');if(!C)el.innerHTML='';await loadCfg();el.innerHTML='';
 const list=H('div',{class:'list'}),shown=C.sched.map((s,i)=>({...s,i})).filter(s=>s.mask);
 for(const s of shown)list.append(H('div',{class:'item tap'},H('div',{class:'t',onclick:()=>schedSheet(s.i)},H('div',{},hhmm(s.min)+' · '+tiltShort(s.tilt)),H('div',{class:'small'},daysText(s.days)+' · '+(C.b.filter((b,k)=>!b.hid&&s.mask>>k&1).map(b=>b.name).join(', ')||'no blinds'))),
  sw(s.on,v=>{s.on=v?1:0;saveSched(s.i,s)})));
 el.append(H('h2',{},'Schedules'));if(shown.length)el.append(list);else el.append(H('div',{class:'card muted center'},'No schedules yet. Open the blinds every morning, close them at night.'));
 const free=C.sched.findIndex(s=>!s.mask);
 el.append(H('button',{class:'p big mt',disabled:free<0?'':null,onclick:()=>schedSheet(free,true)},free<0?'All 8 schedules are used':'Add a schedule'),
  H('div',{class:'small muted mt center'},(S&&S.tok?'Device time '+new Date(S.t*1000).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',timeZone:TZ[C.tzn]?C.tzn:undefined})+' ('+C.tzn+'). ':'The clock is not set yet (needs Wi-Fi once). ')+'Schedules also run on battery, with Wi-Fi off.'))}
function schedSheet(i,isNew){const s={...C.sched[i]};if(isNew){s.on=1;s.days=127;s.mask=7;s.min=480;s.tilt=0}
 const dayRow=H('div',{class:'chips'}),bl=H('div',{class:'chips'}),ac=H('div',{class:'chips'}),cu=H('div',{class:'mt',hidden:true});
 const rd=()=>{dayRow.innerHTML='';DAYS.forEach((d,k)=>dayRow.append(H('div',{class:'chip'+(s.days>>k&1?' on':''),onclick:()=>{s.days^=1<<k;rd()}},d)));
  bl.innerHTML='';C.b.forEach((b,k)=>{if(!b.hid)bl.append(H('div',{class:'chip w'+(s.mask>>k&1?' on':''),onclick:()=>{s.mask^=1<<k;rd()}},b.name))});
  ac.innerHTML='';const std=[0,100,-100].includes(s.tilt)&&!s.custom;[[-100,'Close down'],[0,'Open'],[100,'Close up']].forEach(([t,l])=>ac.append(H('div',{class:'chip w'+(std&&s.tilt==t?' on':''),onclick:()=>{s.tilt=t;s.custom=0;rd()}},l)));
  ac.append(H('div',{class:'chip w'+(std?'':' on'),onclick:()=>{s.custom=1;rd()}},'Other'));cu.hidden=std;cu.innerHTML='';
  if(!std)cu.append(H('input',{type:'range',min:-100,max:100,step:5,value:s.tilt,oninput:e=>{s.tilt=+e.target.value;$('cuT').textContent=tiltText(s.tilt)}}),H('div',{class:'small muted center',id:'cuT'},tiltText(s.tilt)))};rd();
 const tm=H('input',{type:'time',value:String(Math.floor(s.min/60)).padStart(2,'0')+':'+String(s.min%60).padStart(2,'0'),onchange:e=>{const[h,m]=e.target.value.split(':');s.min=h*60+ +m}});
 sheet(H('div',{class:'row'},H('h3',{},isNew?'New schedule':'Schedule'),H('span',{class:'sp'}),H('button',{class:'ghost',onclick:()=>{$('sheet').hidden=true}},'Cancel')),
  H('label',{class:'f'},'Time'),tm,H('label',{class:'f'},'Days'),dayRow,H('label',{class:'f'},'Do this'),ac,cu,H('label',{class:'f'},'Blinds'),bl,
  H('button',{class:'p big mt2',onclick:async()=>{if(!s.days||!s.mask)return toast('Pick at least one day and one blind');await saveSched(i,s);$('sheet').hidden=true;drawSched()}},'Save'),
  isNew?null:H('button',{class:'ghost big bad',onclick:async()=>{s.on=0;s.mask=0;await saveSched(i,s);$('sheet').hidden=true;drawSched()}},'Delete'))}

async function drawSet(){const el=$('v-set');await loadCfg();el.innerHTML='';const set=(k,v,x)=>act('set',{k,v,...x});
 const txt=(val,fn,ph)=>H('input',{type:'text',value:val,maxlength:19,placeholder:ph||'',onchange:e=>fn(e.target.value)});
 el.append(H('h2',{},'Blinds'));const bl=H('div',{class:'list'});el.append(bl);
 C.b.forEach((b,i)=>bl.append(H('div',{class:'item tap',onclick:()=>blindSheet(i)},H('div',{class:'t'},H('div',{},b.name),H('div',{class:'small'},'Port '+(i+1)+(b.hid?' · hidden':S&&S.b[i].seen&&!S.b[i].pres?' · nothing plugged in':S&&!S.b[i].cal?' · not set up':''))),H('span',{class:'muted'},'›'))));
 el.append(H('h2',{},'General'),H('div',{class:'list'},
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Name')),H('div',{style:'width:55%'},txt(C.name,v=>set('name',v)))),
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'"Close" tilts the slats'),H('div',{class:'small'},'Used by Close all, schedules and voice.')),H('div',{class:'chips'},H('div',{class:'chip w'+(C.closeUp?' on':''),onclick:()=>set('closeUp',1).then(drawSet)},'Up'),H('div',{class:'chip w'+(C.closeUp?'':' on'),onclick:()=>set('closeUp',0).then(drawSet)},'Down'))),
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Move blinds together'),H('div',{class:'small'},'Adjust one blind and the others go to the same position.')),sw(C.sync,v=>set('sync',v?1:0))),
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Time zone'),H('div',{class:'small'},C.tzn)),H('button',{class:'sm',onclick:()=>{const[n,z]=phoneTz();set('tz',z,{n}).then(drawSet)}},'Use this device’s'))));
 if(!(S&&S.hk!=null))el.append(H('h2',{},'Battery'),H('div',{class:'list'},
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'On battery'),H('div',{class:'small'},C.battMode?'Wi-Fi stays on. Always reachable, but one charge lasts about a week.':'Wi-Fi off to save the battery. Schedules still run. Plug in USB to use this app.')),H('div',{class:'chips'},H('div',{class:'chip w'+(C.battMode?'':' on'),onclick:()=>set('battMode',0).then(drawSet)},'Sleep'),H('div',{class:'chip w'+(C.battMode?' on':''),onclick:()=>set('battMode',1).then(drawSet)},'Stay on'))),
  C.battMode?null:H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Check in on Wi-Fi'),H('div',{class:'small'},'While asleep it joins Wi-Fi for a few seconds this often, so this app can catch it.')),H('select',{style:'width:auto',onchange:e=>set('checkin',e.target.value)},...[[5,'5 min'],[15,'15 min'],[30,'30 min'],[60,'1 hour'],[0,'Never']].map(([v,l])=>H('option',{value:v,selected:C.checkin==v?'':null},l))))));
 el.append(H('h2',{},'Connection'),H('div',{class:'list'},H('div',{class:'item tap',onclick:()=>S&&S.hk!=null?toast('Changing the network is not in this version yet'):wifiSheet()},H('div',{class:'t'},H('div',{},'Wi-Fi network'),H('div',{class:'small',id:'wfN'},'')),H('span',{class:'muted'},'›')),
  S&&S.hk!=null?H('div',{class:'item tap',onclick:hkSheet},H('div',{class:'t'},H('div',{},'Apple Home'),H('div',{class:'small'},S.hk?'Added':'Not added yet. Tap for the pairing code.')),H('span',{class:'muted'},'\u203A')):H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Apple Home and Alexa'),H('div',{class:'small'},'Not in this version yet.')))));
 el.append(H('h2',{},'About'),H('div',{class:'list'},H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Version'),H('div',{class:'small'},S?S.v:''))),
  H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Developer mode'),H('div',{class:'small'},'Adds a page with live readings, tests and updates.')),sw(dev(),v=>{localStorage.dev=v?'1':'0';nav()}))));
 api('dev').then(d=>{const w=$('wfN');if(w)w.textContent=d.wifi.ssid||'not connected'}).catch(()=>{})}
function blindSheet(i){const b=C.b[i],set=(f,v)=>act('set',{k:'b'+i+'.'+f,v});
 sheet(H('div',{class:'row'},H('h3',{},b.name),H('span',{class:'sp'}),H('button',{class:'ghost',onclick:()=>{$('sheet').hidden=true;sig='';drawSet()}},'Done')),
  H('label',{class:'f'},'Name'),H('input',{type:'text',value:b.name,maxlength:19,onchange:e=>set('name',e.target.value)}),
  H('label',{class:'f'},'★ Favorite position'),H('input',{type:'range',min:-100,max:100,step:5,value:b.fav,oninput:e=>$('fvT').textContent=tiltText(+e.target.value),onchange:e=>set('fav',e.target.value)}),H('div',{class:'small muted center',id:'fvT'},tiltText(b.fav)),
  H('div',{class:'list mt2'},H('div',{class:'item'},H('div',{class:'t'},H('div',{},'Show this blind'),H('div',{class:'small'},'Turn off for a port with nothing plugged in.')),sw(!b.hid,v=>{b.hid=v?0:1;set('hid',b.hid)}))),
  H('button',{class:'big mt2',onclick:()=>{$('sheet').hidden=true;go('blinds');wizard(i)}},'Redo the setup'))}
async function wifiSheet(){const box=H('div',{class:'list mt'},H('div',{class:'item muted'},'Looking for networks...')),ss=H('input',{type:'text',placeholder:'Network name',autocapitalize:'none'}),pw=H('input',{type:'password',placeholder:'Password'});
 sheet(H('div',{class:'row'},H('h3',{},'Wi-Fi network'),H('span',{class:'sp'}),H('button',{class:'ghost',onclick:()=>{$('sheet').hidden=true}},'Cancel')),
  H('div',{class:'small muted'},'2.4 GHz networks only. If it cannot join, it opens its own network called Blinds-Setup so you can fix it.'),box,H('label',{class:'f'},'Network'),ss,H('label',{class:'f'},'Password'),pw,
  H('button',{class:'p big mt2',onclick:async()=>{if(!ss.value)return toast('Pick a network');const r=await fetch('/api/wifi',{method:'POST',body:new URLSearchParams({ssid:ss.value,pass:pw.value})}).then(r=>r.json()).catch(()=>({ok:1}));$('sheet').hidden=true;toast(r.ok?'Saved. Joining '+ss.value+'...':cap(r.err))}},'Join'));
 try{const r=await api('scan');box.innerHTML='';const seen={};for(const n of r.nets.sort((a,b)=>b.rssi-a.rssi)){if(!n.ssid||seen[n.ssid])continue;seen[n.ssid]=1;box.append(H('div',{class:'item tap',onclick:()=>{ss.value=n.ssid;pw.focus()}},H('div',{class:'t'},H('div',{},n.ssid)),H('span',{class:'small muted'},(n.lock?'🔒 ':'')+n.rssi+' dBm')))}
  if(!box.children.length)box.append(H('div',{class:'item muted'},'No networks found.'))}catch(e){box.innerHTML='';box.append(H('div',{class:'item muted'},'Could not scan. Type the name below.'))}}
