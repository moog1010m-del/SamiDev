import 'dart:convert';

import 'package:flutter/material.dart';

Color settingsBackground(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark
    ? const Color(0xff11161d)
    : const Color(0xfff2f5f8);
Color settingsSurface(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark
    ? const Color(0xff1b222c)
    : Colors.white;
Color settingsMuted(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark
    ? const Color(0xff96a3b4)
    : const Color(0xff8793a3);

class SettingsFrame extends StatelessWidget {
  const SettingsFrame({
    super.key,
    required this.title,
    required this.child,
    this.onBack,
    this.actions,
  });
  final String title;
  final Widget child;
  final VoidCallback? onBack;
  final List<Widget>? actions;
  @override
  Widget build(BuildContext context) => Directionality(
    textDirection: TextDirection.rtl,
    child: Scaffold(
      backgroundColor: settingsBackground(context),
      appBar: AppBar(
        backgroundColor: settingsSurface(context),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        toolbarHeight: 58,
        title: Text(
          title,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        leading: IconButton(
          tooltip: 'رجوع',
          onPressed: onBack ?? () => Navigator.maybePop(context),
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
        ),
        actions: actions,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Divider(
            height: 1,
            color: settingsMuted(context).withValues(alpha: .14),
          ),
        ),
      ),
      body: SafeArea(top: false, child: child),
    ),
  );
}

Widget settingsGroup(BuildContext context, List<Widget> children) => ClipRRect(
  borderRadius: BorderRadius.circular(12),
  child: Material(
    color: settingsSurface(context),
    child: Column(
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0)
            Divider(
              height: 1,
              indent: 16,
              endIndent: 16,
              color: settingsMuted(context).withValues(alpha: .13),
            ),
          children[i],
        ],
      ],
    ),
  ),
);

Widget settingsEntry(
  BuildContext context, {
  required IconData icon,
  required String title,
  required VoidCallback? onTap,
  String? subtitle,
  Color? color,
  Widget? trailing,
}) => ListTile(
  minTileHeight: 60,
  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
  horizontalTitleGap: 12,
  leading: Icon(icon, size: 23, color: color ?? settingsMuted(context)),
  title: Text(
    title,
    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: color),
  ),
  subtitle: subtitle == null
      ? null
      : Text(
          subtitle,
          style: TextStyle(fontSize: 12, color: settingsMuted(context)),
        ),
  trailing:
      trailing ??
      Icon(
        Icons.chevron_right,
        size: 22,
        color: settingsMuted(context).withValues(alpha: .65),
      ),
  onTap: onTap,
);

class SettingsAvatar extends StatelessWidget {
  const SettingsAvatar({super.key, required this.user, this.size = 66});
  final Map<String, dynamic> user;
  final double size;
  @override
  Widget build(BuildContext context) {
    Widget face = Icon(
      Icons.person_rounded,
      size: size * .6,
      color: const Color(0xff5283b8),
    );
    try {
      final data = user['avatarData']?.toString() ?? '';
      if (data.startsWith('data:image/') && data.contains(',')) {
        face = Image.memory(
          base64Decode(data.split(',').last),
          fit: BoxFit.cover,
          width: size,
          height: size,
          errorBuilder: (_, error, stack) => const Icon(Icons.person_rounded),
        );
      }
    } catch (_) {}
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xffe7f0ff),
        border: Border.all(color: settingsBackground(context), width: 4),
      ),
      clipBehavior: Clip.antiAlias,
      child: face,
    );
  }
}

class SettingsDevicesIllustration extends StatelessWidget {
  const SettingsDevicesIllustration({super.key, this.user = const {}});
  final Map<String, dynamic> user;
  @override
  Widget build(BuildContext context) {
    Widget screen(double width, double height, {Widget? child}) => Container(
      width: width,
      height: height,
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xffe7ecf3),
        border: Border.all(color: const Color(0xff8796aa), width: 2.5),
        borderRadius: BorderRadius.circular(9),
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: settingsSurface(context),
          borderRadius: BorderRadius.circular(4),
        ),
        child: child,
      ),
    );
    return SizedBox(
      width: 238,
      height: 148,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Positioned(
            bottom: 10,
            child: Container(
              width: 72,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xff8796aa),
                borderRadius: BorderRadius.circular(5),
              ),
            ),
          ),
          Positioned(
            bottom: 14,
            child: Container(
              width: 36,
              height: 35,
              color: const Color(0xffd3dbe6),
            ),
          ),
          Positioned(
            top: 7,
            child: screen(
              150,
              105,
              child: Center(child: SettingsAvatar(user: user, size: 58)),
            ),
          ),
          Positioned(left: 10, bottom: 11, child: screen(39, 65)),
          Positioned(right: 7, bottom: 11, child: screen(57, 79)),
          Positioned(
            right: 29,
            top: 3,
            child: Container(
              width: 28,
              height: 28,
              decoration: const BoxDecoration(
                color: Color(0xff2584e8),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check, size: 18, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}

IconData settingsDeviceIcon(Map<String, dynamic> device) {
  final name = (device['device'] ?? '').toString().toLowerCase();
  return name.contains('android')
      ? Icons.android
      : name.contains('iphone') || name.contains('ipad') || name.contains('mac')
      ? Icons.apple
      : Icons.computer_outlined;
}

Color settingsDeviceColor(Map<String, dynamic> device) =>
    settingsDeviceIcon(device) == Icons.android
    ? const Color(0xff87c743)
    : settingsDeviceIcon(device) == Icons.apple
    ? const Color(0xff9c67e7)
    : const Color(0xff4f9bc9);
