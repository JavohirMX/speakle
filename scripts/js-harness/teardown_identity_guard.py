import json,time,urllib.request
import websocket
def connect(url):
    ws=websocket.create_connection(url,suppress_origin=True);mid=[0]
    def cmd(method,params=None):
        mid[0]+=1;ws.send(json.dumps({'id':mid[0],'method':method,'params':params or {}}))
        while True:
            m=json.loads(ws.recv())
            if m.get('id')==mid[0]:return m
    return ws,cmd
t=json.load(urllib.request.urlopen('http://127.0.0.1:9223/json'))
pg=[x for x in t if x['type']=='page'][0]
ws,cmd=connect(pg['webSocketDebuggerUrl'])
cmd('Page.enable');cmd('Runtime.enable')
def ev(expr):
    r=cmd('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})['result']
    return r['result'].get('value'), r.get('exceptionDetails',{}).get('text','')
cmd('Page.navigate',{'url':'http://127.0.0.1:8000/users/login/'});time.sleep(2)
ev("document.getElementById('id_username').value='a11ydemo';document.getElementById('id_password').value='fixture-pass-123';")
ev("document.querySelector('form').submit();");time.sleep(2.5)
cmd('Page.navigate',{'url':'http://127.0.0.1:8000/chats/room/ed698d6a-d3d0-458f-8c72-fc81e42f51bb/'});time.sleep(4)
v,ex = ev("""
(async () => {
  const proto = VideoChat.prototype;
  function mkFake() {
    const fake = Object.create(proto);
    fake.userId = 1; fake.isAutoStarting = true; fake.isCallActive = false;
    fake.iceCandidateQueue = []; fake.localStream = null;
    fake.sent = [];
    fake.ws = { readyState: 1, send(s){ fake.sent.push(s); } };
    fake.messages = []; fake.addChatMessage = function(m){ fake.messages.push(m); };
    fake.startTimer = function(){}; fake.updateCallButtons = function(){};
    fake.showRemoteVideoPlaceholder = function(){};
    fake.stopTimer = function(){};
    return fake;
  }
  function mkPc(tag, mid) {
    return { tag, closed:false,
      setRemoteDescription: async function(){ await new Promise(r=>setTimeout(r,50)); if (mid) mid(); },
      addIceCandidate: async function(){ this.ice=(this.ice||0)+1; },
      createAnswer: async function(){ this.created=(this.created||0)+1; return {type:'answer',sdp:tag}; },
      setLocalDescription: async function(){ this.local=true; },
      close(){ this.closed=true; } };
  }
  const out = {};
  // A: real teardown path mid-await (resetPeerConnection = what resetCall/user_left call)
  { const f = mkFake(); const old = mkPc('old', () => proto.resetPeerConnection.call(f)); f.pc = old;
    await proto.handleOffer.call(f, {offer:{type:'offer',sdp:'y'}, sender_id: 999});
    out.A_realTeardown = {messages: f.messages, answersSent: f.sent.length, oldClosed: old.closed, pcNull: f.pc===null}; }
  // B: replacement pc swapped in mid-await (teardown + new offer scenario)
  { const f = mkFake(); let npc;
    const old = mkPc('old', () => { f.pc = null; npc = mkPc('new'); f.pc = npc; }); f.pc = old;
    await proto.handleOffer.call(f, {offer:{type:'offer',sdp:'y'}, sender_id: 999});
    out.B_replacement = {messages: f.messages, answersSent: f.sent.length, newCreateAnswerCalls: npc.created||0, newLocalDesc: !!npc.local}; }
  // C: happy path, no interleaving
  { const f = mkFake(); const pc = mkPc('ok', null); f.pc = pc;
    await proto.handleOffer.call(f, {offer:{type:'offer',sdp:'y'}, sender_id: 999});
    out.C_happy = {messages: f.messages, answersSent: f.sent.length, isCallActive: f.isCallActive, localDesc: !!pc.local}; }
  return JSON.stringify(out);
})()
""")
print('shot16:', v, ex)
ws.close()
