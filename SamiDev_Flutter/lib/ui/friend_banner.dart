import 'dart:async';

import 'package:flutter/material.dart';

/// iOS-style temporary banner; swipe up works with touch and mouse dragging.
class FriendBanner extends StatefulWidget {
  const FriendBanner({
    super.key,
    required this.username,
    required this.text,
    required this.onOpen,
    required this.onDismiss,
  });
  final String username, text;
  final VoidCallback onOpen, onDismiss;
  @override
  State<FriendBanner> createState() => _FriendBannerState();
}

class _FriendBannerState extends State<FriendBanner> {
  Timer? timer;
  @override
  void initState() {
    super.initState();
    timer = Timer(const Duration(milliseconds: 5500), widget.onDismiss);
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Align(
      alignment: Alignment.topCenter,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Dismissible(
            key: const ValueKey('friend-notification'),
            direction: DismissDirection.up,
            onDismissed: (_) => widget.onDismiss(),
            child: Material(
              elevation: 14,
              shadowColor: Colors.black38,
              borderRadius: BorderRadius.circular(24),
              color: Theme.of(context).colorScheme.surfaceContainerHigh,
              child: InkWell(
                borderRadius: BorderRadius.circular(24),
                onTap: widget.onOpen,
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      const CircleAvatar(
                        child: Icon(Icons.chat_bubble_outline),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.username,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              widget.text,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'تجاهل الإشعار',
                        onPressed: widget.onDismiss,
                        icon: const Icon(Icons.close, size: 18),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
