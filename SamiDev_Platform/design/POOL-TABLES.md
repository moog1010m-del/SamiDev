# Current pool tables

Only these three table designs are retained for use:

| Design | Table asset | Preview |
| --- | --- | --- |
| Plazr graphite V9 (default) | `../game/images/themes/pool-midnight.webp` | `../game/images/themes/pool-midnight-preview.webp` |
| Emerald | `../game/images/themes/pool-emerald.webp` | `../game/images/themes/pool-emerald-preview.webp` |
| Large-table match option | `../game/images/pool-large/table.webp` | `../game/images/pool-large/preview.webp` |

`../game/games/pool/images/imported/themes/th_basic_table.webp` is the same
Plazr V9 sprite under the filename required by the engine, not a fourth design.
Flutter runtime copies and generated release copies likewise are not extra designs.
The large-table option stays independent of the two store themes.

On 2026-10-23, historical table experiments and old backup artwork were moved
outside the repository to `C:/Users/Dev/Documents/Plazr-Design-Archive/2026-10-23`.
Its `moved-designs.json` records original and archive paths. Engine code, shared
UI/ball atlases, active table artwork and physics were not changed by cleanup.
