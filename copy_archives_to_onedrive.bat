@echo off

set SOURCE=azureuser@20.213.77.211:/home/azureuser/OneDrive/BridgeDigitalTwin/Archive
set DEST=%USERPROFILE%\OneDrive - Monash University\BridgeDigitalTwin\Archive
set KEY=%USERPROFILE%\.ssh\id_ed25519

scp -r -i "%KEY%" "%SOURCE%/*" "%DEST%"

pause