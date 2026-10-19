"""Community-only WebSocket delivery; game sockets and authority are separate."""
import asyncio
import json
import logging
import re
import time

from aiohttp import WSMsgType, web

from social_platform import COMMUNITY_CHAT_MAX, PlatformError, normalize_community_id, now_ms

LOG = logging.getLogger(__name__)


async def serve(api, request):
    user = await api._user(request)
    uid = str(user['id'])
    cid = normalize_community_id(request.match_info.get('community_id'))
    await api.platform.community_rules.access(uid, cid)
    if not await api.platform.allow_rate(f'community-stream:{uid}', 30, 60):
        raise PlatformError('RATE_LIMIT', 'اتصالات كثيرة؛ حاول لاحقًا', 429)

    socket = web.WebSocketResponse(heartbeat=15, max_msg_size=4096, compress=False)
    write_lock = asyncio.Lock()

    async def send(event):
        event=await api.platform.safety.community_event(uid,event)
        if event is None:return
        async with write_lock:
            await asyncio.wait_for(socket.send_json(event), 5)

    async def deliver(queue):
        try:
            await send({'type': 'snapshot', 'messages': await api.platform.community_chat_history(cid, COMMUNITY_CHAT_MAX),
                        'deliveryState': api.platform.live.status()})
            checked = time.monotonic()
            while not socket.closed:
                try:
                    event = await asyncio.wait_for(queue.get(), 12)
                except TimeoutError:
                    event = {'type': 'resync'}
                if event.get('targetUserId') and event['targetUserId']!=uid:continue
                if event.get('type') == 'closed':
                    break
                if time.monotonic() - checked >= 12:
                    try:
                        await api._user(request)
                        await api.platform.community_rules.access(uid, cid)
                    except PlatformError as error:
                        await send({'type': 'access_denied', 'error': error.code})
                        break
                    checked = time.monotonic()
                if event.get('type') == 'resync':
                    event = {'type': 'snapshot', 'messages': await api.platform.community_chat_history(cid, COMMUNITY_CHAT_MAX),
                             'deliveryState': api.platform.live.status()}
                await send(event)
        except (ConnectionError, TimeoutError, RuntimeError):
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception('Community delivery failed')
        finally:
            await socket.close()

    async with api.platform.live.subscribe(cid, uid) as queue:
        await socket.prepare(request)
        delivery = asyncio.create_task(deliver(queue), name='community-socket-delivery')
        window, frames = time.monotonic(), 0
        try:
            async for item in socket:
                if item.type != WSMsgType.TEXT:
                    if item.type == WSMsgType.BINARY:
                        await socket.close(code=1003, message=b'JSON text required')
                    break
                if time.monotonic() - window >= 10:
                    window, frames = time.monotonic(), 0
                frames += 1
                if frames > 40:
                    await socket.close(code=1008, message=b'too many frames')
                    break
                nonce = None
                try:
                    body = json.loads(item.data)
                    if not isinstance(body, dict):
                        raise ValueError
                    raw_nonce = body.get('clientMessageId')
                    if isinstance(raw_nonce, str) and re.fullmatch(r'[A-Za-z0-9_-]{8,64}', raw_nonce):
                        nonce = raw_nonce
                    if body.get('type') == 'ping':
                        await send({'type': 'pong', 'serverTime': now_ms()})
                        continue
                    if body.get('type') != 'chat_send':
                        raise PlatformError('UNKNOWN_MESSAGE', 'نوع الرسالة غير صالح')
                    if nonce is None:
                        raise PlatformError('BAD_MESSAGE_ID', 'معرّف الرسالة غير صالح')
                    # Session identity and authority are never taken from frames.
                    user = await api._user(request)
                    entry = await api.community_chat_entry(user, cid, body)
                    await send({'type': 'ack', 'message': entry})
                except (ValueError, TypeError):
                    await send({'type': 'error', 'error': 'BAD_JSON', 'message': 'الطلب غير صالح'})
                except PlatformError as error:
                    await send({'type': 'error', 'error': error.code, 'message': error.message,
                                **({'clientMessageId': nonce} if nonce else {})})
                    if error.code in {'AUTH_REQUIRED', 'COMMUNITY_BANNED', 'COMMUNITY_KICKED'}:
                        await socket.close(code=4003, message=b'access denied')
                        break
                except (ConnectionError, TimeoutError, RuntimeError):
                    raise
                except Exception:
                    LOG.exception('Community message failed')
                    await send({'type': 'error', 'error': 'SERVER_ERROR', 'message': 'تعذر إرسال الرسالة',
                                **({'clientMessageId': nonce} if nonce else {})})
        except (ConnectionError, TimeoutError, RuntimeError):
            pass
        finally:
            delivery.cancel()
            await asyncio.gather(delivery, return_exceptions=True)
            await socket.close()
    return socket
