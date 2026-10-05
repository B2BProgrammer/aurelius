# Atrium mobile: setup and testing, step by step

Run every command in **PowerShell**. Project root: `C:\work\1_Projects\aurelius`.

---

## 1. Install Flutter (once, about 15 minutes)

Flutter is a tool you install once on your computer, like Maven or Go. The app's own libraries still stay with the project.

```powershell
# 1a. Get Flutter (stable channel) into C:\dev\flutter
mkdir C:\dev -Force
git clone https://github.com/flutter/flutter.git -b stable C:\dev\flutter

# 1b. Add it to YOUR user PATH (permanent, no admin needed)
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";C:\dev\flutter\bin", "User")
```

**Close PowerShell and open a new one**, so it sees the new PATH. Then:

```powershell
flutter --version     # first run downloads the Dart SDK: takes a few minutes
flutter doctor
```

`flutter doctor` lists what's ready. For this project you need:

| Line in `flutter doctor` | Needed for | If it shows ✗ |
|---|---|---|
| Flutter | everything | re-check the PATH step |
| Chrome | running in Chrome (quickest) | install Google Chrome |
| Android toolchain | the Android emulator | step 6 |
| Visual Studio | Windows desktop apps | **not needed**, ignore |
| Xcode | iOS | only exists on a Mac, ignore |

In VS Code, also install the **Flutter** extension (it brings Dart). It gives you hot reload and a device picker.

---

## 2. Create the project shell, then add our code

`flutter create` generates the standard platform folders (`android/`, `ios/`, `web/`). Our zip then supplies the app itself.

```powershell
cd C:\work\1_Projects\aurelius\frontend
flutter create --org com.aurelius --project-name atrium_mobile --platforms android,ios,web mobile
```

Now put our files on top. They replace `pubspec.yaml`, `lib\`, `test\` and `analysis_options.yaml`:

```powershell
Expand-Archive -Path "$HOME\Downloads\atrium_mobile.zip" -DestinationPath C:\work\1_Projects\aurelius\frontend -Force
```

(Adjust the path if your download is elsewhere. The zip contains a `mobile\` folder, so it lands in the right place.)

Apply the Android debug network setting, which lets the emulator call `http://10.0.2.2:8000`:

```powershell
cd C:\work\1_Projects\aurelius\frontend\mobile
Copy-Item -Recurse -Force android_overrides\app\src\debug\* android\app\src\debug\
```

---

## 3. Get the libraries, check the code, run the tests

```powershell
cd C:\work\1_Projects\aurelius\frontend\mobile
flutter pub get
flutter analyze
flutter test
```

EXPECT:
- `flutter analyze`: no errors. A few "info" hints are fine.
- `flutter test`: `All tests passed!` (16 unit tests and 4 widget tests).

These need no servers. They use a fake Conductor that replays real recorded agent answers.

> I couldn't compile Flutter in my own workspace, so this is the first real compile. If `analyze` or `test` shows an error, paste it to me and I'll fix it.

---

## 4. Start the backend

Same as for the web app: either the full swarm (your start-up notes, steps 1 to 11), or just the Conductor (quick mode, `MOCK_AGENTS=true`).

---

## 5. Run it in Chrome (quickest, no emulator)

Chrome runs the app from `http://localhost:5174`, which is a different origin from the Conductor's, so the Conductor must allow it. In `aurelius\.env` add:

```dotenv
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174
```

Restart the Conductor, then:

```powershell
cd C:\work\1_Projects\aurelius\frontend\mobile
flutter run -d chrome --web-port 5174
```

Sign in with `advisor` and your `DEV_LOGIN_PASSWORD`. In the terminal, press `r` for **hot reload** after you change code, and `q` to quit.

In Chrome, the News tab says live news works only in the phone app. That's expected: browsers buffer the stream in Flutter's http client. Everything else works.

---

## 6. Run it on an Android emulator (the real phone experience)

1. Install **Android Studio** from developer.android.com/studio. Open it once and let it install the Android SDK.
2. Run `flutter doctor --android-licenses` and accept them all with `y`.
3. In Android Studio: **More Actions → Virtual Device Manager → Create device**. Choose a Pixel and the recommended system image, then **Finish** and press ▶ to start it.
4. Then:
   ```powershell
   cd C:\work\1_Projects\aurelius\frontend\mobile
   flutter devices          # the emulator should be listed
   flutter run              # picks the emulator
   ```

The app calls `http://10.0.2.2:8000`, which is the emulator's name for your computer, so the Conductor works as it is (no `.env` change).

---

## 7. What to try

| # | Do this | Expect |
|---|---|---|
| 1 | Sign in with a wrong password | "That username and password don't match." |
| 2 | Sign in correctly | Households: Patel, Chen family, Garcia |
| 3 | Tap **Patel** | $2.35M, the agent names with their timings, and Needs you (Paperwork, Overdue, Market, Rebalance, Concentration) |
| 4 | Scroll to Retirement and tap **64** | Odds for up to 3 ages (they only change with the real Actuary) |
| 5 | **Write to them**, then **Draft email** | Approve is greyed out until you replace `[Add your key points]` |
| 6 | Write "This fund offers guaranteed returns" and approve | Refused; the body comes back with `[removed: non-compliant claim]` |
| 7 | Write a clean body and approve | "Approved and logged to the CRM as note N-…" |
| 8 | Chat icon on a household, then ask the policy question | Answer from the Librarian, saying which agents answered |
| 9 | **News** tab (emulator, full swarm), then push an event to Pulse (see the web TESTING.md, step 6) | It appears within a second and the tab shows a badge |
| 10 | Pull down on a list | It refreshes |
| 11 | Stop the Conductor, then pull down to refresh | "The Conductor isn't reachable…". News shows "Offline, retrying" and reconnects when it's back. |

---

## 8. A real phone on your Wi-Fi (optional)

1. In `aurelius\.env`, set `CONDUCTOR_HOST=0.0.0.0` and restart the Conductor. This lets other devices on your network reach it. Switch it back to `127.0.0.1` when you're done.
2. Find your PC's IP with `ipconfig` (IPv4 Address, for example `192.168.1.20`). Allow Python through Windows Firewall when Windows asks.
3. Add that IP to `android\app\src\debug\res\xml\network_security_config.xml`.
4. Enable Developer options and USB debugging on the phone, plug it in, then:
   ```powershell
   flutter run --dart-define=CONDUCTOR_URL=http://192.168.1.20:8000
   ```

---

## Troubleshooting

| You see | Fix |
|---|---|
| `flutter` not recognized | Open a NEW PowerShell after step 1b. Check `C:\dev\flutter\bin` is on your user PATH. |
| "The Conductor isn't reachable" in Chrome | `ALLOWED_ORIGINS` is missing `http://localhost:5174`, or you didn't restart the Conductor |
| "The Conductor isn't reachable" on the emulator | The debug network file wasn't copied (step 2), or the Conductor isn't running |
| `Cleartext HTTP traffic not permitted` | Same as above: copy `android_overrides` and run `flutter run` again (a full restart, not a hot reload) |
| "Sign-in is turned off" | Add `DEV_LOGIN_PASSWORD` to `aurelius\.env` and restart the Conductor |
| Gradle download is slow the first time | Normal. The first Android build downloads a lot, later builds are fast. |
