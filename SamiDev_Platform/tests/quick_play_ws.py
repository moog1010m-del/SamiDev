"""Real authenticated concurrent quick matching across two production gateways."""
import asyncio, json
from collections import defaultdict
import aiohttp
from realtime_cluster_fixture import Cluster, receive

async def main():
    cluster=Cluster(gateways=2,hosts=1)
    sockets=[]
    try:
        await cluster.start()
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
            cookies=[]
            for i in range(12):
                headers={**cluster.base_headers,'X-Real-IP':f'10.71.0.{i+1}'}
                async with session.post(cluster.urls[i%2]+'/api/auth/register',headers=headers,json={'username':cluster.prefix+str(i),'password':'Test-password-123'}) as response:
                    assert response.status==200,await response.text()
                    cookies.append({**headers,'Cookie':'samidev_session='+response.cookies['samidev_session'].value})
            async def socket(index):
                ws=await session.ws_connect(cluster.urls[index%2]+'/ws',headers=cookies[index]);sockets.append(ws);return ws
            # Eight concurrent requests must fill four matches, never duplicate a seat.
            current=await asyncio.gather(*(socket(i) for i in range(8)))
            await asyncio.gather(*(ws.send_json({'type':'quick_play','preset':'pool-pyramid'}) for ws in current))
            assigned=await asyncio.gather(*(receive(ws,{'created','joined'}) for ws in current))
            groups=defaultdict(list)
            for ws,assignment in zip(current,assigned):
                assert assignment['quickPlay'] and assignment['settings']['gameType']==8
                groups[assignment['roomId']].append((ws,assignment))
            assert len(groups)==4 and all(sorted(a['seat'] for _,a in group)==[0,1] for group in groups.values())
            for group in groups.values():
                await asyncio.gather(*(receive(ws,{'start'}) for ws,_ in group))
                await asyncio.gather(*(ws.send_json({'type':'runtime_ready'}) for ws,_ in group))
                await asyncio.gather(*(receive(ws,{'begin_match'}) for ws,_ in group))
            group=next(iter(groups.values()));host=next(ws for ws,a in group if a['seat']==0)
            await host.send_json({'type':'resync'});state=await receive(host,{'resync_state'})
            await host.send_json({'type':'move','packet':{'i':'quick-cue','n':state['sequence'][0],'m':{'a':9,'rank':1}}})
            for ws,_ in group:assert (await receive(ws,{'move'}))['packet']['m']['rank']==1
            await host.send_json({'type':'resync'});state=await receive(host,{'resync_state'})
            await host.send_json({'type':'move','packet':{'i':'quick-shot','n':state['sequence'][0],'m':{'a':1,'st':.8,'an':1.5707963267948966,'sp':[0,0]}}})
            for ws,_ in group:assert (await receive(ws,{'move'}))['reveal']['pool']['pyramid']['mode']==8
            # Validation and separate preset pools, using fresh authenticated sockets.
            a,b,c,d=await asyncio.gather(*(socket(i) for i in range(8,12)))
            await a.send_json({'type':'quick_play','preset':'ranked-invented'})
            assert (await a.receive_json())['code']=='UNKNOWN_QUICK_MODE'
            await a.send_json({'type':'quick_play','preset':'pool-free','settings':{'winner':0}})
            assert (await a.receive_json())['code']=='INVALID_QUICK_FIELDS'
            await a.send_json({'type':'quick_play','preset':'pool-free'});one=await receive(a,{'created'})
            await b.send_json({'type':'quick_play','preset':'pool-scratch'});two=await receive(b,{'created'})
            assert one['roomId']!=two['roomId'] and one['settings']['gameType']==7 and two['settings']['gameType']==9
            duplicate=await socket(8)
            await duplicate.send_json({'type':'quick_play','preset':'pool-free'})
            assert (await receive_error(duplicate))['code']=='ACCOUNT_ALREADY_SEATED'
            await c.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':0}});manual=await receive(c,{'created'})
            await d.send_json({'type':'quick_play','preset':'pool-eight'});quick=await receive(d,{'created'})
            assert quick['roomId']!=manual['roomId'],'manual invitation rooms must not be consumed by matching'
            await a.send_json({'type':'leave_room'});await receive(a,{'left_room'})
            await duplicate.send_json({'type':'quick_play','preset':'pool-free'});replacement=await receive(duplicate,{'created'})
            assert replacement['roomId']!=one['roomId'],'cancelled waiting room must not trap the next search'
            for preset,capacity in [('pool-teams',4),('pool-three',3)]:
                team=await asyncio.gather(*(socket(i) for i in range(capacity)))
                await asyncio.gather(*(ws.send_json({'type':'quick_play','preset':preset}) for ws in team))
                assignments=await asyncio.gather(*(receive(ws,{'created','joined'}) for ws in team))
                assert len({p['roomId'] for p in assignments})==1
                assert sorted(p['seat'] for p in assignments)==list(range(capacity))
                await asyncio.gather(*(receive(ws,{'start'}) for ws in team))
            for preset,game in [('carrom-classic','carrom'),('uno-two','crazy8'),('football-two','tablesoccer')]:
                pair=await asyncio.gather(socket(10),socket(11))
                await asyncio.gather(*(ws.send_json({'type':'quick_play','preset':preset}) for ws in pair))
                assignments=await asyncio.gather(*(receive(ws,{'created','joined'}) for ws in pair))
                assert assignments[0]['roomId']==assignments[1]['roomId']
                assert all(p['settings']['gameId']==game for p in assignments)
                await asyncio.gather(*(receive(ws,{'start'}) for ws in pair))
                await asyncio.gather(*(ws.send_json({'type':'runtime_ready'}) for ws in pair))
                await asyncio.gather(*(receive(ws,{'begin_match'}) for ws in pair))
                for ws in pair:await ws.close()
            print(json.dumps({'ok':True,'concurrentPlayers':8,'matches':4,'checks':['cross-gateway matching','unique seats','normal start and ready','authoritative cue selection and physical shot fanout','preset isolation','same-account self-match rejected','forged fields rejected','manual rooms untouched','cancelled search replaced','three and four player queues fill','all four supported games start' ],'logs':str(cluster.folder)}))
    finally:
        for ws in sockets:await ws.close()
        await cluster.close()

async def receive_error(ws):
    async with asyncio.timeout(10):
        while True:
            packet=await ws.receive_json()
            if packet['type']=='error':return packet

if __name__=='__main__':asyncio.run(main())
