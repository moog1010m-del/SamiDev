"""The system username cannot be claimed through any public account flow."""
import asyncio
import os
import sys
from pathlib import Path

os.environ['SAMIDEV_FIREBASE_AUTH'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from social_platform import PlatformService, PlatformError, normalize_username

async def main():
    service = PlatformService()
    claims = {'uid': 'reservation-fixture', 'email': 'fixture@example.test'}
    user = await service.firebase_account({'uid': 'existing-fixture', 'email': 'existing@example.test'}, username='Existing_Player')
    original = dict(user)
    checks = 0
    for value in ('Plazr', 'plazr', 'PLAZR', 'pLaZr', ' Plazr '):
        try:
            normalize_username(value)
            raise AssertionError('reserved name normalized: '+value)
        except PlatformError as exc:
            assert exc.code == 'USERNAME_RESERVED' and exc.status == 409
        for operation in (
            lambda: service.create_user(value, 'Unused-password-123'),
            lambda: service.firebase_account(claims, username=value),
            lambda: service.accounts.rename(user['id'], value),
            lambda: service.accounts.rename(user['id'], value, managed_bot_admin=True),
            lambda: service.accounts.link(user['id'], claims, value),
        ):
            try:
                await operation()
                raise AssertionError('reserved name claimed: '+value)
            except PlatformError as exc:
                assert exc.code == 'USERNAME_RESERVED' and exc.status == 409
            checks += 1
        assert await service.get_user(user['id']) == original, 'rejection must not change account or spend rename credit'
        assert await service.find_user_by_username('Plazr') is None
    for value in ('Existing_Player', 'Plazr_fan', 'plazr2'):
        assert normalize_username(value) == value
    assert len(service.mem_users) == 1 and len(service.mem_firebase) == 1
    print(f'RESERVED_USERNAME_PASS: {checks} rejected account claims; case/whitespace variants, unchanged account, no rename charges')

if __name__ == '__main__':
    asyncio.run(main())
