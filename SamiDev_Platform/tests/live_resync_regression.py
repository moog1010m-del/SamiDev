#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('SAMIDEV_STORE', 'memory')

from app import SamiDevRealtime  # noqa: E402


class FakeStore:
    distributed = False

    def __init__(self):
        self.snapshot = {'marker': 'stale', 'turn': [0]}
        self.snapshot_revision = 2
        self.sequence = [1, 0]
        self.synced = None

    async def resync(self, rid):
        return {
            'snapshot': dict(self.snapshot),
            'snapshotMoveCount': 3,
            'snapshotRevision': self.snapshot_revision,
            'history': [],
            'moveCount': 3,
            'sequence': list(self.sequence),
        }

    async def get_authority(self, rid):
        return {'shard': 'http://fake-gamehost', 'epoch': 4, 'revision': 2}

    async def get_room_state(self, rid):
        return {'moveCount': 3}

    async def sync_sequence(self, rid, sequence):
        self.sequence = list(sequence)
        self.synced = list(sequence)

    async def set_snapshot(self, rid, seat, state, move_count, revision=0):
        self.snapshot = dict(state)
        self.snapshot_revision = int(revision)


class FakeGameHost:
    def has_shard(self, shard):
        return shard == 'http://fake-gamehost'

    async def state(self, rid, *, shard=None):
        return {
            'ok': True,
            'roomId': rid,
            'authorityEpoch': 4,
            'authorityRevision': 9,
            'turn': [1],
            'sequence': [2, 0],
            'gameOver': False,
            'snapshot': {'marker': 'live', 'turn': [1], 'sequence': [2, 0]},
            'snapshotDeferred': False,
        }


async def main():
    service = object.__new__(SamiDevRealtime)
    service.store = FakeStore()
    service.gamehost = FakeGameHost()

    payload = await service._authoritative_resync('ABCDEF')
    report = {
        'ok': payload['snapshot']['marker'] == 'live'
              and payload['snapshotRevision'] == 9
              and payload['turn'] == [1]
              and payload['sequence'] == [2, 0]
              and service.store.synced == [2, 0],
        'staleStoreReplaced': payload['snapshot']['marker'] == 'live',
        'snapshotRevision': payload['snapshotRevision'],
        'turn': payload['turn'],
        'sequence': payload['sequence'],
        'authorityEpoch': payload['authorityEpoch'],
        'revision': payload['revision'],
    }
    print(json.dumps(report, indent=2))
    if not report['ok']:
        raise SystemExit(2)


if __name__ == '__main__':
    asyncio.run(main())
