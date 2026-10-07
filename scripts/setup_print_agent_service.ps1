$nssm = "C:\Program Files\nssm\nssm.exe"
$python = "C:\Path\To\python.exe"
$scriptDir = "./wheresdat\scripts"

& $nssm install WheresDatPrintAgent $python
& $nssm set WheresDatPrintAgent AppParameters "print_agent.py"
& $nssm set WheresDatPrintAgent AppDirectory $scriptDir
& $nssm set WheresDatPrintAgent AppStdout "$scriptDir\print_agent.log"
& $nssm set WheresDatPrintAgent AppStderr "$scriptDir\print_agent.log"
& $nssm set WheresDatPrintAgent Start SERVICE_AUTO_START
& $nssm set WheresDatPrintAgent DisplayName "WheresDat Print Agent"
& $nssm set WheresDatPrintAgent Description "Local HTTP wrapper around print_label.py so the WheresDat registration UI can print to the USB-attached Phomemo M110S."
& $nssm start WheresDatPrintAgent

Start-Sleep -Seconds 2
Invoke-RestMethod http://localhost:8104/health
