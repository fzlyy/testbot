#requires -Version 5.1
<#
.SYNOPSIS
    NapCat + AstrBot + DeepSeek 部署自检。

.DESCRIPTION
    检查四件事：
      1. 三个端口是否在监听（6185 AstrBot WebUI / 6199 反向 WS / 6099 NapCat WebUI）
      2. 相关进程是否在跑
      3. DeepSeek API 是否可用（列出模型 + 发一条最小对话）
      4. 常见配置目录是否存在

    不修改任何东西，只读。

.PARAMETER ApiKey
    DeepSeek API Key。不给则读环境变量 DEEPSEEK_API_KEY。

.PARAMETER Model
    用于试聊的模型，默认 deepseek-flash。

.PARAMETER Proxy
    HTTPS 代理，例如 http://127.0.0.1:7890。不给则读环境变量 HTTPS_PROXY。

.EXAMPLE
    .\scripts\check-stack.ps1 -ApiKey sk-xxxx

.EXAMPLE
    .\scripts\check-stack.cmd -ApiKey sk-xxxx -Proxy http://127.0.0.1:7890

.EXAMPLE
    $env:DEEPSEEK_API_KEY = 'sk-xxxx'; .\scripts\check-stack.cmd
#>
[CmdletBinding()]
param(
    [string]$ApiKey = $env:DEEPSEEK_API_KEY,
    [string]$Model = 'deepseek-flash',
    [int]$AstrBotPort = 6185,
    [int]$OneBotPort = 6199,
    [int]$NapCatPort = 6099,
    [string]$Proxy = $env:HTTPS_PROXY,
    [switch]$SkipApi
)

$ErrorActionPreference = 'Continue'
$script:fail = 0
$script:warn = 0

function Write-Result {
    param([string]$Status, [string]$Name, [string]$Detail = '')
    switch ($Status) {
        'OK'   { $color = 'Green' }
        'WARN' { $color = 'Yellow'; $script:warn++ }
        'FAIL' { $color = 'Red';    $script:fail++ }
        default { $color = 'Gray' }
    }
    $tag = "[$Status]".PadRight(6)
    Write-Host ("$tag $Name") -NoNewline -ForegroundColor $color
    if ($Detail) { Write-Host "  $Detail" -ForegroundColor DarkGray } else { Write-Host '' }
}

function Test-TcpPort {
    param([string]$TargetHost = '127.0.0.1', [int]$Port, [int]$TimeoutMs = 800)
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($iar)
        return $true
    }
    catch { return $false }
    finally { if ($client) { $client.Close() } }
}

function Get-PortOwner {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                Select-Object -First 1
        if (-not $conn) { return '' }
        $p = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($p) { return "$($p.ProcessName) (PID $($p.Id))" }
        return "PID $($conn.OwningProcess)"
    }
    catch { return '' }
}

Write-Host ''
Write-Host '== NapCat + AstrBot + DeepSeek 自检 ==' -ForegroundColor Cyan
Write-Host ("   时间：{0}  主机：{1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $env:COMPUTERNAME) -ForegroundColor DarkGray
Write-Host ''

# ---------- 1. 端口 ----------
Write-Host '-- 端口 --' -ForegroundColor Cyan

$ports = @(
    @{ Port = $AstrBotPort; Name = "AstrBot WebUI  ($AstrBotPort)"; Hint = '没监听：AstrBot 没启动，或改了 dashboard.port' },
    @{ Port = $OneBotPort;  Name = "OneBot v11 反向WS ($OneBotPort)"; Hint = '没监听：AstrBot 里 OneBot v11 机器人没启用，或端口不一致' },
    @{ Port = $NapCatPort;  Name = "NapCat WebUI  ($NapCatPort)"; Hint = '没监听：NapCat 没启动，或 WebUI 未开启' }
)

foreach ($item in $ports) {
    if (Test-TcpPort -Port $item.Port) {
        Write-Result OK $item.Name (Get-PortOwner -Port $item.Port)
    }
    else {
        Write-Result WARN $item.Name $item.Hint
    }
}

# ---------- 2. 进程 ----------
Write-Host ''
Write-Host '-- 进程 --' -ForegroundColor Cyan

$interesting = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match '^(QQ|NapCat|python|pythonw|uv|uvicorn|AstrBot|Node|docker)' } |
    Sort-Object ProcessName -Unique

if ($interesting) {
    $names = ($interesting | ForEach-Object { $_.ProcessName }) -join ', '
    Write-Result OK '相关进程' $names
    if (-not ($interesting.ProcessName -match 'QQ')) {
        Write-Result WARN 'QQ 进程' '没看到 QQ 在跑，NapCat 通常需要它（一键安装版会自带）'
    }
}
else {
    Write-Result WARN '相关进程' '没看到 QQ / python / AstrBot / docker 进程'
}

# ---------- 3. 配置目录 ----------
Write-Host ''
Write-Host '-- 文件 --' -ForegroundColor Cyan

$cfgCandidates = @(
    (Join-Path (Get-Location) 'data/cmd_config.json'),
    (Join-Path (Get-Location) 'data\cmd_config.json')
) | Select-Object -Unique

$foundCfg = $cfgCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($foundCfg) {
    Write-Result OK 'AstrBot 配置' $foundCfg
}
else {
    Write-Result WARN 'AstrBot 配置' '当前目录没找到 data/cmd_config.json（在别的目录跑就在那个目录执行本脚本）'
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    $running = docker ps --format '{{.Names}}' 2>$null
    if ($LASTEXITCODE -eq 0 -and $running) {
        Write-Result OK 'Docker 容器' (($running -join ', '))
    }
    elseif ($LASTEXITCODE -eq 0) {
        Write-Result WARN 'Docker 容器' 'docker 可用，但没有运行中的容器'
    }
    else {
        Write-Result WARN 'Docker' 'docker 命令存在但调用失败（Docker Desktop 没启动？）'
    }
}
else {
    Write-Result OK 'Docker' '未安装（用非 Docker 方式部署时可忽略）'
}

# ---------- 4. DeepSeek API ----------
Write-Host ''
Write-Host '-- DeepSeek API --' -ForegroundColor Cyan

if ($SkipApi) {
    Write-Result OK 'API 检查' '已跳过 (-SkipApi)'
}
elseif ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Result WARN 'API Key' '未提供：加 -ApiKey sk-xxx，或设置环境变量 DEEPSEEK_API_KEY'
}
else {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
    $headers = @{ Authorization = "Bearer $ApiKey" }
    $base = 'https://api.deepseek.com'
    $irmCommon = @{ TimeoutSec = 30 }
    if ($Proxy) { $irmCommon['Proxy'] = $Proxy }

    if (Test-TcpPort -TargetHost 'api.deepseek.com' -Port 443 -TimeoutMs 3000) {
        Write-Result OK '到 api.deepseek.com:443' 'TCP 可达'
    }
    else {
        Write-Result WARN '到 api.deepseek.com:443' 'TCP 不可达（需要代理或防火墙拦截）'
    }

    # 4.1 列模型
    $modelIds = @()
    try {
        $resp = Invoke-RestMethod -Uri "$base/models" -Headers $headers -Method Get @irmCommon
        $modelIds = @($resp.data | ForEach-Object { $_.id })
        if ($modelIds.Count -gt 0) {
            Write-Result OK 'API 鉴权与连通' ("可用模型: " + ($modelIds -join ', '))
        }
        else {
            Write-Result WARN 'API 鉴权与连通' '/models 返回空列表'
        }
    }
    catch {
        $msg = $_.Exception.Message
        if ($msg -match '401|403') {
            Write-Result FAIL 'API 鉴权' "Key 无效或被删除（$msg）"
        }
        elseif ($msg -match '402') {
            Write-Result FAIL 'API 鉴权' "余额不足（$msg）"
        }
        elseif ($msg -match '429') {
            Write-Result WARN 'API 鉴权' "频率超限（$msg）"
        }
        else {
            Write-Result FAIL 'API 连通' "$msg （检查网络/代理）"
        }
    }

    # 4.2 试聊
    if ($modelIds.Count -gt 0 -and ($modelIds -notcontains $Model)) {
        Write-Result WARN '模型可用性' "账号看不到 '$Model'，可用: $($modelIds -join ', ')"
    }
    if ($modelIds.Count -eq 0 -or ($modelIds -contains $Model)) {
        $body = @{
            model    = $Model
            messages = @(@{ role = 'user'; content = '只回复两个字：收到' })
            stream   = $false
            max_tokens = 16
        } | ConvertTo-Json -Depth 6 -Compress
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $chat = Invoke-RestMethod -Uri "$base/chat/completions" -Headers $headers -Method Post `
                    -ContentType 'application/json; charset=utf-8' -Body $body @irmCommon
            $sw.Stop()
            $text = $chat.choices[0].message.content
            $usage = $chat.usage
            Write-Result OK "试聊 $Model" ("{0:N0} ms，回复: {1}，tokens: {2}" -f $sw.ElapsedMilliseconds, ($text -replace '\s+', ' '), $usage.total_tokens)
        }
        catch {
            $sw.Stop()
            Write-Result FAIL "试聊 $Model" $_.Exception.Message
        }
    }
}

# ---------- 总结 ----------
Write-Host ''
Write-Host '-- 结论 --' -ForegroundColor Cyan

if ($script:fail -eq 0 -and $script:warn -eq 0) {
    Write-Host '  全部通过。' -ForegroundColor Green
}
elseif ($script:fail -eq 0) {
    Write-Host ("  {0} 项提示，0 项失败。按上面的提示逐条看 README 第 9 节。" -f $script:warn) -ForegroundColor Yellow
}
else {
    Write-Host ("  {0} 项失败，{1} 项提示。先修失败项：README 第 5 节（连接）/ 第 3 节（模型）。" -f $script:fail, $script:warn) -ForegroundColor Red
}
Write-Host ''
Write-Host '  提示：端口检查只看「有没有监听」，不看「能不能通消息」。' -ForegroundColor DarkGray
Write-Host '        真正的连接成功标志是 AstrBot 日志里的：aiocqhttp(OneBot v11) 适配器已连接。' -ForegroundColor DarkGray
Write-Host ''

exit ([int]($script:fail -gt 0))
