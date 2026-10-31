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
    return ws,cmd
t=json.load(urllib.request.urlopen(CDP + '/json'))
pg=[x for x in t if x['type']=='page'][0]
ws,cmd=connect(pg['webSocketDebuggerUrl'])
cmd('Network.enable');cmd('Network.clearBrowserCookies');cmd('Page.enable');cmd('Runtime.enable')
def ev(expr):
    return cmd('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})['result']
cmd('Page.navigate',{'url':BASE + '/users/login/'});time.sleep(2)
ev("document.getElementById('id_username').value='"+FXU+"';document.getElementById('id_password').value='"+FXP+"';")
ev("document.querySelector('form').submit();");time.sleep(2.5)
cmd('Page.navigate',{'url':BASE + '/chats/text/' + FXC + '/'});time.sleep(4)
r = ev("""
(async () => {
  const tc = window.textChat;
  const stuck = new WebSocket('ws://10.255.255.1/ws/x/');  // unroutable: stays CONNECTING
  const orig = tc.ws;
  tc.ws = stuck;
  tc.isTyping = false;
  let threw = null;
  try { tc.handleTyping(); } catch (e) { threw = e.name; }
  // stopTyping path
  tc.isTyping = true;
  let threw2 = null;
  try { tc.stopTyping(); } catch (e) { threw2 = e.name; }
  tc.ws = orig;
  return JSON.stringify({handleTyping_threw: threw, stopTyping_threw: threw2, readyState: stuck.readyState});
})()
""")
print('text_chat typing on CONNECTING ws:', r['result'].get('value'), r.get('exceptionDetails',{}).get('text',''))
ws.close()
