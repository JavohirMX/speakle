import json,time,urllib.request
import websocket
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
t=json.load(urllib.request.urlopen('http://127.0.0.1:9223/json'))
pg=[x for x in t if x['type']=='page'][0]
ws,cmd,drain=connect(pg['webSocketDebuggerUrl'])
cmd('Network.enable');cmd('Page.enable');cmd('Runtime.enable');cmd('Log.enable')
cmd('Page.navigate',{'url':'http://127.0.0.1:8000/users/login/'});time.sleep(2)
cmd('Runtime.evaluate',{'expression':"document.getElementById('id_username').value='a11ydemo';document.getElementById('id_password').value='fixture-pass-123';"})
cmd('Runtime.evaluate',{'expression':"document.querySelector('form').submit();"});time.sleep(2.5)
cmd('Runtime.evaluate',{'expression':"currentGlobalIncomingInvitation={id:1,match_id:2,caller_id:2,caller_username:'fixturepartner'};"})
r=cmd('Runtime.evaluate',{'expression':"sendQuickMessage(); 'sent'"})
time.sleep(2.5)
ev=drain(0.5)
p=cmd('Runtime.evaluate',{'expression':'location.pathname'})['result']['result'].get('value')
errs=[e for e in ev if e.get('method')=='Log.entryAdded' and e['params']['entry'].get('level')=='error']
print('pathname after Message:',p)
print('navigated to match 2:', p=='/chats/match/2/')
print('page errors:',[e['params']['entry']['text'][:100] for e in errs])
ws.close()
