# SamiDev Authoritative Game Architecture

Crazy 8 is registered alongside Carrom and Table Soccer. Each game uses its own
`GameRuntimeFactory`. Crazy 8 checkpoints contain private server state plus native
per-seat serialized views; the gateway only sends the authenticated seat view
(or spectator view -1) to browsers. Turn clocks wait for clients to finish loading.
See `CRAZY8_INTEGRATION_AR.md` for the integration and validation limits.

## Data plane

```text
Web Browser
           |
           | WSS
           v
     Nginx Load Balancer
       /      |      \
 Gateway-1 Gateway-2 Gateway-3
       \      |      /
              |
        Redis room state
              |
   authoritative room routing
              |
      Rendezvous hashing
      /        |        \
 GameHost-1 GameHost-2 GameHost-3
      |        |        |
      +-- exact main.js GameLogic --+
          server=true, localSeat=undefined
```

## Authority boundary

Gateways do not decide Carrom rules. For each incoming game packet:

1. Gateway identifies the assigned room/seat and validates the active connection epoch.
2. The packet is sent to the room's deterministic GameHost shard.
3. The shard executes `GameLogic.move(seat, packet)` using the exact bundled `main.js`.
4. Rejected packets are not stored and are not broadcast.
5. Accepted packets are appended to Redis history/sequence as defense-in-depth.
6. `GameLogic.serialize()` becomes the official reconnect/resync snapshot.
7. Client-provided snapshots are ignored.

`__info` / WorldState packets also pass through the headless GameLogic, so the existing ServerTrust validation path remains in use.

## GameHost memory model

`main.js` is compiled and executed once per GameHost process. The registered GameLogic constructor is reused to create an isolated GameLogic instance per room. This avoids loading a whole VM/bundle for every match while retaining separate mutable state per room.

Clean local measurements in the build environment: 500 authoritative 1v1 rooms used about 227 MB RSS; 250 authoritative 2v2 rooms used about 154 MB RSS. These are start/move load tests, not full-length production-match capacity guarantees.

## Sharding

Gateways accept `SAMIDEV_GAMEHOST_URLS`, a comma-separated set of GameHost addresses. Rooms are assigned using rendezvous hashing. Adding/removing a shard remaps only part of the keyspace. If a room lands on a GameHost that does not currently have it loaded, the Gateway recreates the GameLogic and restores the last authoritative server snapshot from Redis before retrying the move.

## Timers

Headless GameLogic's `onSetAlarm` schedules alarms inside the owning GameHost. When an alarm fires, the same `logic.alarm()` path runs and a fresh authoritative snapshot is emitted to Gateways and persisted. The client is not the source of truth for timer state.

## Current security boundary

Already enforced in this build:

- GameLogic decides legal/illegal moves.
- Wrong-turn moves are rejected before broadcast.
- Duplicate sequence packets are rejected by GameLogic; Redis sequence remains a second check.
- Client snapshots cannot overwrite server state.
- Official reconnect state is `GameLogic.serialize()` from the GameHost.
- GameHost pins the expected `main.js` SHA-256 and fails startup if it changes.
- Container processes run as non-root.
- Production Compose uses an Origin allowlist for the local deployment example.

Still required before a public Internet launch:

- Optional first-party account/authentication layer if persistent user accounts are required.
- TLS/WSS and production domains.
- Per-user/IP connection and room-creation limits.
- Durable account/economy database.
- Full replay corpus for Queen/Fouls/AFK/resign/reconnect/game-over cases.
- Multi-host Redis/Docker benchmark on production hardware.
