$cfg  = Import-PowerShellDataFile C:\LocalBox\LocalBox-Config.psd1
$cred = New-Object System.Management.Automation.PSCredential(
          "jumpstart\Administrator",
          (ConvertTo-SecureString $cfg.SDNAdminPassword -AsPlainText -Force))
Invoke-Command -VMName AzLHOST1 -Credential $cred -ScriptBlock { azcmagent check } | Out-String
