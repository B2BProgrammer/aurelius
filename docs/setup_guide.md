# Setup Guide: Python, Node.js, React, Java, Go, Flutter (Windows)

For each technology:
1. **Download:** what to get from the internet
2. **Install and configure:** installation, PATH and environment variables, how to verify
3. **Scaffold:** commands that create a bare-minimum project
4. **Build tools:** the commands you use every day
5. **Baseline code:** the first code to write

Run every command in **PowerShell**. After changing PATH or environment variables, **close and reopen** PowerShell and VS Code.

---

## 0. Common tools (install first)

| Tool | Download | Why |
|---|---|---|
| Git | https://git-scm.com/download/win | Version control; also used to install Flutter |
| VS Code | https://code.visualstudio.com | Editor and debugger |

**VS Code extensions:** Python, Extension Pack for Java, Go, Flutter (includes Dart), Markdown Preview Mermaid Support.

**Allow PowerShell scripts** (one time):
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Check versions anytime:**
```powershell
git --version; python --version; node -v; java -version; mvn -v; go version; flutter --version
```

---

## 1. Python (FastAPI services)

### 1. Download
- Python 3.12 or newer: https://www.python.org/downloads/windows/ (Windows installer, 64-bit)

### 2. Install and configure
- In the installer, tick **"Add python.exe to PATH"**, then Install Now.
- This also installs the `py` launcher.
- Verify:
```powershell
  python --version
  py -3 --version
```
- **No environment variables needed.** Each project uses its own `.venv` folder.

### 3. Scaffold
```powershell
mkdir my-service; cd my-service
py -3 -m venv .venv                      # private Python for this project
.\.venv\Scripts\Activate.ps1             # prompt now shows (.venv)
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic-settings pytest httpx
pip freeze > requirements.txt            # record the exact versions
mkdir src, tests
```

### 4. Build tools
| Command | Does |
|---|---|
| `pip install -r requirements.txt` | Install dependencies (fresh machine) |
| `python src\main.py` | Run the service |
| `pytest -q` | Run the tests |
| `deactivate` | Leave the venv |

There's no compile step; Python runs the source directly.

### 5. Baseline code: `src/main.py`
```python
from fastapi import FastAPI
import uvicorn

app = FastAPI(title="My Service")

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```
Run it, then open http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs (Swagger).

---

## 2. Node.js + TypeScript (Express services)

### 1. Download
- Node.js LTS (22 or newer): https://nodejs.org (Windows Installer .msi). It includes `npm`.

### 2. Install and configure
- Run the .msi with the defaults; it adds Node to PATH.
- Verify:
```powershell
  node -v
  npm -v
```
- **No environment variables needed.** Libraries go into each project's `node_modules`.

### 3. Scaffold
```powershell
mkdir my-api; cd my-api
npm init -y
npm install express
npm install -D typescript tsx @types/node @types/express
npx tsc --init
mkdir src
```
Then edit `package.json` and add:
```json
"type": "module",
"scripts": {
  "dev": "tsx watch src/server.ts",
  "build": "tsc",
  "start": "node dist/server.js"
}
```

### 4. Build tools
| Command | Does |
|---|---|
| `npm install` (or `npm ci`) | Install dependencies (`ci` = exact versions from the lock file) |
| `npm run dev` | Run with auto-reload |
| `npm run build` | Compile TypeScript into `dist/` |
| `npm test` | Run tests (after adding vitest: `npm i -D vitest`, script `"test": "vitest run"`) |

### 5. Baseline code: `src/server.ts`
```typescript
import express from "express";

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.listen(8102, "127.0.0.1", () => {
  console.log("Listening on http://127.0.0.1:8102");
});
```

---

## 3. React (web app with Vite)

### 1. Download
- Same Node.js as above. Nothing extra.

### 2. Install and configure
- Nothing more to install; Vite is downloaded per project.

### 3. Scaffold
```powershell
npm create vite@latest web -- --template react-ts
cd web
npm install
npm run dev          # http://localhost:5173
```

### 4. Build tools
| Command | Does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm i -D vitest @testing-library/react jsdom` | Add testing |

**Calling a backend without CORS problems:** add a proxy in `vite.config.ts`:
```typescript
server: { proxy: { "/v1": "http://127.0.0.1:8000" } }
```

### 5. Baseline code: `src/App.tsx`
```tsx
import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch("/v1/health")
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("backend not reachable"));
  }, []);

  return <h1>Backend status: {status}</h1>;
}
```

---

## 4. Java (Spring Boot services)

### 1. Download
- JDK 21 LTS (Temurin): https://adoptium.net (Windows .msi)
- Maven: https://maven.apache.org/download.cgi ("Binary zip archive")

### 2. Install and configure
- **JDK:** run the .msi. On "Custom Setup", enable **"Set JAVA_HOME variable"** and **"Add to PATH"**.
- **Maven:** extract the zip to `C:\dev\maven`, then add its `bin` folder to your user PATH:
```powershell
  [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";C:\dev\maven\bin", "User")
```
- Verify (in a new PowerShell):
```powershell
  java -version
  mvn -v
  echo $env:JAVA_HOME
```
- **Optional:** to keep libraries inside the project, create `.mvn\maven.config` in the project containing:
```
  -Dmaven.repo.local=.m2/repository
```

### 3. Scaffold
Use Spring Initializr, either at https://start.spring.io (choose Maven, Java 21, add "Spring Web") or from PowerShell:
```powershell
curl.exe https://start.spring.io/starter.zip -d type=maven-project -d javaVersion=21 `
  -d dependencies=web -d groupId=com.example -d artifactId=demo -o demo.zip
Expand-Archive demo.zip demo
cd demo
```

### 4. Build tools
| Command | Does |
|---|---|
| `mvn spring-boot:run` | Compile and run |
| `mvn test` | Run the tests |
| `mvn package` | Build `target\demo-*.jar` |
| `java -jar target\demo-0.0.1-SNAPSHOT.jar` | Run the built jar |
| `mvn clean` | Delete build output |

### 5. Baseline code: `src/main/java/com/example/demo/HealthController.java`
```java
package com.example.demo;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {
    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }
}
```
Set the port in `src/main/resources/application.properties`:
```
server.port=8201
```

---

## 5. Go (services)

### 1. Download
- Go: https://go.dev/dl (Windows .msi)

### 2. Install and configure
- Run the .msi; it adds Go to PATH.
- `GOPATH` defaults to `%USERPROFILE%\go`. Nothing to set.
- Verify:
```powershell
  go version
```
- **For debugging in VS Code** (one time):
```powershell
  go install github.com/go-delve/delve/cmd/dlv@latest
```

### 3. Scaffold
```powershell
mkdir my-go-service; cd my-go-service
go mod init example.com/myservice      # creates go.mod
mkdir cmd\server
```

### 4. Build tools
| Command | Does |
|---|---|
| `go run ./cmd/server` | Compile and run |
| `go build -o server.exe ./cmd/server` | Build one standalone .exe |
| `go test ./...` | Run all tests |
| `go vet ./...` | Find suspicious code |
| `gofmt -w .` | Format the code |
| `go mod tidy` | Add or remove dependencies in go.mod |

### 5. Baseline code: `cmd/server/main.go`
```go
package main

import (
	"encoding/json"
	"log"
	"net/http"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	log.Println("Listening on http://127.0.0.1:8301")
	log.Fatal(http.ListenAndServe("127.0.0.1:8301", mux))
}
```

---

## 6. Flutter (mobile app)

### 1. Download
- Flutter SDK, via Git (stable channel)
- Google Chrome, to run the app on the web
- Android Studio (only for the Android emulator): https://developer.android.com/studio

### 2. Install and configure
```powershell
git clone https://github.com/flutter/flutter.git -b stable C:\dev\flutter
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";C:\dev\flutter\bin", "User")
```
Close and reopen PowerShell and VS Code, then:
```powershell
flutter --version              # the first run downloads the Dart SDK
flutter doctor                 # lists what's ready
```
For Android:
1. Open Android Studio once and let it install the SDK.
2. Run `flutter doctor --android-licenses` and answer `y` to each.
3. Create an emulator: More Actions → Virtual Device Manager.

### 3. Scaffold
```powershell
flutter create --org com.example my_app
cd my_app
```

### 4. Build tools
| Command | Does |
|---|---|
| `flutter pub get` | Install packages from `pubspec.yaml` |
| `flutter run -d chrome` | Run in Chrome (`r` = hot reload, `q` = quit) |
| `flutter run` | Run on a connected device or emulator |
| `flutter analyze` | Check the code |
| `flutter test` | Run the tests |
| `flutter build apk` / `flutter build web` | Release builds |

### 5. Baseline code: `lib/main.dart`
```dart
import 'package:flutter/material.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      home: Scaffold(
        body: Center(child: Text('Hello from Flutter')),
      ),
    );
  }
}
```

---

## Quick reference

| Tech | Install | Env vars | Scaffold | Run | Test | Build |
|---|---|---|---|---|---|---|
| Python | python.org installer | none (use .venv) | `py -3 -m venv .venv` | `python src\main.py` | `pytest` | none |
| Node/TS | nodejs.org .msi | none | `npm init -y` | `npm run dev` | `npm test` | `npm run build` |
| React | (Node) | none | `npm create vite@latest` | `npm run dev` | `npx vitest` | `npm run build` |
| Java | Temurin .msi + Maven zip | JAVA_HOME, PATH+maven\bin | start.spring.io | `mvn spring-boot:run` | `mvn test` | `mvn package` |
| Go | go.dev .msi | none (GOPATH default) | `go mod init` | `go run ./cmd/...` | `go test ./...` | `go build` |
| Flutter | git clone | PATH+flutter\bin | `flutter create` | `flutter run` | `flutter test` | `flutter build` |


---

## 7. Install everything with winget (optional shortcut)

Run in PowerShell. If an ID isn't found, run `winget search <name>`.
```powershell
winget install Git.Git
winget install Microsoft.VisualStudioCode
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install EclipseAdoptium.Temurin.21.JDK
winget install GoLang.Go
winget install Google.Chrome
winget install Google.AndroidStudio      # only for the Android emulator
```
Maven and Flutter are still installed manually (sections 4 and 6). Close and reopen PowerShell afterwards.

---

## 8. First test for each technology

Write one test that calls `/health` right after the baseline code, so you know the setup works end to end.

### Python: `tests/test_health.py`
Create `pytest.ini` in the project root so tests can import from `src`:
```ini
[pytest]
pythonpath = src
```
```python
from fastapi.testclient import TestClient
from main import app

def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```
Run it with `pytest -q`.

### Node.js: split the app from the listener so tests can use it
```powershell
npm i -D vitest supertest @types/supertest
```
`src/app.ts`
```typescript
import express from "express";
export const app = express();
app.use(express.json());
app.get("/health", (_req, res) => { res.json({ status: "ok" }); });
```
`src/server.ts`
```typescript
import { app } from "./app.js";
app.listen(8102, "127.0.0.1", () => console.log("Listening on 8102"));
```
`tests/health.test.ts`
```typescript
import { test, expect } from "vitest";
import request from "supertest";
import { app } from "../src/app.js";

test("health", async () => {
  const r = await request(app).get("/health");
  expect(r.status).toBe(200);
  expect(r.body).toEqual({ status: "ok" });
});
```
Add `"test": "vitest run"` to the scripts in package.json, then run `npm test`.

### React: `src/App.test.tsx`
```powershell
npm i -D vitest @testing-library/react jsdom
```
In `vite.config.ts`, add `/// <reference types="vitest/config" />` on line 1, and add this inside `defineConfig({ ... })`:
```typescript
test: { environment: "jsdom" },
```
```tsx
import { render, screen } from "@testing-library/react";
import { test, expect, vi } from "vitest";
import App from "./App";

test("shows backend status", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ json: async () => ({ status: "ok" }) }));
  render(<App />);
  expect(await screen.findByText("Backend status: ok")).toBeTruthy();
});
```
Add `"test": "vitest run"` to the scripts, then run `npm test`.

### Java: `src/test/java/com/example/demo/HealthControllerTest.java` (Spring Boot 3.x)
```java
package com.example.demo;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(HealthController.class)
class HealthControllerTest {
    @Autowired MockMvc mvc;

    @Test
    void health() throws Exception {
        mvc.perform(get("/health"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.status").value("ok"));
    }
}
```
Run it with `mvn test`.

### Go: move the routes into a function so tests can use them
In `cmd/server/main.go`:
```go
func routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	return mux
}
// in main(): log.Fatal(http.ListenAndServe("127.0.0.1:8301", routes()))
```
`cmd/server/main_test.go`
```go
package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHealth(t *testing.T) {
	rec := httptest.NewRecorder()
	routes().ServeHTTP(rec, httptest.NewRequest("GET", "/health", nil))
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `"ok"`) {
		t.Fatalf("got %d %s", rec.Code, rec.Body.String())
	}
}
```
Run it with `go test ./...`.

### Flutter: replace `test/widget_test.dart`
⚠️ `flutter create` makes a test for its counter demo. It fails as soon as you change `main.dart`. Replace it with:
```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:my_app/main.dart';

void main() {
  testWidgets('shows hello', (tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('Hello from Flutter'), findsOneWidget);
  });
}
```
Run it with `flutter test`.

---

## 9. .gitignore and .env habits

One `.gitignore` at the repo root covers every technology:
```gitignore
# Python
.venv/
__pycache__/
.pytest_cache/
# Node / React
node_modules/
dist/
# Java
target/
.m2/
# Go
*.exe
# Flutter
.dart_tool/
build/
# Secrets and editor files
.env
*.log
```
**Secrets rule:**
- Keep a `.env.example` with fake values and commit it.
- Keep the real `.env` local only. Never paste it into chat, email or screenshots.
- If a secret leaks, change it straight away.

---

## 10. Troubleshooting (Windows)

| Problem | Fix |
|---|---|
| `xyz is not recognized` after installing | Close and reopen PowerShell and VS Code. Or reload PATH in the current window: `$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")` |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port already in use | `Get-NetTCPConnection -LocalPort 8000 \| % { Stop-Process -Id $_.OwningProcess -Force }` |
| `python` opens the Microsoft Store | Settings → Apps → Advanced app settings → App execution aliases → turn off python.exe and python3.exe |
| VS Code Java: "JDK not supported" | Use JDK 21 LTS, or run with `mvn spring-boot:run` |
| `mvn` uses the wrong Java | Check `echo $env:JAVA_HOME` and `mvn -v`; they must point to the same JDK |
| CORS error in the browser | Add the page's origin (for example `http://localhost:5173`) to the backend's allowed origins, or use the Vite proxy |
| Android emulator can't reach localhost | Use `10.0.2.2` instead of `localhost` from inside the emulator |
| Weird errors from a OneDrive folder | Keep projects outside OneDrive (for example `C:\work`) |

---

## 11. Corporate network (proxy)

On a company laptop, installs often fail behind a proxy. Ask IT for the proxy address and set it once per tool:
```powershell
# replace with your company's proxy
$p = "http://proxy.company.com:8080"
npm config set proxy $p; npm config set https-proxy $p
pip config set global.proxy $p
git config --global http.proxy $p
[Environment]::SetEnvironmentVariable("HTTPS_PROXY", $p, "User")   # used by Go, Flutter and others
```
**Maven:** add a `<proxy>` block to `%USERPROFILE%\.m2\settings.xml`.

**Certificate errors** (for example "self-signed certificate in chain"): ask IT for the company root certificate and point each tool at it. Don't switch SSL checking off.