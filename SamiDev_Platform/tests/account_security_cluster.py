"""Real two-gateway HTTP, SSE and WebSocket revocation (no Firebase network)."""
import asyncio
import hashlib
import json
import secrets
import aiohttp
from realtime_cluster_fixture import Cluster


async def main():
    cluster=Cluster(gateways=2,hosts=1)
    socket=None
    try:
        await cluster.start()
        cookies=await cluster.seed(2)
        uid=cluster.prefix+'_0'
        token=secrets.token_urlsafe(32)
        await cluster.r.set(cluster.prefix+':session:'+hashlib.sha256(token.encode()).hexdigest(),json.dumps({'uid':uid,'version':'0'}),ex=3600)
        remote={**cookies[0],'Cookie':'samidev_session='+token,'User-Agent':'Mozilla/5.0 (iPhone) Safari/1'}
        async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as client:
            async def req(gateway,method,path,headers,body=None):
                async with client.request(method,cluster.urls[gateway]+path,headers=headers,json=body) as response:
                    data=await response.json()
                    assert response.status==200,(method,path,response.status,data)
                    return data
            # Enroll legacy cookies using real routes; legacy unknown devices must
            # be manageable, and HTTP/WS authority stays in the shared store.
            await req(1,'GET','/api/account/devices',remote)
            devices=(await req(0,'GET','/api/account/devices',cookies[0]))['devices']
            target=next(d for d in devices if not d['current'])
            ticket=await req(1,'POST','/api/game-ticket',remote,{'communityId':'majlis'})
            socket=await client.ws_connect(cluster.urls[1]+'/ws?ticket='+ticket['ticket'],headers=remote)
            await req(1,'POST','/api/communities/majlis/enter',remote,{})
            stream=await client.get(cluster.urls[1]+'/api/communities/majlis/events',headers=remote)
            assert stream.status==200
            assert (await stream.content.readline()).startswith(b'data: ')
            await req(0,'DELETE','/api/account/devices/'+target['id'],cookies[0])
            # Existing sockets and SSE must stop receiving protected state.
            async with asyncio.timeout(10):
                while True:
                    packet=await socket.receive()
                    if packet.type in {aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED}:break
            async with asyncio.timeout(16):
                payload=await stream.read()
                assert b'access_denied' in payload
            async with client.get(cluster.urls[1]+'/api/me',headers=remote) as response:assert response.status==401
            await req(1,'GET','/api/me',cookies[0])
            await req(0,'POST','/api/account/logout-all',cookies[0],{})
            async with client.get(cluster.urls[1]+'/api/me',headers=cookies[0]) as response:assert response.status==401
            await req(1,'GET','/api/me',cookies[1])
        print('ACCOUNT_SECURITY_TWO_GATEWAY_HTTP_WS_SSE_PASS')
    finally:
        if socket is not None:await socket.close()
        await cluster.close()


if __name__=='__main__':asyncio.run(main())
