# Exact customer-credential staging and one management namespace GET. No PSDirect/MOC.
param([ValidateSet('Auto','Prepare','Read')][string]$Mode = 'Auto')
$ErrorActionPreference = 'Stop'
$result = @{ status = 'not-requested'; hostName = $env:COMPUTERNAME; atUtc = [datetime]::UtcNow.ToString('o'); namespace = 'hybridaks-operator-system'; apiRequests = 0; credentialsReturned = $false }
$certificate = $null; $request = $null; $response = $null; $memory = $null
$phase = 'host-window-check'
try {
if ($env:COMPUTERNAME -ine 'LocalBox-Client' -or $env:OS -cne 'Windows_NT') { throw 'Exact LocalBox-Client required' }
$end = [DateTimeOffset]::Parse('2026-11-09T23:50:00+02:00')
if ([DateTimeOffset]::UtcNow -ge $end) { throw 'Diagnostic phase expired' }
$phase = 'staging-path-selection'
$directory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'smal-bridge-customer-20261109-02'
$credentialPath = Join-Path $directory 'credential.json'
if ($Mode -eq 'Auto') {
    if (-not (Test-Path -LiteralPath $directory)) { $Mode = 'Prepare' }
    elseif (Test-Path -LiteralPath $credentialPath) { $Mode = 'Read' }
    else { throw 'Existing staging directory awaits its exact credential; no request permitted' }
}
$phase = 'current-user-sid'
$userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$allowed = @($userSid.Value, 'S-1-5-18', 'S-1-5-32-544')
function Get-Digest([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Assert-PrivatePath([string]$Path, [bool]$Directory) {
    $item = Get-Item -LiteralPath $Path -Force
    if ([bool]$item.PSIsContainer -ne $Directory -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Staged path type/reparse mismatch' }
    $acl = Get-Acl -LiteralPath $Path
    if ($allowed -notcontains $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value) { throw 'Staged owner mismatch' }
    if ($Directory -and -not $acl.AreAccessRulesProtected) { throw 'Staging inheritance is not disabled' }
    foreach ($rule in $acl.Access) {
        $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and $allowed -notcontains $sid) { throw 'Staging access is too broad' }
    }
}
if ($Mode -eq 'Prepare') {
    $phase = 'prepare-private-directory'
    if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse('2026-11-09T23:40:00+02:00')) { throw 'Credential staging deadline expired' }
    if (Test-Path -LiteralPath $directory) { throw 'Fresh staging directory already exists; preserve it' }
    [void][IO.Directory]::CreateDirectory($directory)
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false); $acl.SetOwner($userSid)
    foreach ($sid in $allowed) {
        $identity = New-Object Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $directory -AclObject $acl
    Assert-PrivatePath $directory $true
    @{ status = 'private-staging-directory-created'; hostName = $env:COMPUTERNAME; directory = $directory; credentialPath = $credentialPath; userSid = $userSid.Value; apiRequests = 0 } | ConvertTo-Json -Compress
    return
}
    $phase = 'credential-path-acl'
    Assert-PrivatePath $directory $true; Assert-PrivatePath $credentialPath $false
    $phase = 'credential-envelope-read-hash'
    $item = Get-Item -LiteralPath $credentialPath
    if ($item.Length -gt 262144) { throw 'Credential envelope exceeds cap' }
    $bytes = [IO.File]::ReadAllBytes($credentialPath)
    if ((Get-Digest $bytes) -cne '7662932bce431e93d0c4e9c4436cb97d8ecaf0698ac5832edbc7651a225534dc') { throw 'Exact selected credential envelope differs' }
    $phase = 'credential-envelope-parse-window'
    $config = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json; $bytes = $null
    if ($config.schemaVersion -ne 1 -or $config.profile -cne 'clusterCustomerUser' -or [DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($config.expiresAt)) { throw 'Credential profile/window mismatch' }
    $phase = 'endpoint-binding'
    $server = [uri]$config.server
    if ($server.Scheme -cne 'https' -or $server.Port -ne 6443 -or $server.AbsolutePath -cne '/' -or $server.Query -or $server.Fragment -or $server.UserInfo) { throw 'Exact private API shape mismatch' }
    if ((Get-Digest ([Text.Encoding]::UTF8.GetBytes([string]$config.server))) -cne '94b0698609eb829bcfc17a7d19cf132695b2bf3f9cf80c61381a0cb673bfa1d7') { throw 'ARM endpoint binding mismatch' }
    $phase = 'client-pfx-decode'
    $pfx = [Convert]::FromBase64String($config.clientPfx)
    $phase = 'client-pfx-ephemeral-import'
    $certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($pfx, [string]$config.clientPfxPassword, [Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet)
    $pfx = $null; $config.clientPfxPassword = $null; $config.clientPfx = $null
    $phase = 'client-private-key-check'
    if (-not $certificate.HasPrivateKey) { throw 'Customer certificate has no private key' }
    $phase = 'http-request-configure-no-send'
    $request = [Net.HttpWebRequest]::Create($server.AbsoluteUri.TrimEnd('/') + '/api/v1/namespaces/hybridaks-operator-system/pods')
    $request.Method = 'GET'; $request.AllowAutoRedirect = $false; $request.UseDefaultCredentials = $false; $request.Proxy = $null
    $request.KeepAlive = $false; $request.ConnectionGroupName = [guid]::NewGuid().ToString()
    $request.Timeout = [int][Math]::Min(15000, ($end - [DateTimeOffset]::UtcNow).TotalMilliseconds)
    if ($request.Timeout -le 0) { throw 'No diagnostic time remains' }
    $request.ReadWriteTimeout = $request.Timeout
    [void]$request.ClientCertificates.Add($certificate)
    # CLR delegate: no PowerShell callback on a transport thread without a runspace.
    $phase = 'leaf-pin-clr-compile'
    Add-Type -TypeDefinition @'
using System;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
public static class SmalBridgeLeafPin20261109 {
    public static readonly RemoteCertificateValidationCallback Callback = new RemoteCertificateValidationCallback(Verify);
    public static bool Verify(object sender, X509Certificate peer, X509Chain chain, SslPolicyErrors errors) {
        if (peer == null) return false;
        using (var sha = SHA256.Create()) {
            return BitConverter.ToString(sha.ComputeHash(peer.GetRawCertData())).Replace("-", "").ToLowerInvariant()
                == "8baf0e4e43e6f99f8228f3e68b345cfa1864e3ef1f6fb2a5c630be3a79fbfeed";
        }
    }
}
'@
    $phase = 'leaf-pin-clr-delegate-bind'
    $request.ServerCertificateValidationCallback = [SmalBridgeLeafPin20261109]::Callback
    # One-shot local marker is created before the only HTTP request. Never reset it.
    $phase = 'one-shot-marker-create'
    $marker = Join-Path $directory 'pods-request-once.marker'
    $stream = [IO.File]::Open($marker, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $stream.Dispose()
    $phase = 'pod-get'
    $result.apiRequests = 1
    try { $response = $request.GetResponse() }
    catch [Net.WebException] { if ($_.Exception.Response) { $response = $_.Exception.Response } else { throw } }
    $phase = 'pod-response-read'
    $result.httpStatus = [int]$response.StatusCode
    $input = $response.GetResponseStream(); $memory = New-Object IO.MemoryStream
    try {
        $buffer = New-Object byte[] 8192
        while (($count = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($memory.Length + $count -gt 1048576 -or [DateTimeOffset]::UtcNow -ge $end) { throw 'Response/time cap exceeded' }
            $memory.Write($buffer, 0, $count)
        }
    } finally { $input.Dispose() }
    $phase = 'pod-response-private-save'
    $body = $memory.ToArray(); $rawPath = Join-Path $directory 'pods-response-private.json'
    $stream = [IO.File]::Open($rawPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($body, 0, $body.Length) } finally { $stream.Dispose() }
    $result.responseSha256 = Get-Digest $body
    $phase = 'pod-response-status-projection'
    if ($result.httpStatus -ne 200) { throw 'Pod GET returned non-200; private body retained' }
    $pods = [Text.Encoding]::UTF8.GetString($body) | ConvertFrom-Json
    if ($pods.kind -cne 'PodList') { throw 'Unexpected pod response shape' }
    $result.pods = @($pods.items | ForEach-Object {
        @{ name = $_.metadata.name; uid = $_.metadata.uid; phase = $_.status.phase
           conditions = @($_.status.conditions | Select-Object type, status, reason, lastTransitionTime)
           containers = @($_.status.containerStatuses | ForEach-Object { @{ name = $_.name; ready = $_.ready; restartCount = $_.restartCount
               waitingReason = $_.state.waiting.reason; terminatedReason = $_.state.terminated.reason; exitCode = $_.state.terminated.exitCode
               lastTerminatedReason = $_.lastState.terminated.reason; lastExitCode = $_.lastState.terminated.exitCode } }) }
    })
    $result.status = 'management-pod-status-read'
} catch {
    $result.status = 'stopped-no-retry'
    $result.failurePhase = $phase
    $result.sourceLine = [int]$_.InvocationInfo.ScriptLineNumber
    $result.errorCategory = $_.CategoryInfo.Category.ToString()
    # Never emit messages, source text or an arbitrary FullyQualifiedErrorId.
    $result.safeErrorId = switch -Exact ($_.FullyQualifiedErrorId) {
        'MethodInvocationException' { 'MethodInvocationException'; break }
        'ExceptionWhenSetting' { 'ExceptionWhenSetting'; break }
        'InvalidCastException' { 'InvalidCastException'; break }
        'ParameterArgumentTransformationError' { 'ParameterArgumentTransformationError'; break }
        default { 'UnclassifiedError' }
    }
}
finally {
    if ($response) { $response.Close() }; if ($request) { $request.Abort() }; if ($memory) { $memory.Dispose() }; if ($certificate) { $certificate.Dispose() }
    $config = $null
}
# Parent may remove only the exact staged credential after this reader process has exited.
$result | ConvertTo-Json -Depth 9 -Compress
