@echo off
rem WoL prep: turn OFF Realtek Green Ethernet / Power Saving Mode (they can block wake-from-shutdown). Needs admin: self-elevates (click Yes).
rem Undo: set the same two keywords back to 1 (EnableGreenEthernet, PowerSavingMode).
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a=Get-NetAdapter | Where-Object InterfaceDescription -like 'Realtek*'; foreach($k in 'EnableGreenEthernet','PowerSavingMode'){ Set-NetAdapterAdvancedProperty -Name $a.Name -RegistryKeyword $k -RegistryValue 0 }; Get-NetAdapterAdvancedProperty -Name $a.Name | Where-Object RegistryKeyword -in 'EnableGreenEthernet','PowerSavingMode','S5WakeOnLan','*WakeOnMagicPacket' | Format-Table RegistryKeyword,RegistryValue,DisplayValue -AutoSize"
echo.
echo DONE. Expected: EnableGreenEthernet=0, PowerSavingMode=0, S5WakeOnLan=1, WakeOnMagicPacket=1
pause
