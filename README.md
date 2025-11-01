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
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install fastapi uvicorn[standard] python-dotenv pydantic pyyaml

- Um Backend zu starten, führe aus dem Ordner backend `uvicorn app:app --reload --port 8000` im Terminal aus
- health check: curl http://127.0.0.1:8000/health

## 4) Frontend Setup

- Frontend kann in der IDE mittels Run-Button gestartet werden oder im Terminal, in der Run-Konfiguration von main.dart muss 
  unter "Additional run args"  `uvicorn app:app --reload --port 8000`
  angegeben werden.

