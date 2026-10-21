#!/bin/bash
# Build and smoke-test every shellquest Docker arena. Run this once your user
# can reach Docker (see the one-time fix below) and the compose plugin is
# installed. It builds each image, starts it, probes the key behaviour, and
# tears it down. Nothing here is destructive to your system.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)/content"
pass=0; fail=0
ok(){ echo "  PASS: $1"; pass=$((pass+1)); }
no(){ echo "  FAIL: $1"; fail=$((fail+1)); }

compose() { docker compose "$@" 2>/dev/null || docker-compose "$@"; }

echo "== L7 juicebox (vulnerable web app) =="
( cd "$ROOT/level7/arena" && compose -f compose.yaml up -d --build )
sleep 4
IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' sq-juicebox 2>/dev/null)
# juicebox is on an internal net; exec curl from inside
R=$(docker exec sq-juicebox python3 -c "import urllib.request,urllib.parse;
d=urllib.parse.urlencode({'username':'admin','password':\"' OR '1'='1\"}).encode();
print(urllib.request.urlopen('http://127.0.0.1:80/login',d).read().decode())" 2>/dev/null)
echo "$R" | grep -q 'role=admin' && ok "SQLi auth bypass" || no "SQLi auth bypass"
( cd "$ROOT/level7/arena" && compose -f compose.yaml down -v )

echo "== L4 gatekeeper (ssh + web + echo) =="
( cd "$ROOT/level4/arena" && compose -f compose.yaml up -d --build )
sleep 4
docker exec sq-gatekeeper python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8080").read().decode())' 2>/dev/null | grep -q welcome && ok "web welcome page" || no "web welcome"
docker exec sq-gatekeeper sh -c 'echo ping | socat - TCP:localhost:9000' 2>/dev/null | grep -q pong-42 && ok "echo pong-42" || no "echo service"
( cd "$ROOT/level4/arena" && compose -f compose.yaml down -v )

echo "== L6 recon net (web/db/misc) =="
( cd "$ROOT/level6/arena" && compose -f compose.yaml up -d --build )
sleep 4
docker exec sq-web python3 -c 'import urllib.request;print("Server:",urllib.request.urlopen("http://127.0.0.1:80/").headers.get("Server"))' 2>/dev/null | grep -qi nginx && ok "web nginx fingerprint" || no "web fingerprint"
docker exec sq-web python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:80/backup").status)' 2>/dev/null | grep -q 200 && ok "hidden /backup" || no "/backup"
( cd "$ROOT/level6/arena" && compose -f compose.yaml down -v )

echo "== L9 citadel (foothold + privesc) =="
( cd "$ROOT/level9/arena" && compose -f citadel.yaml up -d --build )
sleep 4
docker exec sq-citadel sh -c 'test -f /root/root.txt && grep -q CITADEL-ROOT-FF /root/root.txt' && ok "root flag present" || no "root flag"
docker exec sq-citadel sh -c 'grep -q "svc ALL=(root) NOPASSWD: /usr/bin/find" /etc/sudoers.d/svc' && ok "privesc misconfig present" || no "privesc misconfig"
( cd "$ROOT/level9/arena" && compose -f citadel.yaml down -v )

echo
echo "RESULT: $pass passed, $fail failed"
exit $fail
