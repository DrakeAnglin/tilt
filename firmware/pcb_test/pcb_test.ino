// Test firmware for the carrier PCB (hardware/pcb, docs/pcb-build.md): 3 RJ12 ports. ESP32-C6, Arduino-ESP32 core 3.x.
// Same as bench_test, but with the PCB's pin map and a port selector. One port runs at a time.
//
// Web page: http://blinds-pcb.local (or the IP it prints) - live telemetry, angle graph, controls.
// Commands, over USB serial (115200) or Wi-Fi (nc blinds-pcb.local 23):
//   p = next port (1 -> 2 -> 3)   e = EN on   x = EN off   f = forward   r = reverse   s = stop (brake)
//   0..9 = duty 0..100 %     a = print angle continuously on/off     v = print all voltages and angles
// Updates over Wi-Fi: arduino-cli ... -p blinds-pcb.local (firmware/README.md).
// Wi-Fi name / password / update password go in secrets.h (copy secrets.h.example; secrets.h is not committed).
//
// Safety: every move is timed (web hold-to-run stops within ~0.4 s of letting go or losing the connection), no move
// lasts more than 15 s, and a move stops by itself if the angle stops changing (stall).
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <WebServer.h>
#include <Preferences.h>
#include "secrets.h"

// PCB pin map (hardware/pcb/netlist.py): per port IN1, IN2, EN, angle
const int PORTS = 3;
const int P_IN1[PORTS] = {14, 19, 16}, P_IN2[PORTS] = {18, 20, 17}, P_EN[PORTS] = {7, 5, 1}, P_ANG[PORTS] = {6, 4, 2};
const int PIN_VBAT = 3, PIN_VIN = 0;           // PCB dividers (1 M / 1 M): battery / LOAD rail (VDIV), input power (PSENSE)
int port = 0;                                  // selected port, 0..2
int PIN_IN1 = 14, PIN_IN2 = 18, PIN_EN = 7, PIN_ANGLE = 6;
const int PWM_HZ = 20000, PWM_BITS = 8;
const char *HOSTNAME = "blinds-pcb";
const uint32_t MAX_MOVE_MS = 15000, STALL_MS = 400;
const float STALL_DEG = 0.7f, GOTO_TOL = 2.0f;

int duty = 255;            // 0..255
int dir = 0;               // 1 forward (angle rises), -1 reverse, 0 stopped (braked)
bool en = false, streaming = false;
uint32_t moveUntil = 0, moveStart = 0, stallT = 0;
float stallRef = 0, target = NAN, angle = NAN, angleMv = 0, vbat = 0, vin = 0;
float markLo = NAN, markHi = NAN;
WiFiServer telnet(23);
WiFiClient client;
WebServer web(80);
Preferences prefs;

String logLines[12];
int logSeq = 0;

void say(const char *fmt, ...) {
  char buf[160];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  if (Serial) Serial.print(buf);                // only when a USB host is listening (no stalls on battery)
  if (client && client.connected()) client.print(buf);
}

void event(const char *fmt, ...) {              // a line for the web page's log (and the serial / telnet output)
  char buf[120];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  char line[140];
  snprintf(line, sizeof line, "%7.1fs  %s", millis() / 1000.0, buf);
  logLines[logSeq % 12] = line;
  logSeq++;
  say("%s\n", buf);
}

void drive() {
  // DRV8833 slow decay: one input high, PWM the other inverted (high = brake)
  if (dir > 0) { ledcWrite(PIN_IN1, 255); ledcWrite(PIN_IN2, 255 - duty); }
  else if (dir < 0) { ledcWrite(PIN_IN1, 255 - duty); ledcWrite(PIN_IN2, 255); }
  else { ledcWrite(PIN_IN1, 255); ledcWrite(PIN_IN2, 255); }      // brake
}

float readMv(int pin) {
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(pin);
  return mv / 16.0f;
}

float angDiff(float to, float from) {          // shortest signed difference, -180..180
  return fmodf(to - from + 540.0f, 360.0f) - 180.0f;
}

void setEn(bool on) {
  if (!on) { dir = 0; drive(); moveUntil = 0; target = NAN; }
  en = on;
  digitalWrite(PIN_EN, on ? HIGH : LOW);
  if (!on) angle = NAN;
}

void stopMotor(const char *why) {
  bool was = dir != 0 || !isnan(target);
  dir = 0; drive(); moveUntil = 0; target = NAN;
  if (was && why) event("stop: %s (angle %.1f)", why, angle);
}

void startMove(int d, int pct, uint32_t ms) {
  if (!en) { setEn(true); delay(5); }
  duty = constrain(pct, 0, 100) * 255 / 100;
  if (dir != d) { moveStart = millis(); stallT = millis(); stallRef = angle; }
  dir = d;
  drive();
  moveUntil = millis() + min(ms, MAX_MOVE_MS);
}

void selectPort(int p) {
  setEn(false);
  port = constrain(p, 0, PORTS - 1);
  PIN_IN1 = P_IN1[port]; PIN_IN2 = P_IN2[port]; PIN_EN = P_EN[port]; PIN_ANGLE = P_ANG[port];
  char k[4];
  snprintf(k, sizeof k, "lo%d", port + 1); markLo = prefs.getFloat(k, NAN);
  snprintf(k, sizeof k, "hi%d", port + 1); markHi = prefs.getFloat(k, NAN);
  event("port %d selected", port + 1);
}

void printAll() {
  say("battery/LOAD %.2f V   input %.2f V\n", readMv(PIN_VBAT) * 2.0f / 1000.0f, readMv(PIN_VIN) * 2.0f / 1000.0f);
  for (int i = 0; i < PORTS; i++) {
    bool was = digitalRead(P_EN[i]);
    digitalWrite(P_EN[i], HIGH); delay(30);
    float mv = readMv(P_ANG[i]);
    if (!was) digitalWrite(P_EN[i], LOW);
    say("port %d: angle %.1f deg (%.0f mV)%s\n", i + 1, mv / 3300.0f * 360.0f, mv, mv < 30 ? "  (nothing plugged in?)" : "");
  }
}

void command(char c) {
  if (c == 'p') selectPort((port + 1) % PORTS);
  else if (c == 'v') printAll();
  else if (c == 'e') { setEn(true); event("EN on"); }
  else if (c == 'x') { setEn(false); event("EN off"); }
  else if (c == 'f') { startMove(1, duty * 100 / 255, MAX_MOVE_MS); event("forward %d%%", duty * 100 / 255); }
  else if (c == 'r') { startMove(-1, duty * 100 / 255, MAX_MOVE_MS); event("reverse %d%%", duty * 100 / 255); }
  else if (c == 's') { stopMotor("command"); }
  else if (c == 'a') { streaming = !streaming; }
  else if (c >= '0' && c <= '9') { duty = (c - '0') * 255 / 9; if (dir) drive(); say("duty %d %%\n", duty * 100 / 255); }
}

// ------------------------------------------------------------------ web page
const char PAGE[] PROGMEM = R"HTML(<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Blinds PCB</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2329;--mut:#69737d;--line:#dde1e6;--acc:#2b6cb0;--ok:#2f855a;--bad:#c53030}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1e2328;--fg:#e6e9ec;--mut:#9aa4ae;--line:#323a42;--acc:#63a4ff;--ok:#48bb78;--bad:#fc8181}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid var(--line)}
h1{font-size:18px;margin:0}#conn{font-size:13px;color:var(--mut)}main{max-width:1100px;margin:0 auto;padding:16px;display:grid;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile .k{font-size:12px;color:var(--mut)}.tile .v{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums}
.big .v{font-size:34px}canvas{width:100%;height:220px;display:block}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button{font:inherit;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:9px;padding:10px 14px;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none}
button:active{transform:translateY(1px)}button.pb.sel{background:var(--acc);color:#fff;border-color:var(--acc)}button.p{background:var(--acc);color:#fff;border-color:var(--acc)}
#stop{background:var(--bad);color:#fff;border-color:var(--bad);font-weight:700;padding:14px 26px;font-size:17px}
.hold{min-width:130px;font-weight:600}input[type=range]{flex:1;min-width:160px}input[type=number]{width:90px;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
.on{color:var(--ok)}.off{color:var(--mut)}#log{font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;color:var(--mut);max-height:190px;overflow:auto}
small{color:var(--mut)}h2{font-size:14px;margin:0 0 10px;color:var(--mut);font-weight:600}
</style></head><body>
<header><h1>Blinds PCB &middot; port <span id="pn">-</span></h1><div id="conn">connecting...</div></header>
<main>
<div class="tiles">
 <div class="tile big"><div class="k">Angle</div><div class="v" id="ang">--</div></div>
 <div class="tile big"><div class="k">Position (between marks)</div><div class="v" id="pct">--</div></div>
 <div class="tile"><div class="k">Motor</div><div class="v" id="mot">--</div></div>
 <div class="tile"><div class="k">Driver / sensor (EN)</div><div class="v" id="en">--</div></div>
 <div class="tile"><div class="k">Battery + rail</div><div class="v" id="vbat">--</div></div>
 <div class="tile"><div class="k">USB / solar input</div><div class="v" id="vin">--</div></div>
 <div class="tile"><div class="k">Sensor output</div><div class="v" id="mv">--</div></div>
 <div class="tile"><div class="k">Wi-Fi signal</div><div class="v" id="rssi">--</div></div>
 <div class="tile"><div class="k">Chip temp</div><div class="v" id="temp">--</div></div>
 <div class="tile"><div class="k">Uptime</div><div class="v" id="up">--</div></div>
</div>
<div class="card"><h2>Angle, last 60 s</h2><canvas id="ch"></canvas><small>Shaded = motor running. The angle reads a few degrees high while the motor runs (shared GND wire); stopped readings are the true ones.</small></div>
<div class="card"><h2>Control</h2>
 <div class="row" style="margin-bottom:12px"><span>Port</span><button class="pb" data-p="0">1</button><button class="pb" data-p="1">2</button><button class="pb" data-p="2">3</button><small>switching turns the old port off</small></div>
 <div class="row" style="margin-bottom:12px"><button id="stop">STOP</button>
  <button id="enOn">EN on</button><button id="enOff">EN off</button><small>Space or Esc also stops</small></div>
 <div class="row" style="margin-bottom:12px"><span>Speed</span><input type="range" id="spd" min="10" max="100" step="5" value="60"><b id="spdv">60%</b></div>
 <div class="row" style="margin-bottom:12px"><button class="hold p" id="hf">Hold: forward</button><button class="hold p" id="hr">Hold: reverse</button>
  <small>runs only while held</small></div>
 <div class="row" style="margin-bottom:12px"><span>Timed move</span><input type="number" id="tms" value="1000" min="100" max="15000" step="100"><span>ms</span>
  <button id="tf">Forward</button><button id="tr">Reverse</button></div>
 <div class="row" style="margin-bottom:12px"><span>Go to angle</span><input type="number" id="tgt" value="90" min="0" max="359" step="1"><span>&deg;</span>
  <button id="go">Go</button><small>stops within 2&deg;, on stall, or after 15 s</small></div>
 <div class="row"><span>Mark ends</span><button id="mlo">This is closed</button><button id="mhi">This is open</button><button id="mclr">Clear marks</button>
  <small id="marks"></small></div>
</div>
<div class="card"><h2>Events</h2><div id="log"></div></div>
<div class="card"><h2>Device</h2><small id="dev"></small></div>
</main>
<script>
const $=id=>document.getElementById(id);const hist=[];let fails=0;
const get=u=>fetch(u,{cache:'no-store'}).then(r=>r.json());
const spd=()=>+$('spd').value;$('spd').oninput=()=>$('spdv').textContent=spd()+'%';
function fmtUp(s){const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?h+'h '+m+'m':m+'m '+Math.floor(s%60)+'s'}
function draw(){const c=$('ch'),w=c.clientWidth,h=c.clientHeight,d=devicePixelRatio||1;c.width=w*d;c.height=h*d;const g=c.getContext('2d');g.scale(d,d);
 const cs=getComputedStyle(document.documentElement),mut=cs.getPropertyValue('--mut'),line=cs.getPropertyValue('--line'),acc=cs.getPropertyValue('--acc').trim();
 const now=Date.now(),pts=hist.filter(p=>now-p.t<60000);g.clearRect(0,0,w,h);
 const L=36,B=18,W=w-L-6,H=h-B-6,x=t=>L+W*(1-(now-t)/60000),y=a=>6+H*(1-a/360);
 g.strokeStyle=line;g.fillStyle=mut;g.font='11px system-ui';g.lineWidth=1;
 for(const a of [0,90,180,270,360]){g.beginPath();g.moveTo(L,y(a));g.lineTo(L+W,y(a));g.stroke();g.fillText(a+'°',2,y(a)+4)}
 g.fillStyle='rgba(99,164,255,0.18)';for(const p of pts)if(p.m)g.fillRect(x(p.t)-2,6,4,H);
 g.strokeStyle=acc;g.lineWidth=2;g.beginPath();let pen=false,prev=null;
 for(const p of pts){if(p.a==null){pen=false;prev=null;continue}if(prev!=null&&Math.abs(p.a-prev)>180)pen=false;
  pen?g.lineTo(x(p.t),y(p.a)):g.moveTo(x(p.t),y(p.a));pen=true;prev=p.a}g.stroke()}
async function poll(){try{const s=await get('/s');fails=0;$('conn').textContent='live · '+s.ip;
 $('pn').textContent=s.port+1;document.querySelectorAll('.pb').forEach(b=>b.classList.toggle('sel',+b.dataset.p==s.port));
 const run=s.dir!=0;$('ang').textContent=s.en&&s.ang!=null?s.ang.toFixed(1)+'°':'EN off';
 $('pct').textContent=s.pct!=null?Math.round(s.pct)+'%':'mark ends';
 $('mot').textContent=run?(s.dir>0?'forward ':'reverse ')+Math.round(s.duty*100/255)+'%':(s.tgt!=null?'seeking':'braked');
 $('en').innerHTML=s.en?'<span class=on>on</span>':'<span class=off>asleep</span>';
 $('vbat').textContent=s.vbat.toFixed(2)+' V';$('vin').textContent=s.vin.toFixed(2)+' V';
 $('mv').textContent=s.en?Math.round(s.mv)+' mV':'--';$('rssi').textContent=s.rssi+' dBm';
 $('temp').textContent=s.temp.toFixed(0)+' °C';$('up').textContent=fmtUp(s.up);
 $('marks').textContent=(s.lo!=null?'closed '+s.lo.toFixed(1)+'°':'')+(s.hi!=null?'  open '+s.hi.toFixed(1)+'°':'');
 $('log').textContent=s.log.slice().reverse().join('\n');$('dev').textContent='IP '+s.ip+' · heap '+Math.round(s.heap/1024)+' kB free · last reset: '+s.rst+' · firmware built '+s.build;
 hist.push({t:Date.now(),a:s.en?s.ang:null,m:run});while(hist.length>400)hist.shift();draw()}
 catch(e){if(++fails>3)$('conn').textContent='offline - retrying'}}
setInterval(poll,200);poll();addEventListener('resize',draw);
const cmd=k=>get('/c?k='+k);$('stop').onclick=()=>cmd('s');$('enOn').onclick=()=>cmd('e');$('enOff').onclick=()=>cmd('x');
function holdBtn(b,d){let t=null;const go=()=>get('/m?d='+d+'&p='+spd()+'&ms=400');
 const down=e=>{e.preventDefault();if(t)return;go();t=setInterval(go,150)};const up=()=>{if(!t)return;clearInterval(t);t=null;cmd('s')};
 b.addEventListener('pointerdown',down);['pointerup','pointerleave','pointercancel'].forEach(ev=>b.addEventListener(ev,up))}
holdBtn($('hf'),'f');holdBtn($('hr'),'r');
$('tf').onclick=()=>get('/m?d=f&p='+spd()+'&ms='+$('tms').value);$('tr').onclick=()=>get('/m?d=r&p='+spd()+'&ms='+$('tms').value);
$('go').onclick=()=>get('/g?a='+$('tgt').value+'&p='+spd());
document.querySelectorAll('.pb').forEach(b=>b.onclick=()=>{hist.length=0;get('/p?n='+b.dataset.p)});
$('mlo').onclick=()=>get('/k?w=lo');$('mhi').onclick=()=>get('/k?w=hi');$('mclr').onclick=()=>get('/k?w=clr');
addEventListener('keydown',e=>{if(e.key==' '||e.key=='Escape'){e.preventDefault();cmd('s')}});
</script></body></html>)HTML";

const char *resetReason() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power on";
    case ESP_RST_SW: return "software / update";
    case ESP_RST_PANIC: return "crash";
    case ESP_RST_BROWNOUT: return "brownout (supply too low)";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "watchdog";
    case ESP_RST_USB: return "USB";
    default: return "other";
  }
}

void sendOk() { web.send(200, "application/json", "{\"ok\":1}"); }

String num(float v, int dp) { return isnan(v) ? String("null") : String(v, dp); }

void handleStatus() {
  String j;
  j.reserve(1200);
  j += "{\"port\":"; j += port;
  j += ",\"en\":"; j += en ? 1 : 0;
  j += ",\"dir\":"; j += dir;
  j += ",\"duty\":"; j += duty;
  j += ",\"ang\":"; j += num(angle, 1);
  j += ",\"mv\":"; j += String(angleMv, 0);
  j += ",\"vbat\":"; j += String(vbat, 2);
  j += ",\"vin\":"; j += String(vin, 2);
  j += ",\"tgt\":"; j += num(target, 1);
  j += ",\"lo\":"; j += num(markLo, 1);
  j += ",\"hi\":"; j += num(markHi, 1);
  float pct = NAN;
  if (!isnan(markLo) && !isnan(markHi) && !isnan(angle) && fabsf(angDiff(markHi, markLo)) > 1)
    pct = angDiff(angle, markLo) / angDiff(markHi, markLo) * 100.0f;
  j += ",\"pct\":"; j += num(pct, 1);
  j += ",\"rssi\":"; j += WiFi.RSSI();
  j += ",\"temp\":"; j += String(temperatureRead(), 1);
  j += ",\"up\":"; j += millis() / 1000;
  j += ",\"heap\":"; j += ESP.getFreeHeap();
  j += ",\"ip\":\""; j += WiFi.localIP().toString(); j += "\"";
  j += ",\"rst\":\""; j += resetReason(); j += "\"";
  j += ",\"build\":\"" __DATE__ " " __TIME__ "\"";
  j += ",\"log\":[";
  int n = min(logSeq, 12);
  for (int k = 0; k < n; k++) {
    String s = logLines[(logSeq - n + k) % 12];
    s.replace("\"", "'");
    j += (k ? ",\"" : "\""); j += s; j += "\"";
  }
  j += "]}";
  web.send(200, "application/json", j);
}

void setupWeb() {
  web.on("/", []() { web.send_P(200, "text/html", PAGE); });
  web.on("/s", handleStatus);
  web.on("/c", []() { String k = web.arg("k"); if (k.length()) command(k[0]); sendOk(); });
  web.on("/m", []() {
    int d = web.arg("d") == "r" ? -1 : 1;
    bool fresh = dir != d;
    target = NAN;
    startMove(d, web.arg("p").toInt(), web.arg("ms").toInt());
    if (fresh) event("%s %d%% (%ld ms)", d > 0 ? "forward" : "reverse", duty * 100 / 255, web.arg("ms").toInt());
    sendOk();
  });
  web.on("/g", []() {
    if (!en) { setEn(true); delay(30); angleMv = readMv(PIN_ANGLE); angle = angleMv / 3300.0f * 360.0f; }
    target = fmodf(web.arg("a").toFloat() + 360.0f, 360.0f);
    duty = constrain((int)web.arg("p").toInt(), 10, 100) * 255 / 100;
    moveStart = millis(); stallT = millis(); stallRef = angle;
    event("go to %.1f (from %.1f)", target, angle);
    sendOk();
  });
  web.on("/k", []() {
    String w = web.arg("w");
    if (w == "lo" && !isnan(angle)) markLo = angle;
    else if (w == "hi" && !isnan(angle)) markHi = angle;
    else if (w == "clr") markLo = markHi = NAN;
    char k[4];
    snprintf(k, sizeof k, "lo%d", port + 1); prefs.putFloat(k, markLo);
    snprintf(k, sizeof k, "hi%d", port + 1); prefs.putFloat(k, markHi);
    event("marks: closed %.1f, open %.1f", markLo, markHi);
    sendOk();
  });
  web.on("/p", []() { selectPort(web.arg("n").toInt()); sendOk(); });
  web.onNotFound([]() { web.send(404, "text/plain", "not found"); });
  web.begin();
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  for (int i = 0; i < PORTS; i++) {             // every driver asleep, every motor braked
    pinMode(P_EN[i], OUTPUT);
    digitalWrite(P_EN[i], LOW);
    ledcAttach(P_IN1[i], PWM_HZ, PWM_BITS);
    ledcAttach(P_IN2[i], PWM_HZ, PWM_BITS);
    ledcWrite(P_IN1[i], 255);
    ledcWrite(P_IN2[i], 255);
    analogSetPinAttenuation(P_ANG[i], ADC_11db);
  }
  analogSetPinAttenuation(PIN_VBAT, ADC_11db);
  analogSetPinAttenuation(PIN_VIN, ADC_11db);
  drive();
  prefs.begin("pcb", false);
  markLo = prefs.getFloat("lo1", NAN);
  markHi = prefs.getFloat("hi1", NAN);

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);   // up to 10 s; keeps trying after
  MDNS.begin(HOSTNAME);
  ArduinoOTA.setHostname(HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { setEn(false); for (int i = 0; i < PORTS; i++) digitalWrite(P_EN[i], LOW); });   // all off while updating
  ArduinoOTA.begin();
  telnet.begin();
  setupWeb();
  MDNS.addService("http", "tcp", 80);

  event("boot (%s)", resetReason());
  say("pcb_test: p port, e/x EN, f/r/s motor, 0-9 duty, a angle stream, v voltages\n");
  if (WiFi.status() == WL_CONNECTED) say("Wi-Fi %s, web http://%s.local, telnet port 23\n", WiFi.localIP().toString().c_str(), HOSTNAME);
  else say("Wi-Fi not connected yet (check secrets.h)\n");
}

void loop() {
  ArduinoOTA.handle();
  web.handleClient();
  if (telnet.hasClient()) {                      // one Wi-Fi client at a time; a new one replaces the old
    if (client) client.stop();
    client = telnet.accept();
    client.print("pcb_test over Wi-Fi: p port, e/x EN, f/r/s motor, 0-9 duty, a angle stream, v voltages\n");
  }
  while (Serial.available()) command(Serial.read());
  while (client && client.connected() && client.available()) command(client.read());

  static uint32_t lastS = 0;
  uint32_t now = millis();
  if (now - lastS >= 20) {                       // sensors, 50 Hz
    lastS = now;
    vbat = readMv(PIN_VBAT) * 2.0f / 1000.0f;
    vin = readMv(PIN_VIN) * 2.0f / 1000.0f;
    if (en) { angleMv = readMv(PIN_ANGLE); angle = angleMv / 3300.0f * 360.0f; }
  }

  // timed moves
  if (dir != 0 && isnan(target) && moveUntil && (int32_t)(now - moveUntil) >= 0) stopMotor("time");
  // go-to-angle
  if (!isnan(target) && en && !isnan(angle)) {
    float err = angDiff(target, angle);
    if (fabsf(err) <= GOTO_TOL) stopMotor("reached");
    else {
      int d = err > 0 ? 1 : -1;
      if (d != dir) { dir = d; stallT = now; stallRef = angle; }
      drive();
      if (now - moveStart > MAX_MOVE_MS) stopMotor("15 s limit");
    }
  }
  // stall: running, but the angle hasn't moved in STALL_MS
  if (dir != 0 && en && !isnan(angle) && now - moveStart > STALL_MS && now - stallT >= STALL_MS) {
    if (fabsf(angDiff(angle, stallRef)) < STALL_DEG) stopMotor("stall (angle not changing)");
    stallT = now; stallRef = angle;
  }

  static uint32_t lastA = 0;
  if (streaming && now - lastA > 200) {
    lastA = now;
    say("port %d angle %.1f deg  %s\n", port + 1, en ? angle : 0.0f, en ? "" : "(EN off: not valid)");
  }
}
