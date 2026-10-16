import 'package:flutter/material.dart';

import 'sticker_art.dart';

/// Public profile data only: owned cosmetics and server-recorded game results.
class ProfileDetails extends StatefulWidget {
  const ProfileDetails({super.key, required this.user});
  final Map<String, dynamic> user;
  @override
  State<ProfileDetails> createState() => _ProfileDetailsState();
}

class _ProfileDetailsState extends State<ProfileDetails> {
  bool expanded = false, full = false;
  String filter = 'all';
  static const names = {
    'pool': 'البلياردو',
    'carrom': 'الكيرم',
    'tablesoccer': 'كرة الطاولة',
    'crazy8': 'أونو',
  };
  int number(dynamic value) =>
      (value is num ? value.toInt() : int.tryParse('$value') ?? 0)
          .clamp(0, 1 << 40)
          .toInt();
  String? asset(dynamic value) {
    final path = '$value';
    if (!RegExp(
          r'^/(images|games|platform/assets|room-sprites)/[A-Za-z0-9_./-]+$',
        ).hasMatch(path) ||
        path.contains('..'))
      return null;
    return 'assets/runtime$path';
  }

  Widget picture(dynamic value, {double height = 65}) {
    if (StickerArtwork.cell('$value') != null)
      return StickerArtwork(asset: '$value', size: height);
    final path = asset(value);
    return path == null
        ? Icon(Icons.auto_awesome, size: height / 2)
        : Image.asset(path, height: height, fit: BoxFit.contain);
  }

  void showItem(Map item) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${item['name']}', textAlign: TextAlign.right),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            picture(item['asset'], height: 140),
            const SizedBox(height: 14),
            Text('العدد: ${number(item['quantity'] ?? 1)}'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إغلاق'),
          ),
        ],
      ),
    );
  }

  Widget heading(String label, Widget trailing) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
        ),
        trailing,
      ],
    ),
  );
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final items = (widget.user['showcaseItems'] as List? ?? [])
        .whereType<Map>()
        .toList();
    final selected = expanded && filter != 'all'
        ? items
              .where(
                (x) => (x['gameId'] == '' ? 'profile' : x['gameId']) == filter,
              )
              .toList()
        : items;
    final visible = expanded ? selected : selected.take(3).toList();
    final total = items.fold<int>(
      0,
      (n, item) => n + number(item['quantity'] ?? 1),
    );
    final stats = (widget.user['gameStatistics'] as List? ?? [])
        .whereType<Map>()
        .where((s) => number(s['played']) > 0 && names.containsKey(s['gameId']))
        .toList();
    final collected = number(
      widget.user['collectionOwnedCount'] ??
          items.map((x) => x['id']).toSet().length,
    );
    final catalogTotal = number(widget.user['collectionTotalCount'])
        .clamp(collected, 1 << 40);
    final completion = catalogTotal > 0 ? collected / catalogTotal : 0.0;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          heading(
            widget.user['relation'] == 'self' ? 'مقتنياتي' : 'مقتنيات اللاعب',
            Text(
              '($collected / $catalogTotal)',
              textDirection: TextDirection.ltr,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 12),
            ),
          ),
          Semantics(
            label: 'تقدم جمع المقتنيات',
            value: '$collected من $catalogTotal',
            child: LinearProgressIndicator(
              value: completion,
              minHeight: 8,
              borderRadius: BorderRadius.circular(99),
              color: const Color(0xff79b845),
            ),
          ),
          const SizedBox(height: 12),
          if (expanded)
            DropdownButton<String>(
              value: filter,
              isExpanded: true,
              onChanged: (value) => setState(() => filter = value ?? 'all'),
              items: [
                const DropdownMenuItem(
                  value: 'all',
                  child: Text('كل المقتنيات'),
                ),
                const DropdownMenuItem(
                  value: 'profile',
                  child: Text('زينة الملف'),
                ),
                for (final game in names.entries)
                  DropdownMenuItem(value: game.key, child: Text(game.value)),
              ],
            ),
          if (visible.isEmpty)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                items.isEmpty
                    ? 'لا توجد مقتنيات مملوكة للعرض بعد.'
                    : 'لا توجد مقتنيات في هذه الفئة.',
                style: TextStyle(color: colors.onSurfaceVariant),
              ),
            ),
          if (visible.isNotEmpty)
            GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: .78,
              children: [
                for (final item in visible)
                  Card(
                    margin: EdgeInsets.zero,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => showItem(item),
                      child: Padding(
                        padding: const EdgeInsets.all(7),
                        child: Column(
                          children: [
                            Expanded(child: picture(item['asset'])),
                            const SizedBox(height: 5),
                            Text(
                              '${item['name']}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              textAlign: TextAlign.center,
                              style: const TextStyle(fontSize: 11),
                            ),
                            Text(
                              '×${number(item['quantity'] ?? 1)}',
                              style: TextStyle(
                                color: colors.primary,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          if (items.isNotEmpty)
            OutlinedButton(
              onPressed: () => setState(() => expanded = !expanded),
              child: Text(
                expanded ? 'عرض العيّنة' : 'تصفّح كل المقتنيات ($total)',
              ),
            ),
          if (stats.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(),
            heading(
              'رحلتي في الألعاب',
              TextButton(
                onPressed: () => setState(() => full = !full),
                child: Text(full ? 'عرض مختصر' : 'عرض التفاصيل'),
              ),
            ),
            for (final game in names.entries) ...[
              for (final stat in stats.where((s) => s['gameId'] == game.key))
                rankRow(game.key, game.value, stat, colors),
            ],
            if (full)
              Text(
                'يُحتسب التقدم من نتائج المباريات المسجلة لكل لعبة. نجوم الرتب مستقلة عن زينة النجوم المشتراة.${number(widget.user['legacyWins']) > 0 ? ' يوجد ${number(widget.user['legacyWins'])} فوز سابق دون تفاصيل حسب اللعبة.' : ''}',
                style: TextStyle(fontSize: 11, color: colors.onSurfaceVariant),
              ),
          ],
        ],
      ),
    );
  }

  Widget rankRow(String id, String name, Map stat, ColorScheme colors) =>
      GameRankCard(id: id, name: name, stat: stat, full: full);
}

/// The same server-recorded rank presentation in profile and game discovery.
class GameRankCard extends StatelessWidget {
  const GameRankCard({
    super.key,
    required this.id,
    required this.name,
    required this.stat,
    this.full = false,
  });
  final String id, name;
  final Map stat;
  final bool full;
  static const marks = {
    'pool': 'pool',
    'carrom': 'carrom',
    'tablesoccer': 'football',
    'crazy8': 'cards',
  };
  int number(dynamic value) =>
      (value is num ? value.toInt() : int.tryParse('$value') ?? 0)
          .clamp(0, 1 << 40)
          .toInt();
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final level = number(stat['level']).clamp(1, 100);
    final progress = ((stat['progress'] as num?)?.toDouble() ?? 0)
        .clamp(0.0, 1.0)
        .toDouble();
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            SizedBox(
              width: 68,
              height: 82,
              child: Stack(
                children: [
                  Image.asset(
                    'assets/runtime/room-sprites/${marks[id]}.png',
                    width: 60,
                    height: 60,
                    fit: BoxFit.contain,
                  ),
                  Positioned(
                    left: 0,
                    bottom: 0,
                    child: Image.asset(
                      'assets/runtime/platform/assets/ranks/level-${level.toString().padLeft(3, '0')}.png',
                      width: 49,
                      height: 49,
                      semanticLabel: 'المستوى $level',
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      Text(
                        'المستوى $level',
                        style: const TextStyle(fontSize: 11),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${number(stat['wins'])} فوز',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                      Text(
                        '${stat['rankName'] ?? ''}',
                        style: TextStyle(
                          color: colors.onSurfaceVariant,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Semantics(
                    label: 'تقدم مستوى $name',
                    value: '${(progress * 100).round()} بالمئة',
                    child: LinearProgressIndicator(
                      value: progress,
                      minHeight: 7,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  if (full) ...[
                    const SizedBox(height: 9),
                    Text(
                      level == 100
                          ? 'وصلت إلى قمة المستويات'
                          : '${number(stat['winsToNextLevel'])} فوز للمستوى ${level + 1}',
                      style: const TextStyle(fontSize: 11),
                    ),
                    const SizedBox(height: 5),
                    Wrap(
                      spacing: 10,
                      children:
                          [
                                Text('لعب ${number(stat['played'])}'),
                                Text('خسر ${number(stat['losses'])}'),
                                Text('تعادل ${number(stat['draws'])}'),
                              ]
                              .map(
                                (x) => DefaultTextStyle(
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: colors.onSurfaceVariant,
                                  ),
                                  child: x,
                                ),
                              )
                              .toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
