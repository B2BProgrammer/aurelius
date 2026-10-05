import 'package:flutter/material.dart';

/// The same palette as the Atrium web app: paper, ink, ledger green,
/// brass only for "needs you".
class AppColors {
  static const paper = Color(0xFFF6F7F5);
  static const sheet = Color(0xFFFFFFFF);
  static const ink = Color(0xFF1C2B30);
  static const ink2 = Color(0xFF4A5A5F);
  static const ink3 = Color(0xFF6F7D80);
  static const ledger = Color(0xFF2E5E4E);
  static const ledgerSoft = Color(0xFFE3ECE7);
  static const brass = Color(0xFFA8823A);
  static const blocker = Color(0xFFB3432E);
  static const attention = Color(0xFFB98316);
  static const rule = Color(0xFFD7DDD9);
}

/// Serif for names and big numbers. The phone's own serif font, so nothing is downloaded.
const serif = 'serif';
const serifFallback = ['Georgia', 'Noto Serif', 'Times New Roman'];

TextStyle serifStyle(double size, {FontWeight weight = FontWeight.w400, Color color = AppColors.ink, double height = 1.2}) =>
    TextStyle(fontFamily: serif, fontFamilyFallback: serifFallback, fontSize: size, fontWeight: weight, color: color, height: height);

ThemeData buildTheme() {
  const scheme = ColorScheme.light(
    primary: AppColors.ink,
    onPrimary: AppColors.paper,
    secondary: AppColors.ledger,
    onSecondary: Colors.white,
    surface: AppColors.paper,
    onSurface: AppColors.ink,
    error: AppColors.blocker,
    onError: Colors.white,
    outline: AppColors.rule,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme);
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.paper,
    dividerTheme: const DividerThemeData(color: AppColors.rule, thickness: 1, space: 1),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.paper,
      foregroundColor: AppColors.ink,
      elevation: 0,
      scrolledUnderElevation: 0.5,
      centerTitle: false,
    ),
    textTheme: base.textTheme.apply(bodyColor: AppColors.ink, displayColor: AppColors.ink),
    inputDecorationTheme: const InputDecorationTheme(
      filled: true,
      fillColor: AppColors.sheet,
      border: OutlineInputBorder(borderSide: BorderSide(color: AppColors.rule)),
      enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: AppColors.rule)),
      focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: AppColors.ledger, width: 2)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.ink,
        foregroundColor: AppColors.paper,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.ink,
        side: const BorderSide(color: AppColors.rule),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      backgroundColor: AppColors.paper,
      indicatorColor: AppColors.ledgerSoft,
    ),
  );
}
