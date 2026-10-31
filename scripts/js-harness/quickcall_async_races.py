import json, sys, time, urllib.request
from websocket import create_connection

import os as _os, json as _json
try:
    _fx = _json.load(open(_os.path.join(_os.path.dirname(__file__), 'fixtures.json')))
except Exception:
    _fx = {}
BASE = _fx.get('base_url', 'http://127.0.0.1:8000')
CDP = _fx.get('cdp_url', 'http://127.0.0.1:9223')
FXU = _fx.get('user', 'a11ydemo'); FXP = _fx.get('password', 'fixture-pass-123')
FXPARTNER = _fx.get('partner', 'fixturepartner'); FXM = _fx.get('match_id', 2)
FXV = _fx.get('video_room_id', 'ed698d6a-d3d0-458f-8c72-fc81e42f51bb')
FXC = _fx.get('chat_room_id', '9edbfeae-f6ac-4fbf-9ce1-880b732cf9fe')
FXI = _fx.get('invitation_id', 1)

ts=json.load(urllib.request.urlopen(CDP + '/json'))
t=[x for x in ts if x.get('type')=='page'][0]
ws=create_connection(t['webSocketDebuggerUrl'], timeout=60); mid=[0]
def cmd(m, **p):
    mid[0]+=1; ws.send(json.dumps({'id':mid[0],'method':m,'params':p}))
    while True:
        r=json.loads(ws.recv())
        if r.get('id')==mid[0]:
            if 'error' in r: raise Exception(r['error'])
            return r.get('result',{})
def evraw(e): return cmd('Runtime.evaluate', expression=e, returnByValue=True, awaitPromise=True)
def ev(e): return evraw(e).get('result',{}).get('value')
cmd('Network.enable');cmd('Network.clearBrowserCookies')
cmd('Emulation.setDeviceMetricsOverride', width=1440, height=900, deviceScaleFactor=1, mobile=False)
cmd('Page.navigate', url=BASE+'/users/login/'); time.sleep(2)
ev("var u=document.getElementById('id_username'); u.value='"+FXU+"'; document.getElementById('id_password').value='"+FXP+"'; u.closest('form').submit(); 1")
time.sleep(3)
ev("""(function(){
  window.__log={fetch:[]}; window.__defer={};
  const of=window.fetch;
  window.fetch=function(url,opts){
    var u=String(url), m=(opts&&opts.method)||'GET';
    window.__log.fetch.push({url:u,method:m});
    if(u.indexOf('/api/partner-availability/')>=0){return new Promise(function(res){window.__defer.availability=function(){res({json:function(){return Promise.resolve({is_online:true});}});};});}
    if(u.indexOf('/api/send-invitation/')>=0){return new Promise(function(res){window.__defer.send=function(){res({json:function(){return Promise.resolve({success:true,invitation_id:777});}});};});}
    if(u.indexOf('/api/cancel-invitation/')>=0){return Promise.resolve({json:function(){return Promise.resolve({success:true});}});}
    return of.apply(this,arguments);
  };
  window.navigateToUrl=function(){}; return 1;})()""")
# A refined: cancel-during-send, then look for visible error toast
ev("initiateVideoCallGlobal("+str(FXM)+",'"+FXPARTNER+"',{redirectOnAccept:false}); 1"); time.sleep(0.5)
ev("window.__defer.availability(); 1"); time.sleep(1)
ev("[...document.querySelectorAll('#quickCallModal button')].find(b=>b.textContent.includes('Send Invitation')).click(); 1"); time.sleep(0.3)
ev("closeQuickCallModal(); 1"); time.sleep(0.3)
ev("window.__defer.send(); 1"); time.sleep(1.5)
print('A: orphan cancel POST:', ev("window.__log.fetch.some(function(f){return f.url.indexOf('/api/cancel-invitation/777/')>=0})"))
print('A: visible error toast:', ev("!![...document.querySelectorAll('body *')].find(function(d){var s=getComputedStyle(d);return d.children.length===0&&s.display!=='none'&&s.visibility!=='hidden'&&d.textContent.indexOf('Failed to send invitation')===0;})"))
# C refined: late events, capture exceptionDetails from evaluate
ev("(document.getElementById('quickCallModal')||{remove(){}}).remove(); window.closeQuickCallModal(); 1"); time.sleep(0.3)
r1=evraw("window.invitationDeclined(); 1")
print('C declined exception:', 'exceptionDetails' in r1, (r1.get('exceptionDetails',{}).get('text') or ''))
r2=evraw("window.invitationExpired(); 1")
print('C expired exception:', 'exceptionDetails' in r2, (r2.get('exceptionDetails',{}).get('text') or ''))
r3=evraw("window.invitationAccepted('/chats/room/x/'); 1")
print('C accepted exception:', 'exceptionDetails' in r3, (r3.get('exceptionDetails',{}).get('text') or ''))
