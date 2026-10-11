import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from social_platform import PlatformService, PlatformError  # noqa: E402


async def main():
    p = PlatformService()
    giver = await p.create_user('profile_giver', 'Test-password-123', 'Giver')
    targets = [await p.create_user(f'profile_t{i}', 'Test-password-123', f'Target {i}') for i in range(6)]
    gid = str(giver['id'])

    profile = await p.public_profile(str(targets[0]['id']), gid)
    assert profile['wins'] == 0 and profile['reputation'] == 0
    assert profile['reputationDailyRemaining'] == 5
    assert profile['relation'] == 'none'

    first = await p.grant_reputation(gid, str(targets[0]['id']))
    assert first == {'reputation': 1, 'remaining': 4}
    try:
        await p.grant_reputation(gid, str(targets[0]['id']))
        raise AssertionError('duplicate daily reputation accepted')
    except PlatformError as exc:
        assert exc.code == 'REPUTATION_ALREADY_GIVEN'

    for i in range(1, 5):
        result = await p.grant_reputation(gid, str(targets[i]['id']))
        assert result['remaining'] == 4 - i
    try:
        await p.grant_reputation(gid, str(targets[5]['id']))
        raise AssertionError('daily reputation limit exceeded')
    except PlatformError as exc:
        assert exc.code == 'REPUTATION_DAILY_LIMIT'

    rid = 'ROOM1234'
    liked = await p.record_match_rating(gid, str(targets[0]['id']), rid, True)
    assert liked['liked'] is True and liked['reputation'] == 2
    try:
        await p.record_match_rating(gid, str(targets[0]['id']), rid, False)
        raise AssertionError('duplicate match rating accepted')
    except PlatformError as exc:
        assert exc.code == 'MATCH_ALREADY_RATED'

    disliked = await p.record_match_rating(gid, str(targets[0]['id']), 'ROOM5678', False)
    assert disliked['liked'] is False and disliked['reputation'] == 1
    # A dislike at zero is still recorded, but never creates negative reputation.
    zero_dislike = await p.record_match_rating(gid, str(targets[1]['id']), 'ROOMZERO', False)
    assert zero_dislike['liked'] is False and zero_dislike['reputation'] == 0

    report = await p.submit_report(gid, str(targets[0]['id']), message='test report', room_id=rid)
    assert report['status'] == 'open'
    reports = await p.list_reports()
    assert reports and reports[0]['id'] == report['id'] and reports[0]['message'] == 'test report'

    pending = await p.send_friend_request(giver, str(targets[0]['username']))
    assert pending['status'] == 'pending'
    rel = await p.relationship(gid, str(targets[0]['id']))
    assert rel == 'outgoing'

    print('PLAYER_PROFILE_SOCIAL_REGRESSION_PASS')


if __name__ == '__main__':
    asyncio.run(main())
