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
FXV = _fx.get('video_room_id', 'ed698d6a-d3d0-458f-8c72-fc81e42f51bb')

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
    r=cmd('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})['result']
    return r['result'].get('value'), r.get('exceptionDetails',{}).get('text','')
cmd('Page.navigate',{'url':BASE + '/users/login/'});time.sleep(2)
ev("document.getElementById('id_username').value='"+FXU+"';document.getElementById('id_password').value='"+FXP+"';")
ev("document.querySelector('form').submit();");time.sleep(2.5)
cmd('Page.navigate',{'url':BASE + '/chats/room/' + FXV + '/'});time.sleep(4)
v,ex = ev("""
(async () => {
  const proto = VideoChat.prototype;
  function mkFake() {
    const fake = Object.create(proto);
    fake.userId = 1; fake.isAutoStarting = true; fake.isCallActive = false;
    fake.iceCandidateQueue = [];
    fake.localStream = { getTracks(){ return []; } };
    fake.sent = [];
    fake.ws = { readyState: 1, send(s){ fake.sent.push(JSON.parse(s).type); } };
    fake.messages = []; fake.addChatMessage = function(m){ fake.messages.push(m); };
    fake.startTimer = function(){ this.timerStarted = true; };
    fake.stopTimer = function(){};
    fake.updateCallButtons = function(){};
    fake.showRemoteVideoPlaceholder = function(){};
    fake.isVideoEnabled = true; fake.isAudioEnabled = true; fake.isMediaReady = true;
    return fake;
  }
  function mkPc(mid1, mid2) {
    return { closed:false,
      createOffer: async function(){ await new Promise(r=>setTimeout(r,40)); if (mid1) mid1(); return {type:'offer',sdp:'x'}; },
      setLocalDescription: async function(){ await new Promise(r=>setTimeout(r,40)); if (mid2) mid2(); },
      addTrack(){}, close(){ this.closed = true; } };
  }
  const out = {};
  // A: real teardown during createOffer await
  { const f = mkFake(); const pc = mkPc(() => proto.resetPeerConnection.call(f), null);
    f.createPeerConnection = function(){ f.pc = pc; };
    await proto.startCall.call(f);
    out.A_teardownDuringCreateOffer = {messages: f.messages, sent: f.sent, isCallActive: f.isCallActive}; }
  // B: real teardown during setLocalDescription await -> stale offer must NOT be sent
  { const f = mkFake(); const pc = mkPc(null, () => proto.resetPeerConnection.call(f));
    f.createPeerConnection = function(){ f.pc = pc; };
    await proto.startCall.call(f);
    out.B_teardownDuringSetLocal = {messages: f.messages, sent: f.sent, isCallActive: f.isCallActive, timerStarted: !!f.timerStarted}; }
  // C: happy path
  { const f = mkFake(); const pc = mkPc(null, null);
    f.createPeerConnection = function(){ f.pc = pc; };
    await proto.startCall.call(f);
    out.C_happy = {messages: f.messages, sent: f.sent, isCallActive: f.isCallActive, timerStarted: !!f.timerStarted}; }
  return JSON.stringify(out);
})()
""")
print('shot17:', v, ex)
ws.close()
