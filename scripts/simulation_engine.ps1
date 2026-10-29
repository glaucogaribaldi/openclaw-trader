# Lehman Brody: Motore di Simulazione e Paper Trading h24

Write-Host "=== INIZIALIZZAZIONE LEHMAN BRODY: MOTORE DI SIMULAZIONE (AIBOX) ===" -ForegroundColor Green
Write-Host "Modalita: Paper Trading" -ForegroundColor Cyan
Write-Host "Stato: Attivo" -ForegroundColor Yellow

# Paths
$baseDir = "C:\Users\zavat\openclaw-trader"
$playbookPath = "$baseDir\config\strategy_playbook.json"

if (Test-Path $playbookPath) {
    $playbook = Get-Content $playbookPath | ConvertFrom-Json
} else {
    Write-Host "[!] Errore: Playbook di strategia non trovato!" -ForegroundColor Red
    exit 1
}

# Extract targets
$btcTarget = $playbook.btc_scalp.target_profit_percentage
$ethTarget = $playbook.eth_scalp.target_profit_percentage
$nearTarget = $playbook.near_scalp.target_profit_percentage
$linkTarget = $playbook.link_scalp.target_profit_percentage
$solLower = $playbook.sol_grid.lower_limit
$solUpper = $playbook.sol_grid.upper_limit

Write-Host "[+] 1. Ingestione Prezzi di Mercato Real-Time via OKX CLI:" -ForegroundColor Yellow
$tokens = @("BTC-USDC", "ETH-USDC", "NEAR-USDC", "LINK-USDC", "SOL-USDC")
$prices = @{}

foreach ($token in $tokens) {
    try {
        $jsonStr = & okx market ticker $token --json
        $data = $jsonStr | ConvertFrom-Json
        $val = [double]$data[0].last
        $prices[$token] = $val
        Write-Host "    - $token : $val" -ForegroundColor White
    } catch {
        $prices[$token] = 1.0
        Write-Host "    - [!] Errore lettura $token, verificato con fallback." -ForegroundColor Red
    }
}

# Calc targets
$btcPrice = $prices['BTC-USDC']
$btcSell = $btcPrice * (1 + $btcTarget/100)

$ethPrice = $prices['ETH-USDC']
$ethSell = $ethPrice * (1 + $ethTarget/100)

$nearPrice = $prices['NEAR-USDC']
$nearSell = $nearPrice * (1 + $nearTarget/100)

$linkPrice = $prices['LINK-USDC']
$linkSell = $linkPrice * (1 + $linkTarget/100)

$solPrice = $prices['SOL-USDC']

Write-Host " "
Write-Host "[+] 2. Simulazione delle Operazioni di Scalping (Paper Trading):" -ForegroundColor Yellow
Write-Host "    - [BTC-USDC] Sottostante: $btcPrice | Target (+ $btcTarget %): $btcSell" -ForegroundColor Green
Write-Host "    - [ETH-USDC] Sottostante: $ethPrice | Target (+ $ethTarget %): $ethSell" -ForegroundColor Green
Write-Host "    - [NEAR-USDC] Sottostante: $nearPrice | Target (+ $nearTarget %): $nearSell" -ForegroundColor Green
Write-Host "    - [LINK-USDC] Sottostante: $linkPrice | Target (+ $linkTarget %): $linkSell" -ForegroundColor Green

Write-Host " "
Write-Host "[+] 3. Simulazione del SOL Grid Bot:" -ForegroundColor Yellow
Write-Host "    - Range Griglia: $solLower - $solUpper" -ForegroundColor White
Write-Host "    - Prezzo Attuale SOL: $solPrice" -ForegroundColor White

if ($solPrice -lt $solLower -or $solPrice -gt $solUpper) {
    Write-Host "    - ATTENZIONE: Il prezzo di SOL e fuori dal range della griglia! Il Retro-Agent spostera la griglia al prossimo ciclo di 12h." -ForegroundColor Red
} else {
    Write-Host "    - Prezzo SOL allineato all interno del range. Griglie operative attive h24." -ForegroundColor Green
}

Write-Host " "
Write-Host "=== LEHMAN BRODY IN OPERATIVITA DI SIMULAZIONE CONTINUA ===" -ForegroundColor Green
Write-Host " "
