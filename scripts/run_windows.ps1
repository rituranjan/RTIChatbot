$root = Resolve-Path "$PSScriptRoot\.."

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd '$root\backend'; .\.venv\Scripts\Activate.ps1; python manage.py runserver 127.0.0.1:8000"
)

Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd '$root\frontend'; npm run dev"
)

Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:5173"