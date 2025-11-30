# Colours of Wine — Kurz-Setup & Commands

## 1) Voraussetzungen
- **Python 3.12** (oder 3.11+)
- **Edge/Chrome**
- **Flutter SDK**

## 2) IntelliJ Setup
- Flutter installieren und entpacken, dann in PATH (Windows Umgebungsvariablen) einfügen
- In IntelliJ IDEA das Flutter Plugin installieren
- In IntelliJ IDEA ein neues Flutter Projekt erstellen und den Pfad zum Flutter SDK angeben
- Im Terminal des Projekts `flutter pub get` ausführen, um die Abhängigkeiten zu installieren
- Im Terminal des Projekts `flutter doctor` ausführen, um sicherzustellen, dass alle Voraussetzungen erfüllt sind

## 3) Backend Setup
- Im Terminal des Projekts folgende Befehle ausführen, um das Backend einzurichten:
1. `cd backend`
2. `py -3.12 -m venv .venv`
3. `source .venv/bin/activate` (Linux/Mac)
4.  Die API keys in `backend/.env` einfügen
5.  Die API keys im folgenden Format in `backend/.venv/activate` einfügen:
    - `export GEMINI_API_KEY="DEIN_GEMINI_KEY"`
    - `export GOOGLE_SEARCH_API_KEY="DEIN_GOOGLE_SEARCH_KEY"`
    - `export GOOGLE_CSE_ID="DEINE_CSE_ID"`
6. `pip install fastapi uvicorn[standard] python-dotenv pydantic pyyaml httpx google-generativeai pillow numpy`

- Um Backend zu starten, führe folgendes im Terminal aus:
- 1. `source backend/.venv/bin/activate` # damit die virtuelle Umgebung aktiviert wird
- 2. `uvicorn app:app --reload --port 8000` # damit der Server gestartet wird
- health check: curl http://127.0.0.1:8000/health

## 4) Frontend Setup
- Frontend kann in der IDE mittels Run-Button gestartet werden oder im Terminal, in der Run-Konfiguration von main.dart muss
  unter "Additional run args" die backend URL angegeben werden: `--dart-define=BACKEND_URL=http://127.0.0.1:8000/analyze`

## 5) Nützliche Hinweise
- Änderungen am Backend werden automatisch übernommen, wenn `--reload` beim Starten von Uvicorn angegeben wurde.
- Änderungen am Frontend erfordern einen Neustart der App.
