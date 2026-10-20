"""Human-reviewed reports; a reporter never decides a global account sanction."""
import json
from contextlib import asynccontextmanager

REASONS = {
    'harassment': 'مضايقة أو تنمر',
    'cheating': 'غش في اللعب',
    'abuse': 'إساءة أو خطاب كراهية',
    'profile': 'اسم مستخدم أو صورة غير لائقة',
    'threat': 'تهديد بالعنف في الحياة الواقعية',
    'exploitation': 'استغلال أو تحرش جنسي',
    'spam': 'رسائل مزعجة أو احتيال',
    'other': 'سبب آخر',
}

@asynccontextmanager
async def transaction(service, keys):
    # PostgreSQL locks the shared report list and account in one DB transaction.
    if service.r is not None and hasattr(service.r, 'pool'):
        async with service.accounts.transaction(keys): yield
    else:
        async with service.lock: yield

async def store_report(service, report):
    # Caller owns the report-list transaction (and block keys when requested).
    if service.r is None:
        service.mem_reports.insert(0, report)
        del service.mem_reports[5000:]
    else:
        pipeline = service.r.pipeline(transaction=True)
        pipeline.lpush(service.k_reports(), json.dumps(report,ensure_ascii=False,separators=(',',':')))
        pipeline.ltrim(service.k_reports(),0,4999)
        await pipeline.execute()

async def review(service, actor, report_id, decision, note=''):
    from social_platform import PlatformError, now_ms
    if not isinstance(decision,str) or decision not in {'ban', 'dismiss'}:
        raise PlatformError('BAD_REVIEW', 'اختر اتخاذ إجراء أو تجاهل')
    reports = await service.list_reports(5000)
    row = next((r for r in reports if r.get('id') == report_id), None)
    if row is None: raise PlatformError('REPORT_NOT_FOUND', 'البلاغ غير موجود', 404)
    target_id = row['targetId']
    keys = [service.k_reports(), service.k_user(target_id), service.k_user(actor['id'])]
    async with transaction(service, keys):
        current_actor = await service.get_user(actor['id'])
        if not current_actor or current_actor.get('role') != 'admin' or current_actor.get('banned') == '1':
            raise PlatformError('ADMIN_REQUIRED', 'لا تملك صلاحية مراجعة البلاغات', 403)
        reports = await service.list_reports(5000)
        row = next((r for r in reports if r.get('id') == report_id), None)
        if row is None: raise PlatformError('REPORT_NOT_FOUND', 'البلاغ غير موجود', 404)
        if row.get('status', 'open') != 'open':
            raise PlatformError('REPORT_REVIEWED', 'تمت مراجعة هذا البلاغ مسبقًا', 409)
        if decision == 'ban':
            target = await service.get_user(target_id)
            if target_id == actor['id']: raise PlatformError('CANNOT_BAN_SELF', 'لا يمكنك حظر حسابك الإداري')
            if current_actor.get('role') != 'admin' and target and target.get('role') in {'admin', 'moderator'}:
                raise PlatformError('ADMIN_REQUIRED', 'لا تملك صلاحية حظر هذا الحساب', 403)
            if not target: raise PlatformError('USER_NOT_FOUND', 'المستخدم غير موجود', 404)
            if target.get('banned') != '1': await service.set_banned(target_id, True)
        row.update(status='actioned' if decision == 'ban' else 'dismissed', decision=decision,
                   reviewedAt=now_ms(), actorId=actor['id'], reviewNote=' '.join(str(note).split())[:500])
        if service.r is None:
            service.mem_reports[:] = reports
        else:
            await service.r.delete(service.k_reports())
            if reports:
                await service.r.rpush(service.k_reports(), *(json.dumps(r,ensure_ascii=False,separators=(',',':')) for r in reports))
    return row
