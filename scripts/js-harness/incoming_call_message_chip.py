import json,time,urllib.request
import websocket

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

def connect(url):
    ws=websocket.create_connection(url,suppress_origin=True);mid=[0]
    def cmd(method,params=None):
        mid[0]+=1;ws.send(json.dumps({'id':mid[0],'method':method,'params':params or {}}))
        while True:
            m=json.loads(ws.recv())
            if m.get('id')==mid[0]:return m
    def drain(dur=1.0):
        end=time.time()+dur;ev=[]
        ws.settimeout(0.3)
        while time.time()<end:
            try:ev.append(json.loads(ws.recv()))
            except:pass
        ws.settimeout(30);return ev
    return ws,cmd,drain
t=json.load(urllib.request.urlopen(CDP + '/json'))
pg=[x for x in t if x['type']=='page'][0]
ws,cmd,drain=connect(pg['webSocketDebuggerUrl'])
cmd('Network.enable');cmd('Network.enable');cmd('Network.clearBrowserCookies');cmd('Page.enable');cmd('Runtime.enable');cmd('Log.enable')
cmd('Page.navigate',{'url':BASE + '/users/login/'});time.sleep(2)
cmd('Runtime.evaluate',{'expression':"document.getElementById('id_username').value='"+FXU+"';document.getElementById('id_password').value='"+FXP+"';"})
cmd('Runtime.evaluate',{'expression':"document.querySelector('form').submit();"});time.sleep(2.5)
cmd('Runtime.evaluate',{'expression':"currentGlobalIncomingInvitation={id:"+str(FXI)+",match_id:"+str(FXM)+",caller_id:2,caller_username:'"+FXPARTNER+"'};"})
r=cmd('Runtime.evaluate',{'expression':"sendQuickMessage(); 'sent'"})
time.sleep(2.5)
ev=drain(0.5)
p=cmd('Runtime.evaluate',{'expression':'location.pathname'})['result']['result'].get('value')
errs=[e for e in ev if e.get('method')=='Log.entryAdded' and e['params']['entry'].get('level')=='error']
print('pathname after Message:',p)
print('navigated to match', FXM, ':', p=='/chats/match/'+str(FXM)+'/')
print('page errors:',[e['params']['entry']['text'][:100] for e in errs])
ws.close()
