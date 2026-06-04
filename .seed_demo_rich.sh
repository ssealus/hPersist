#!/bin/bash
# Rich seed: 12 emulators × 6 mockups, 17 inventories across 90 days, varied
# orgs/sizes/statuses, plus warmed PartSurfer cache and a deep Redfish history.
# Wipes data/ and starts the app live on :8099. Read the rest at the bottom.

B=http://localhost:8099/api/v1
PY=e:/Projects/hPersist/venv/Scripts/python.exe
APP_DIR=e:/Projects/hPersist

post_collection() {
    local NAME="$1" ORG="$2" DESC="$3" HOSTS_JSON="$4" CONC="${5:-4}"
    curl -s -X POST $B/collections -H "Content-Type: application/json" \
        -d "{\"name\":\"$NAME\",\"organization\":\"$ORG\",\"description\":\"$DESC\",\"mode\":\"cidr\",\"default_login\":\"root\",\"default_password\":\"root_password\",\"hosts\":$HOSTS_JSON,\"timeout\":12.0,\"concurrency\":$CONC}" \
        | $PY -c "import json,sys; print(json.load(sys.stdin).get('id',''))"
}

wait_inv() {
    local ID="$1"
    for i in $(seq 1 25); do
        sleep 1
        ST=$(curl -s $B/inventories/$ID 2>/dev/null | $PY -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
        case "$ST" in complete|complete-warn|failed) return 0;; esac
    done
    return 0
}

# Builds a JSON host list cycling through the given IP range.
# usage: hosts_for 5 prod-east 1 12   → 5 hosts named prod-east-01..05 over IPs .1-.12
hosts_for() {
    local n="$1" prefix="$2" ip_lo="$3" ip_hi="$4"
    $PY -c "
import json
n, prefix, lo, hi = $n, '$prefix', $ip_lo, $ip_hi
hosts = []
for i in range(n):
    ip = f'127.0.0.{lo + (i % (hi - lo + 1))}'
    hosts.append({'ip': ip, 'hostname': f'{prefix}-{i+1:02d}', 'login': 'root', 'password': 'root_password'})
print(json.dumps(hosts))
"
}

# Same, but mixes in 1-2 unreachable IPs to force complete-warn status.
hosts_with_warn() {
    local n="$1" prefix="$2" ip_lo="$3" ip_hi="$4" n_warn="${5:-1}"
    $PY -c "
import json
n, prefix, lo, hi, warn = $n, '$prefix', $ip_lo, $ip_hi, $n_warn
hosts = []
for i in range(n - warn):
    ip = f'127.0.0.{lo + (i % (hi - lo + 1))}'
    hosts.append({'ip': ip, 'hostname': f'{prefix}-{i+1:02d}', 'login': 'root', 'password': 'root_password'})
for i in range(warn):
    hosts.append({'ip': f'127.0.0.{200+i}', 'hostname': f'{prefix}-warn-{i+1}', 'login': 'root', 'password': 'root_password'})
print(json.dumps(hosts))
"
}

probe_redfish() {
    curl -s -X POST $B/tools/redfish-test -H "Content-Type: application/json" -d "$1" > /dev/null 2>&1
}

backdate_sqlite() {
    local INV="$1" DAYS="$2"
    $PY -c "
import sqlite3
c = sqlite3.connect('$APP_DIR/data/hpersist.db')
c.execute(\"UPDATE inventories SET created_at = datetime('now', '-$DAYS days'), completed_at = datetime('now', '-$DAYS days', '+45 seconds') WHERE id = '$INV'\")
c.commit()
c.close()
print('  backdated $INV by $DAYS days')
"
}

echo "════════════════════════ STEP 1 ════════════════════════"
echo "Spin up 12 emulators × 6 mockups (2 of each)"
docker ps -a --filter "name=hpemu_seed" -q | xargs -r docker rm -f > /dev/null 2>&1
declare -a MODELS=(DL360 DL380a DL365_Gen10Plus DL325_Gen10Plus_FC DL380a_Gen12 EX235a)
for i in $(seq 1 12); do
    model=${MODELS[$(( (i-1) % 6 ))]}
    docker run -d --name "hpemu_seed_$i" \
        -e MOCKUP_FOLDER=$model \
        -e ASYNC_SLEEP=0 \
        -p "127.0.0.$i:443:443" \
        ilo-emulator:latest > /dev/null
done
sleep 10
READY=0
for i in $(seq 1 12); do
    curl -sk -u root:root_password --connect-timeout 3 https://127.0.0.$i/redfish/v1/ > /dev/null 2>&1 && READY=$((READY+1))
done
echo "  emulators ready: $READY/12"

echo
echo "════════════════════════ STEP 2 ════════════════════════"
echo "Clean DB + bring app up"
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>&1 > /dev/null
sleep 1
rm -f $APP_DIR/data/hpersist.db* 2>/dev/null
powershell -Command "cmd /c '$APP_DIR\\start.bat --port 8099'" > /tmp/seed_app.log 2>&1 &
APP_PID=$!
sleep 8
if curl -sf $B/health > /dev/null; then
    echo "  app responding on :8099"
else
    echo "  ERROR app not responding"; tail -20 /tmp/seed_app.log; exit 1
fi

echo
echo "════════════════════════ STEP 3 ════════════════════════"
echo "Seed 17 inventories — varied orgs, sizes, statuses"

# ── Acme Corp (primary tenant, 6 inventories, biggest footprint) ──
INV01=$(post_collection "prod-rack-fra-01" "Acme Corp" "Primary production rack, Frankfurt DC, row A" "$(hosts_for 12 prod-fra-a 1 6)" 6)
echo "  [01] $INV01  prod-rack-fra-01    Acme Corp     12 hosts"

INV02=$(post_collection "prod-rack-fra-02" "Acme Corp" "Primary production rack, Frankfurt DC, row B" "$(hosts_for 10 prod-fra-b 7 12)" 5)
echo "  [02] $INV02  prod-rack-fra-02    Acme Corp     10 hosts (-2d)"

INV03=$(post_collection "prod-rack-ams-01" "Acme Corp" "Amsterdam production extension" "$(hosts_for 8 prod-ams 1 8)" 4)
echo "  [03] $INV03  prod-rack-ams-01    Acme Corp     8 hosts (-7d)"

INV04=$(post_collection "prod-rack-dub-01" "Acme Corp" "Dublin DR site, full sync" "$(hosts_with_warn 15 prod-dub 1 12 1)" 5)
echo "  [04] $INV04  prod-rack-dub-01    Acme Corp     15 hosts, 1 unreachable (-14d)"

INV05=$(post_collection "staging-cluster-eu" "Acme Corp" "EU staging pre-prod" "$(hosts_for 6 stg 5 10)" 4)
echo "  [05] $INV05  staging-cluster-eu  Acme Corp     6 hosts (-3d)"

INV06=$(post_collection "dev-pool" "Acme Corp" "Engineering dev pool" "$(hosts_for 4 dev 1 4)" 3)
echo "  [06] $INV06  dev-pool            Acme Corp     4 hosts (-5d)"

# ── Globex Industries (DR + legacy fleet) ──
INV07=$(post_collection "dr-site-london" "Globex Industries" "London DR, quarterly compliance audit" "$(hosts_for 8 dr-lon 1 8)" 4)
echo "  [07] $INV07  dr-site-london      Globex        8 hosts (-30d)"

INV08=$(post_collection "dr-site-paris" "Globex Industries" "Paris DR, half-year audit" "$(hosts_for 6 dr-par 3 9)" 4)
echo "  [08] $INV08  dr-site-paris       Globex        6 hosts (-60d)"

INV09=$(post_collection "legacy-fleet-q2" "Globex Industries" "Legacy fleet, biannual inventory" "$(hosts_with_warn 25 legacy 1 12 2)" 6)
echo "  [09] $INV09  legacy-fleet-q2     Globex        25 hosts, 2 unreachable (-90d)"

# ── Initech (customer colo) ──
INV10=$(post_collection "colo-equinix-fra4" "Initech" "Customer rack at Equinix FRA4" "$(hosts_with_warn 12 colo-frα 1 10 2)" 5)
echo "  [10] $INV10  colo-equinix-fra4   Initech       12 hosts, 2 unreachable (-10d)"

# ── Hyperion Labs (R&D + HPC) ──
INV11=$(post_collection "lab-rd-floor3" "Hyperion Labs" "R&D floor 3 server room" "$(hosts_for 10 lab-rd 1 10)" 5)
echo "  [11] $INV11  lab-rd-floor3       Hyperion      10 hosts (-45d)"

INV12=$(post_collection "hpc-pilot-batch" "Hyperion Labs" "HPC cluster pilot, batch 1" "$(hosts_for 8 hpc 3 10)" 5)
echo "  [12] $INV12  hpc-pilot-batch     Hyperion      8 hosts (-25d)"

# ── Vertex Pharma (edge POPs) ──
INV13=$(post_collection "edge-pop-mil" "Vertex Pharma" "Edge POP Milan" "$(hosts_for 4 edge-mil 1 4)" 3)
echo "  [13] $INV13  edge-pop-mil        Vertex Pharma 4 hosts (-8d)"

INV14=$(post_collection "edge-pop-mad" "Vertex Pharma" "Edge POP Madrid" "$(hosts_for 4 edge-mad 5 8)" 3)
echo "  [14] $INV14  edge-pop-mad        Vertex Pharma 4 hosts (-12d)"

# ── Cygnus Systems (small but multiple) ──
INV15=$(post_collection "cygnus-prod-1" "Cygnus Systems" "Primary production" "$(hosts_for 6 cyg-prod 1 6)" 4)
echo "  [15] $INV15  cygnus-prod-1       Cygnus        6 hosts (-4d)"

INV16=$(post_collection "cygnus-prod-2" "Cygnus Systems" "Secondary production" "$(hosts_for 5 cyg-prod-2 7 11)" 3)
echo "  [16] $INV16  cygnus-prod-2       Cygnus        5 hosts (-18d)"

# ── failed collection (intentional, all hosts unreachable) ──
H_FAIL='[{"ip":"127.0.0.201","hostname":"failed-01","login":"root","password":"wrong"},
        {"ip":"127.0.0.202","hostname":"failed-02","login":"root","password":"wrong"},
        {"ip":"127.0.0.203","hostname":"failed-03","login":"root","password":"wrong"}]'
INV17=$(post_collection "failed-import-attempt" "Acme Corp" "Wrong creds on import — all hosts unreachable" "$H_FAIL" 3)
echo "  [17] $INV17  failed-import       Acme Corp     0/3 reachable (-1d)"

echo
echo "════════════════════════ STEP 4 ════════════════════════"
echo "Wait for all collections to complete"
for ID in $INV01 $INV02 $INV03 $INV04 $INV05 $INV06 $INV07 $INV08 $INV09 $INV10 $INV11 $INV12 $INV13 $INV14 $INV15 $INV16 $INV17; do
    wait_inv "$ID" &
done
wait
echo "  all 17 collections settled"

echo
echo "════════════════════════ STEP 5 ════════════════════════"
echo "Smart Hands stub — an awaiting-results inventory (operator handed an archive off)"
RESP=$(curl -s -X POST $B/smart-hands/generate \
    -H "Content-Type: application/json" \
    -d '{"name":"customer-acme-q1-handoff","organization":"Acme Corp","description":"Quarterly handoff, awaiting Smart Hands engineer","csv_text":"ip,hostname,login,password\n10.0.99.10,sh-host-01,root,placeholder\n10.0.99.11,sh-host-02,root,placeholder\n10.0.99.12,sh-host-03,root,placeholder\n10.0.99.13,sh-host-04,root,placeholder\n10.0.99.14,sh-host-05,root,placeholder\n"}')
SH_INV=$(echo "$RESP" | $PY -c "import json,sys; print(json.load(sys.stdin).get('inventory_id',''))" 2>/dev/null)
echo "  [SH] $SH_INV  customer-acme-q1-handoff  Smart Hands archive generated"

echo
echo "════════════════════════ STEP 6 ════════════════════════"
echo "Warm PartSurfer cache (5 known-good HPE part numbers)"
for q in "USE839N0CK" "P52562-B21" "865408-B21" "P38997-B21" "R2E09A"; do
    curl -s "$B/tools/partsurfer/search?q=$q" > /dev/null
    echo "  cached: $q"
done

echo
echo "════════════════════════ STEP 7 ════════════════════════"
echo "Redfish tester history (15 probes — mix of success / 401 / wrong-path)"
probe_redfish '{"host":"127.0.0.1","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/","method":"GET"}'
probe_redfish '{"host":"127.0.0.1","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Systems","method":"GET"}'
probe_redfish '{"host":"127.0.0.1","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Systems/1","method":"GET"}'
probe_redfish '{"host":"127.0.0.2","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Chassis","method":"GET"}'
probe_redfish '{"host":"127.0.0.2","username":"administrator","password":"wrong","tls":"off","path":"/redfish/v1/Managers/1","method":"GET"}'
probe_redfish '{"host":"127.0.0.3","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Systems/1/Memory","method":"GET"}'
probe_redfish '{"host":"127.0.0.3","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Systems/1/Processors","method":"GET"}'
probe_redfish '{"host":"127.0.0.4","username":"oper","password":"wrong","tls":"off","path":"/redfish/v1/Systems/1/Storage","method":"GET"}'
probe_redfish '{"host":"127.0.0.5","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Chassis/Node0","method":"GET"}'
probe_redfish '{"host":"127.0.0.6","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Systems/1/EthernetInterfaces","method":"GET"}'
probe_redfish '{"host":"127.0.0.7","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Chassis/1/Power","method":"GET"}'
probe_redfish '{"host":"127.0.0.8","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/Chassis/1/Thermal","method":"GET"}'
probe_redfish '{"host":"127.0.0.9","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/AccountService","method":"GET"}'
probe_redfish '{"host":"127.0.0.10","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/UpdateService","method":"GET"}'
probe_redfish '{"host":"127.0.0.11","username":"root","password":"root_password","tls":"off","path":"/redfish/v1/SessionService","method":"GET"}'
echo "  15 probes stored"

echo
echo "════════════════════════ STEP 8 ════════════════════════"
echo "User settings"
curl -s -X PATCH $B/settings -H "Content-Type: application/json" \
    -d '{"theme":"dark","density":"regular","direction":"console","accent":"#00ff88","locale":"en"}' > /dev/null
echo "  dark / regular / console / mint / en applied"

echo
echo "════════════════════════ STEP 9 ════════════════════════"
echo "Backdate inventories so the dashboard timeline spans 90 days"
kill $APP_PID 2>/dev/null
sleep 2
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>&1 > /dev/null
sleep 1

backdate_sqlite "$INV02" 2
backdate_sqlite "$INV03" 7
backdate_sqlite "$INV04" 14
backdate_sqlite "$INV05" 3
backdate_sqlite "$INV06" 5
backdate_sqlite "$INV07" 30
backdate_sqlite "$INV08" 60
backdate_sqlite "$INV09" 90
backdate_sqlite "$INV10" 10
backdate_sqlite "$INV11" 45
backdate_sqlite "$INV12" 25
backdate_sqlite "$INV13" 8
backdate_sqlite "$INV14" 12
backdate_sqlite "$INV15" 4
backdate_sqlite "$INV16" 18
backdate_sqlite "$INV17" 1

powershell -Command "cmd /c '$APP_DIR\\start.bat --port 8099'" > /tmp/seed_app.log 2>&1 &
APP_PID2=$!
sleep 6
curl -sf $B/health > /dev/null && echo "  app back up after backdate"

echo
echo "════════════════════════ FINAL STATE ════════════════════════"
curl -s $B/inventories | $PY -c "
import json, sys
rows = json.load(sys.stdin)
print(f'inventories: {len(rows)}')
for r in rows:
    age = r.get('created_at', '')[:10]
    print(f\"  {r['status']:<16} {r['servers']:>3}/{r['servers']:<3}  {r['name']:<30}  {r['organization']:<18}  {age}\")
"
echo
curl -s $B/stats/fleet | $PY -c "
import json, sys
d = json.load(sys.stdin)
t = d['totals']
print('fleet totals:')
print(f'  inventories : {t[\"inventories\"]}')
print(f'  servers     : {t[\"servers\"]}')
print(f'  components  : {t[\"components\"]}')
print(f'  avg collect : {t[\"avg_collection_seconds\"]}s')
print()
print('top models:')
for m, n in d['model_distribution'][:8]:
    print(f'  {n:>3}  {m}')
print()
print('iLO firmware mix:')
for f, n in d['ilo_firmware_distribution'][:6]:
    print(f'  {n:>3}  {f}')
"
echo
echo "redfish tester history:"
curl -s $B/tools/redfish-test/history | $PY -c "import json,sys; print(f'  {len(json.load(sys.stdin))} rows')"
echo
echo "partsurfer cache:"
$PY -c "
import sqlite3
c = sqlite3.connect('$APP_DIR/data/hpersist.db')
for k, _, hits in c.execute('SELECT key, fetched_at, hits FROM partsurfer_cache'):
    print(f'  {k:<14} hits={hits}')
c.close()
"

echo
echo "════════════════════════ DONE ════════════════════════"
echo "  → app live at http://127.0.0.1:8099"
echo "  → poke around the dashboard, then when done teardown:"
echo "      docker rm -f \$(docker ps -aq --filter name=hpemu_seed)"
echo "      powershell -Command \"Get-Process python | Stop-Process -Force\""
