// Core: helpers, polling, navigation, the Blinds page and the setup steps.
const $=id=>document.getElementById(id),H=(t,a={},...k)=>{const e=document.createElement(t);for(const n in a){if(n=='class')e.className=a[n];else if(n=='html')e.innerHTML=a[n];else if(n.startsWith('on'))e.addEventListener(n.slice(2),a[n]);else if(a[n]!==false&&a[n]!=null)e.setAttribute(n,a[n])}for(const c of k.flat())if(c!=null)e.append(c);return e};
const api=(p,q)=>fetch('/api/'+p+(q?'?'+new URLSearchParams(q):''),{cache:'no-store'}).then(r=>r.json());
let S=null,C=null,view='blinds',fails=0,lastTouch=Date.now(),paused=false,sig='',dragging={};
const dev=()=>localStorage.dev=='1';
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('on');clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove('on'),2600)}
async function act(p,q){try{const r=await api(p,q);if(!r.ok)toast(cap(r.err||'That did not work'));poll();return r}catch(e){toast('Cannot reach the blinds');return{ok:0}}}
const cap=s=>s.charAt(0).toUpperCase()+s.slice(1);
const ICON={blinds:'<path d="M4 4h16M5 8h14M5 12h14M5 16h14M12 16v4"/>',sched:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',set:'<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',dev:'<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>'};
function nav(){const n=$('nav');n.innerHTML='';for(const[k,l]of[['blinds','Blinds'],['sched','Schedule'],['set','Settings']].concat(dev()?[['dev','Developer']]:[]))
 n.append(H('button',{class:view==k?'on':'',onclick:()=>go(k),html:'<svg viewBox="0 0 24 24">'+ICON[k]+'</svg>'+l}))}
function go(k){view=k;for(const v of['blinds','sched','set','dev'])$('v-'+v).hidden=v!=k;nav();window.scrollTo(0,0);if(k=='sched')drawSched();if(k=='set')drawSet();if(k=='dev')drawDev();poll()}

// ---- words for a tilt
function tiltText(t){if(t==null)return'';const a=Math.abs(t);if(a<8)return'Open';if(a>92)return'Closed, slats '+(t>0?'up':'down');return Math.round(a)+'% toward '+(t>0?'up':'down')}
function tiltShort(t){return t==0?'Open':t==100?'Close up':t==-100?'Close down':'Tilt '+(t>0?'+':'')+t}
function slats(t,cls){const th=(t==null?0:t)*0.8*Math.PI/180,L=13;let s='';for(let i=0;i<7;i++){const y=14+i*12.6,dx=L*Math.cos(th),dy=L*Math.sin(th);s+=`<line x1="${38-dx}" y1="${y+dy}" x2="${38+dx}" y2="${y-dy}"/>`}
 return`<svg class="${cls}" viewBox="0 0 76 104"><rect class="glow" width="76" height="104" opacity="${t==null?0:(.06+.8*(1-Math.abs(t)/100)).toFixed(2)}"/>${s}</svg>`}
const glyph=t=>{const th=t*0.55*Math.PI/180,dx=7*Math.cos(th),dy=7*Math.sin(th);return'<svg viewBox="0 0 30 22">'+[4.5,11,17.5].map(y=>`<line x1="${15-dx}" y1="${y+dy}" x2="${15+dx}" y2="${y-dy}"/>`).join('')+'</svg>'};

// ---- polling
async function poll(){if(paused)return;try{S=await api('s');fails=0}catch(e){if(++fails>2)S=null}render()}
function loop(){const fast=S&&(S.mv>=0||view=='dev'||wiz);clearTimeout(loop.t);loop.t=setTimeout(async()=>{if(document.visibilityState=='visible'){if(S&&S.batt.st=='battery'&&S.pw.mode==0&&Date.now()-lastTouch>300000&&!paused){paused=true;render()}await poll()}loop()},fast?300:900)}
['pointerdown','keydown'].forEach(e=>addEventListener(e,()=>{lastTouch=Date.now();if(paused){paused=false;poll()}},true));
document.addEventListener('visibilitychange',()=>{if(document.visibilityState=='visible'){lastTouch=Date.now();paused=false;poll()}});

function render(){
 const b=$('banner');b.innerHTML='';
 if(!S){$('hSub').innerHTML='<span class="dot off"></span> Not reachable';$('batt').hidden=true;
  b.append(H('div',{class:'ban',html:'<div><b>Cannot reach the blinds.</b> On battery they sleep and join Wi-Fi only now and then. Plug in the USB cable to wake them, then wait half a minute.</div>'}));return}
 $('hName').textContent=S.name;document.title=S.name;
 const moving=S.mv>=0;$('hSub').innerHTML=paused?'<span class="dot warn"></span> Paused to save battery':'<span class="dot"></span> '+(moving?'Moving '+S.b[S.mv].name:'Connected');
 const bt=$('batt');bt.hidden=false;const st=S.batt.st;bt.innerHTML=(st=='charging'?'&#9889; ':st=='full'?'&#9889; ':'')+S.batt.pct+'%'+(st=='battery'?'':' <span class="muted">'+(st=='full'?'full':'charging')+'</span>');
 bt.style.color=S.batt.low?'var(--bad)':'';
 if(paused)b.append(H('div',{class:'ban',html:'<div>Paused so the blinds can go back to sleep. Tap anywhere to carry on.</div>'}));
 else if(S.pw.sleepIn>=0)b.append(H('div',{class:'ban',html:'<div><b>On battery.</b> Wi-Fi goes off '+(S.pw.sleepIn>90?'in about '+Math.round(S.pw.sleepIn/60)+' min':'in '+S.pw.sleepIn+' s')+' after you stop using this page.</div>'}));
 if(S.batt.low)b.append(H('div',{class:'ban',html:'<div><b>Battery too low to move the blinds.</b> Plug in the USB cable.</div>'}));
 if(S.ap)b.append(H('div',{class:'ban'},H('div',{html:'<b>Not on your Wi-Fi.</b> You are on the setup network.'}),H('span',{class:'sp'}),H('button',{class:'sm',onclick:()=>{go('set');wifiSheet()}},'Set Wi-Fi')));
 if(view=='blinds')drawBlinds();if(view=='dev'&&window.devTick)devTick();if(wiz)wizTick()}

// ---- Blinds page
function drawBlinds(){const el=$('v-blinds'),vis=S.b.map((x,i)=>({...x,i})).filter(x=>!x.hid);
 const s2=JSON.stringify(vis.map(x=>[x.i,x.name,x.cal,x.pres,x.seen]))+S.closeUp+S.sync;
 if(s2!=sig){sig=s2;el.innerHTML='';const ready=vis.filter(x=>x.cal&&x.pres);
  if(ready.length>1)el.append(H('div',{class:'card',style:'margin-bottom:14px'},H('div',{class:'row wrap'},H('h3',{},'All blinds'),H('span',{class:'sp'}),
   H('div',{class:'chip w'+(S.sync?' on':''),title:'Move one, they all follow',onclick:()=>act('set',{k:'sync',v:S.sync?0:1}).then(()=>toast(S.sync?'Each blind moves on its own':'Blinds now move together'))},S.sync?'In sync':'Sync off'),H('button',{class:'sm',onclick:()=>act('go',{b:'all',to:'open'})},'Open'),H('button',{class:'sm',onclick:()=>act('go',{b:'all',to:'close'})},'Close'),H('button',{class:'sm stop',id:'allStop',hidden:true,onclick:()=>act('stop')},'Stop'))));
  const g=H('div',{class:'grid'});el.append(g);
  for(const x of vis){const i=x.i,c=H('div',{class:'card',id:'c'+i});g.append(c);
   const head=H('div',{class:'blind'},H('div',{id:'w'+i}),H('div',{},H('h3',{},x.name),H('div',{class:'state',id:'s'+i})));c.append(head);
   if(x.seen&&!x.pres){c.append(H('div',{class:'row mt'},H('span',{class:'muted small sp'},'Nothing is plugged into port '+(i+1)+'.'),H('button',{class:'sm',onclick:()=>act('set',{k:'b'+i+'.hid',v:1}).then(()=>toast('Hidden. Bring it back in Settings.'))},'Hide')))}
   else if(!x.cal){c.append(H('button',{class:'p big mt',onclick:()=>wizard(i)},'Set up this blind'))}
   else{c.append(H('div',{class:'seg mt',id:'g'+i},...[[-100,'Close down'],[0,'Open'],[100,'Close up']].map(([t,l])=>H('button',{'data-t':t,onclick:()=>act('go',{b:i,t}),html:glyph(t)+l}))),
    H('div',{class:'mt'},H('input',{type:'range',min:-100,max:100,step:1,id:'r'+i,'aria-label':'Tilt',oninput:e=>{dragging[i]=1;paint(i,+e.target.value,true)},onchange:e=>{act('go',{b:i,t:e.target.value});setTimeout(()=>dragging[i]=0,1500)}}),
     H('div',{class:'ends'},H('span',{},'Closed down'),H('span',{},'Open'),H('span',{},'Closed up'))),
    H('div',{class:'row mt'},H('button',{class:'sm',onclick:()=>act('go',{b:i,to:'fav'})},'★ Favorite'),H('span',{class:'sp'}),H('button',{class:'sm stop',id:'x'+i,hidden:true,onclick:()=>act('stop')},'Stop')))}}
  if(!vis.length)el.append(H('div',{class:'card center muted'},'Every port is hidden. Turn one back on in Settings.'))}
 for(const x of vis){const i=x.i;if(!$('s'+i))continue;paint(i,x.cal?x.tilt:null,false,x);const xb=$('x'+i);if(xb)xb.hidden=!(x.mov||x.q)}
 const as=$('allStop');if(as)as.hidden=S.mv<0}
function paint(i,t,drag,x){$('w'+i).innerHTML=slats(t,'win');const r=$('r'+i);if(r&&!drag&&!dragging[i]&&t!=null)r.value=Math.round(t);
 const g=$('g'+i);if(g)for(const b of g.children)b.classList.toggle('on',t!=null&&Math.abs(t-b.dataset.t)<8);
 const s=$('s'+i);if(drag){s.innerHTML='<b>'+tiltText(t)+'</b>';return}if(!x)return;
 s.innerHTML=x.seen&&!x.pres?'Not connected':!x.cal?'Not set up yet':x.mov?'<b>Moving</b> to '+tiltText(x.tgt).toLowerCase():x.q?'Waiting its turn':t==null?'...':'<b>'+tiltText(t)+'</b>'+(/blocked|time limit|low/.test(x.last)?' <span class="bad">'+x.last+'</span>':'')}

// ---- setup steps for one blind
let wiz=null;
const WS=[['up','Close the slats upward','Turn until the slats are fully closed with the room-side edge up.'],['open','Level the slats','Turn until the slats are flat, fully open.'],['down','Close the slats downward','Turn until the slats are fully closed with the room-side edge down.']];
function sheet(...k){const s=$('sheetIn');s.innerHTML='';s.append(...k.filter(x=>x!=null));$('sheet').hidden=false}
function closeSheet(){$('sheet').hidden=true;wiz=null;sig='';poll()}
function holdBtn(label,i,d){let t=null;const p=()=>api('jog',{b:i,d,p:wiz&&wiz.slow?60:100,ms:450}).catch(()=>{}),up=()=>{if(!t)return;clearInterval(t);t=null;api('stop')};
 const b=H('button',{},label);b.addEventListener('pointerdown',e=>{e.preventDefault();if(t)return;p();t=setInterval(p,180)});['pointerup','pointerleave','pointercancel'].forEach(ev=>b.addEventListener(ev,up));b.addEventListener('contextmenu',e=>e.preventDefault());return b}
function wizard(i){wiz={i,step:0,slow:false};wizDraw()}
function wizDraw(){const i=wiz.i,n=wiz.step,name=S.b[i].name;
 if(n<3){const[w,t,d]=WS[n];sheet(H('div',{class:'row'},H('h3',{},'Set up '+name),H('span',{class:'sp'}),H('button',{class:'ghost',onclick:closeSheet},'Cancel')),
  H('div',{class:'steps'},...[0,1,2,3].map(k=>H('i',{class:k<=n?'on':''}))),H('div',{class:'row'},H('div',{html:slats([100,0,-100][n],'win')}),H('div',{},H('h3',{},(n+1)+'. '+t),H('div',{class:'muted small',style:'margin-top:4px'},d+' Hold a button, or turn the wand by hand. After a change of direction the motor runs several seconds before the slats start to move.'))),
  H('div',{class:'jog mt2'},holdBtn('◀ Turn',i,-1),holdBtn('Turn ▶',i,1)),
  H('div',{class:'row mt'},H('label',{class:'row small muted'},H('input',{type:'checkbox',onchange:e=>wiz.slow=e.target.checked}),'Slow'),H('span',{class:'sp'}),H('span',{class:'small muted',id:'wAng'})),
  H('button',{class:'p big mt2',onclick:async()=>{const r=await act('mark',{b:i,w});if(!r.ok)return;if(n==2&&r.prob){toast(cap(r.prob)+'. Start again.');await api('mark',{b:i,w:'clear'});wiz.step=0}else wiz.step++;wizDraw()}},'This is '+['closed up','open','closed down'][n]),
  n?H('button',{class:'ghost big',onclick:()=>{wiz.step--;wizDraw()}},'Back'):null)}
 else sheet(H('div',{class:'steps'},...[0,1,2,3].map(()=>H('i',{class:'on'}))),H('h3',{},name+' is set up'),H('div',{class:'muted small',style:'margin:6px 0 14px'},'Try each position. If one is off, redo the setup from Settings.'),
  H('div',{class:'seg'},...[[-100,'Close down'],[0,'Open'],[100,'Close up']].map(([t,l])=>H('button',{onclick:()=>act('go',{b:i,t,solo:1}),html:glyph(t)+l}))),
  H('div',{class:'center small muted mt',id:'wAng'}),H('button',{class:'stop big mt',onclick:()=>act('stop')},'Stop'),H('button',{class:'p big mt',onclick:closeSheet},'Done'))}
function wizTick(){const a=$('wAng'),x=S&&S.b[wiz.i];if(!a||!x)return;if(wiz.step<3&&S.hk!=null&&!x.mov)api('watch',{b:wiz.i}).catch(()=>{});a.textContent=!x.pres&&x.seen?'Nothing plugged into this port':x.mov?'Moving...':wiz.step==3?tiltText(x.tilt):x.ang!=null?'Sensor '+x.ang.toFixed(1)+'\u00B0':''}
