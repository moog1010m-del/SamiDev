import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/sticker_art.dart';

void main() {
  testWidgets('historical badge addresses use independent inanimate assets', (tester) async {
    const old='/platform/assets/stickers/samidev-stickers.png#cell-3';
    expect(StickerArtwork.resolve(old),'/platform/assets/stickers/badge_fox-v3.png');
    expect(StickerArtwork.resolve('/platform/assets/stickers/samidev-stickers.png#cell-8'),'');
    expect(StickerArtwork.resolve('/platform/assets/cosmetics/badge_shard.webp'),'/platform/assets/stickers/badge_shard-v3.png');
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: StickerArtwork(asset: old))));
    await tester.pumpAndSettle();
    final image=tester.widget<Image>(find.byType(Image));
    expect((image.image as AssetImage).assetName,'assets/runtime/platform/assets/stickers/badge_fox-v3.png');
    expect(tester.takeException(),isNull);
  });
}
