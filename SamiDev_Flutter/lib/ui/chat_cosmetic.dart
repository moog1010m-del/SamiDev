import 'package:flutter/material.dart';

/// Locally bundled, server-selected artwork; never load a URL from chat text.
class ChatCosmetic extends StatelessWidget {
  const ChatCosmetic({super.key, required this.id, required this.child});
  final String id;
  final Widget child;
  static const sizes = {
    'chat_turquoise': Size(384, 200),
    'chat_mist': Size(382, 205),
    'chat_ember': Size(394, 200),
  };
  @override
  Widget build(BuildContext context) {
    final size = sizes[id];
    if (size == null) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(18),
        ),
        child: child,
      );
    }
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 58, minWidth: 84),
      child: Stack(
        children: [
          Positioned.fill(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(7, 7, 7, 6),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: const {
                    'chat_mist': Color(0xff24212e),
                    'chat_turquoise': Color(0xff12312f),
                    'chat_ember': Color(0xff38201c),
                  }[id],
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(30, 22, 30, 20),
            child: DefaultTextStyle.merge(
              style: const TextStyle(color: Color(0xffedf3f5)),
              child: child,
            ),
          ),
          Positioned.fill(
            child: IgnorePointer(
              child: Image.asset(
                'assets/runtime/platform/assets/cosmetics/$id.webp',
                scale: 4,
                centerSlice: Rect.fromLTRB(
                  85 / 4,
                  55 / 4,
                  (size.width - 85) / 4,
                  (size.height - 50) / 4,
                ),
                fit: BoxFit.fill,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
