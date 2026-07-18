import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:attendance_kiosk/main.dart';

void main() {
  testWidgets('renders kiosk setup screen', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const AttendanceKioskApp(cameras: [], enableFaceService: false));

    expect(find.text('Kiosk Settings'), findsOneWidget);
    expect(find.text('Start Kiosk'), findsOneWidget);
  });
}
