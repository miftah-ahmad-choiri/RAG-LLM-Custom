' ============================================================
'  Launch IBM Ceph RAG
'  Double-click to start — fully self-contained:
'    0. Create .venv + install dependencies if missing
'    1. Install Ollama if not found
'    2. Ollama server        (stays running in background)
'    3. nomic-embed-text     (pulled once, skipped if exists)
'    4. Flask app            (opens in its own window)
'    5. Browser              (http://127.0.0.1:5000/rag)
' ============================================================

Option Explicit

Dim oShell, oFSO, sRoot, sVenvPython, sOllama

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")

sRoot       = oFSO.GetParentFolderName(WScript.ScriptFullName)
sVenvPython = sRoot & "\.venv\Scripts\python.exe"

' ── 0. Locate ollama.exe ──────────────────────────────────────────────────
sOllama = "E:\ollama\bin\ollama.exe"
If Not oFSO.FileExists(sOllama) Then
    Dim sLocalApp : sLocalApp = oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
    sOllama = sLocalApp & "\Programs\Ollama\ollama.exe"
End If

' ── 1. Install Ollama if not found ────────────────────────────────────────
If Not oFSO.FileExists(sOllama) Then
    Dim iAns
    iAns = MsgBox("Ollama is not installed." & vbCrLf & vbCrLf & _
                  "Click OK to install it now using the official installer." & vbCrLf & _
                  "A PowerShell window will open — wait for it to finish," & vbCrLf & _
                  "then double-click this file again.", _
                  vbOKCancel + vbInformation, "Ollama Not Found")
    If iAns <> vbOK Then WScript.Quit

    oShell.Run "powershell -NoProfile -Command ""irm https://ollama.com/install.ps1 | iex""", 1, True

    If Not oFSO.FileExists(sOllama) Then
        MsgBox "Installation did not complete. Please try again.", vbCritical, "Install Failed"
        WScript.Quit
    End If

    MsgBox "Ollama installed!" & vbCrLf & _
           "Double-click this file again to launch the app.", _
           vbInformation, "Done"
    WScript.Quit
End If

' ── 2. Start Ollama serve (minimised, keeps running) ──────────────────────
oShell.Run "cmd /c start ""Ollama Server"" /min cmd /k set OLLAMA_MODELS=E:\ollama\models && """ & sOllama & """ serve", 1, False

' Give Ollama a moment to bind its port
WScript.Sleep 3000

' ── 3. Pull nomic-embed-text (shows briefly, closes when done) ────────────
oShell.Run "cmd /c set OLLAMA_MODELS=E:\ollama\models && """ & sOllama & """ pull nomic-embed-text", 1, True

' ── 4. Run start.py — handles venv creation, pip install, and Flask launch ─
' Write a .bat to handle the path safely
Dim sBat : sBat = oShell.ExpandEnvironmentStrings("%TEMP%") & "\launch_ceph_rag.bat"
Dim oTxt : Set oTxt = oFSO.CreateTextFile(sBat, True, False)
oTxt.WriteLine "@echo off"
oTxt.WriteLine "cd /d """ & sRoot & """"
oTxt.WriteLine "python start.py"
oTxt.Close
Set oTxt = Nothing
oShell.Run "cmd /c start ""IBM Ceph RAG"" cmd /k """ & sBat & """", 1, False

' Wait for Flask to finish starting up (longer on first run due to pip install)
WScript.Sleep 8000

' ── 5. Open the RAG UI in the default browser ─────────────────────────────
oShell.Run "http://127.0.0.1:5000/rag"

Set oShell = Nothing
Set oFSO   = Nothing
