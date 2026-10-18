import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/reputation_flame.dart';
void main(){
  test('earned reputation uses the same seven thresholds as web',(){
    for(final row in [[0,0],[1,1],[99,1],[100,2],[499,2],[500,3],[999,3],[1000,4],[9999,4],[10000,5],[49999,5],[50000,6]]){
      expect(ReputationFlame.tier(row[0]),row[1]);
    }
  });
  testWidgets('highest tier respects reduced motion and score updates',(tester)async{
    await tester.pumpWidget(const MaterialApp(home:MediaQuery(data:MediaQueryData(disableAnimations:true),child:ReputationFlame(score:50004))));
    await tester.pumpAndSettle();expect(tester.takeException(),isNull);
    await tester.pumpWidget(const MaterialApp(home:ReputationFlame(score:50004)));
    await tester.pump(const Duration(milliseconds:500));expect(tester.hasRunningAnimations,isTrue);
    await tester.pumpWidget(const MaterialApp(home:ReputationFlame(score:3)));
    await tester.pumpAndSettle();expect(tester.hasRunningAnimations,isFalse);
    expect(tester.takeException(),isNull);
  });
}
