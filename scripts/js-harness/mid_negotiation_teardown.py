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
    return cmd('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})['result']
cmd('Page.navigate',{'url':'http://127.0.0.1:8000/users/login/'});time.sleep(2)
ev("document.getElementById('id_username').value='a11ydemo';document.getElementById('id_password').value='fixture-pass-123';")
ev("document.querySelector('form').submit();");time.sleep(2.5)
cmd('Page.navigate',{'url':'http://127.0.0.1:8000/chats/room/ed698d6a-d3d0-458f-8c72-fc81e42f51bb/'});time.sleep(4)
r = ev("""
(async () => {
  const proto = VideoChat.prototype;
  const fake = Object.create(proto);
  fake.userId = 1;
  fake.isAutoStarting = true;
  fake.isCallActive = false;
  fake.iceCandidateQueue = [];
  fake.localStream = null;
  fake.ws = { send(s){ this.sent = (this.sent||[]); this.sent.push(s); } };
  fake.messages = [];
  fake.addChatMessage = function(m){ fake.messages.push(m); };
  fake.startTimer = function(){};
  fake.updateCallButtons = function(){};
  // peer connection stub: teardown (resetCall -> pc=null) lands during the await,
  // exactly as when the user ends the call / partner hangup arrives mid-negotiation
  fake.pc = {
    setRemoteDescription: async function(){ await new Promise(r=>setTimeout(r,50)); fake.pc = null; },
    addIceCandidate: async function(){},
    createAnswer: async function(){ return {type:'answer',sdp:'x'}; },
    setLocalDescription: async function(){},
  };
  await proto.handleOffer.call(fake, {offer:{type:'offer',sdp:'y'}, sender_id: 999});
  return JSON.stringify({messages: fake.messages, wsSent: (fake.ws.sent||[]).length, isCallActive: fake.isCallActive});
})()
""")
print('handleOffer with mid-await teardown:', r['result'].get('value'))
ws.close()
