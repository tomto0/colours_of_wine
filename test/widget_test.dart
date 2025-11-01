// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:colours_of_wine/main.dart';

void main() {
  testWidgets('App lädt und zeigt Suchfeld und Analysieren-Button', (WidgetTester tester) async {
    // App aufbauen
    await tester.pumpWidget(const ColoursOfWineApp());
    await tester.pumpAndSettle();

    // Erwartete Widgets prüfen
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('Analysieren'), findsOneWidget);
    expect(find.byIcon(Icons.analytics), findsOneWidget);
  });
}
