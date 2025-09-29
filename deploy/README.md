# Deployment Guide

This document captures the remaining steps to complete production deployment on the Windows server.

## 1. Auto-start service (already configured)

- Script: `scripts/start_waitress.ps1` launches Waitress with the virtual environment.
- Scheduled Task: **Feishu Waitress Service** (runs at startup and user logon under SYSTEM, highest privileges).
- Logs:
  - Waitress output: `logs/waitress-YYYYMMDD.log`
  - Application log (rotating 1 MB × 5 backups): `logs/app.log`
- Manual trigger for verification:
  ```powershell
  schtasks /Run /TN "Feishu Waitress Service"
  Get-Content .\logs\waitress-$(Get-Date -Format 'yyyyMMdd').log -Tail 20
  ```

## 2. Install and configure NGINX reverse proxy + HTTPS

1. Download Windows NGINX from <http://nginx.org/en/download.html> (stable build zip).
2. Extract to `C:\nginx` (or another location). Run PowerShell as admin and execute:
   ```powershell
   Expand-Archive -Path .\nginx-*.zip -DestinationPath C:\ -Force
   Rename-Item C:\nginx-* nginx
   ```
3. Place your TLS certificate and key files on the server (PEM format). Example paths: `C:\nginx\certs\fullchain.pem`, `C:\nginx\certs\privkey.pem`.
4. Copy the provided config:
   ```powershell
   Copy-Item .\deploy\nginx.conf C:\nginx\conf\nginx.conf -Force
   ```
5. Edit `C:\nginx\conf\nginx.conf` to update:
   - `server_name` if you have a domain.
   - `ssl_certificate` / `ssl_certificate_key` with your actual file paths.
6. Start NGINX:
   ```powershell
   Start-Process C:\nginx\nginx.exe
   ```
7. On config changes, reload:
   ```powershell
   C:\nginx\nginx.exe -s reload
   ```
8. Verify:
   ```powershell
   Test-NetConnection 127.0.0.1 -Port 80
   Test-NetConnection 127.0.0.1 -Port 443
   curl -k https://localhost/healthz
   ```

## 3. Monitoring & housekeeping

- **Health checks**: endpoint `https://<host>/healthz` (returns `{"status":"ok"}`).
- **Logs**: ensure a scheduled task/log rotation policy copies `logs/*.log` to long-term storage or log service.
- **Backups**: back up `requirements.txt`, `.env`, and `logs/` regularly.
- **Security**: ensure Windows Firewall allows ports 80/443; close 9876 externally once NGINX is in front. Update certificates before expiration.
- **Updates**: when deploying new code, stop Waitress (`schtasks /End /TN "Feishu Waitress Service"`), pull changes, run tests, then re-run the task.

## 4. Optional: IIS instead of NGINX

If you prefer IIS:
1. Install IIS + URL Rewrite + Application Request Routing (ARR).
2. Create a website bound to ports 80/443, point to `C:\inetpub\wwwroot` placeholder.
3. Set up a reverse proxy rule to `http://127.0.0.1:9876` with HTTP/2 and SSL.
4. Import certificate into the Windows certificate store and bind to HTTPS site.

Pick whichever proxy stack matches your team's expertise.
