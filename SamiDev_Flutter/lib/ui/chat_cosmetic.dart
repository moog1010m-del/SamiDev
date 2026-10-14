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
      constraints: const BoxConstraints(minHeight: 42),
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 14),
            child: ColoredBox(
              color: const Color(0xff12242d),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                child: DefaultTextStyle.merge(
                  style: const TextStyle(color: Color(0xffedf3f5)),
                  child: child,
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: IgnorePointer(
              child: Image.asset(
                'assets/runtime/platform/assets/cosmetics/$id.webp',
                centerSlice: Rect.fromLTRB(
                  85,
                  55,
                  size.width - 85,
                  size.height - 50,
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
