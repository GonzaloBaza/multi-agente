@echo off
if "%~1"=="" (
    echo Uso: borrar_conversacion.bat email@ejemplo.com
    pause
    exit /b 1
)
echo Borrando conversaciones de %1 ...
plink -ssh -batch -pw "MSK!@L4t4m" -hostkey "SHA256:oiCZ7kfsEDCMfu442Uq2xxl8U/rebAVs3x6gpJaXbgI" root@68.183.156.122 "docker exec multiagente-api-1 python3 /app/scripts/delete_conversations.py %1"
pause
