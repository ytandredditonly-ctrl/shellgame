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

echo "== DLC d1 recon-net (nmap targets alpha/beta/gamma) =="
( cd "$ROOT/dlc/d1/arena" && compose -f compose.yaml up -d --build )
sleep 4
probe() { docker exec sq-d1-beta python3 -c "import socket;s=socket.create_connection(('$1',$2),3);
s.sendall(b'GET / HTTP/1.0\r\n\r\n');print(s.recv(256).decode('latin1'))" 2>/dev/null; }
probe alpha 80  | grep -qi 'Server: Apache'      && ok "alpha:80 Apache banner"      || no "alpha:80"
probe beta  2222| grep -qi 'SSH-2.0'             && ok "beta:2222 ssh banner"        || no "beta:2222 ssh"
probe gamma 80  | grep -qi 'nginx/1.18.0'        && ok "gamma:80 nginx/1.18.0"       || no "gamma:80 version"
probe gamma 9000| grep -q 'ARS-NMAP-MAP'         && ok "gamma:9000 flag beacon"      || no "gamma:9000 flag"
( cd "$ROOT/dlc/d1/arena" && compose -f compose.yaml down -v )

# httpget <container> <host> <port> <path>: probe an internal arena from inside
# it, reading the full response (headers + body may arrive in separate segments).
httpget() { docker exec "$1" python3 -c "import socket
s=socket.create_connection(('$2',$3),5)
s.sendall(b'GET $4 HTTP/1.0\r\nHost: $2\r\n\r\n')
buf=b''
while True:
    d=s.recv(4096)
    if not d: break
    buf+=d
print(buf.decode('latin1'))" 2>/dev/null; }

echo "== DLC d3 shopfront (Burp target) =="
( cd "$ROOT/dlc/d3/arena" && compose -f compose.yaml up -d --build )
sleep 3
docker exec sq-d3-shopfront python3 -c "import socket
s=socket.create_connection(('127.0.0.1',80),5)
s.sendall(b'GET /admin HTTP/1.0\r\nCookie: role=admin\r\n\r\n')
buf=b''
while True:
    d=s.recv(4096)
    if not d: break
    buf+=d
print(buf.decode('latin1'))" 2>/dev/null | grep -q 'ARS-BURP-TAMPER' && ok "shopfront /admin role=admin flag" || no "shopfront admin flag"
httpget sq-d3-shopfront 127.0.0.1 80 "/deals?code=ARSENAL50" | grep -q 'DEAL UNLOCKED' && ok "shopfront coupon ARSENAL50" || no "shopfront coupon"
( cd "$ROOT/dlc/d3/arena" && compose -f compose.yaml down -v )

echo "== DLC d4 breach (vsftpd 2.3.4 banner + backdoor flag) =="
( cd "$ROOT/dlc/d4/arena" && compose -f compose.yaml up -d --build )
sleep 3
docker exec sq-d4-breach python3 -c "import socket;s=socket.create_connection(('127.0.0.1',21),4);print(s.recv(64).decode('latin1'))" 2>/dev/null | grep -q '2.3.4' && ok "breach 21 vsFTPd 2.3.4" || no "breach ftp banner"
docker exec sq-d4-breach python3 -c "import socket;s=socket.create_connection(('127.0.0.1',6200),4);print(s.recv(64).decode('latin1'))" 2>/dev/null | grep -q 'ARS-MSF-SHELL' && ok "breach 6200 backdoor flag" || no "breach backdoor flag"
( cd "$ROOT/dlc/d4/arena" && compose -f compose.yaml down -v )

echo "== DLC d7 dbshop (real SQLi, SQLite) =="
( cd "$ROOT/dlc/d7/arena" && compose -f compose.yaml up -d --build )
sleep 3
httpget sq-d7-dbshop 127.0.0.1 80 "/item?id=1" | grep -qi 'Lockpick' && ok "dbshop /item?id=1 row" || no "dbshop base query"
httpget sq-d7-dbshop 127.0.0.1 80 "/item?id=1%20UNION%20SELECT%20secret,secret%20FROM%20vault--" | grep -q 'ARS-SQLI-DUMP' && ok "dbshop UNION injection -> vault flag" || no "dbshop UNION injection"
( cd "$ROOT/dlc/d7/arena" && compose -f compose.yaml down -v )

echo "== DLC d9 webmaze (nikto/gobuster/ffuf target) =="
( cd "$ROOT/dlc/d9/arena" && compose -f compose.yaml up -d --build )
sleep 3
httpget sq-d9-webmaze 127.0.0.1 80 "/" | grep -q 'ArsenalCMS' && ok "webmaze Server: ArsenalCMS" || no "webmaze server banner"
httpget sq-d9-webmaze 127.0.0.1 80 "/secret.bak" | grep -q 'backup-key-7781' && ok "webmaze forgotten .bak token" || no "webmaze .bak"
httpget sq-d9-webmaze 127.0.0.1 80 "/admin/panel?debug=1" | grep -q 'ARS-RECON-HIDDEN' && ok "webmaze hidden endpoint flag" || no "webmaze hidden flag"
( cd "$ROOT/dlc/d9/arena" && compose -f compose.yaml down -v )

echo "== DLC d2 chatter (live-capture token) =="
( cd "$ROOT/dlc/d2/arena" && compose -f compose.yaml up -d --build )
sleep 3
httpget sq-d2-chatter 127.0.0.1 8080 "/feed" | grep -q 'CHATTER-FEED-42' && ok "chatter X-Feed token" || no "chatter token"
( cd "$ROOT/dlc/d2/arena" && compose -f compose.yaml down -v )

echo "== DLC d10 serverbox (tcpdump traffic token/flag) =="
( cd "$ROOT/dlc/d10/arena" && compose -f compose.yaml up -d --build )
sleep 3
httpget sq-d10-serverbox 127.0.0.1 80 "/status" | grep -q 'ARS-TCPD-CATCH' && ok "serverbox token+flag payload" || no "serverbox payload"
( cd "$ROOT/dlc/d10/arena" && compose -f compose.yaml down -v )

echo "== DLC d6 loginbox (real sshd + http form) =="
( cd "$ROOT/dlc/d6/arena" && compose -f compose.yaml up -d --build )
sleep 5
docker exec sq-d6-loginbox python3 -c "import socket;s=socket.create_connection(('127.0.0.1',22),5);print(s.recv(64).decode('latin1'))" 2>/dev/null | grep -q 'SSH-2.0' && ok "loginbox sshd listening :22" || no "loginbox sshd"
docker exec sq-d6-loginbox python3 -c "import urllib.request,urllib.parse;
d=urllib.parse.urlencode({'user':'admin','pass':'letmein'}).encode();
print(urllib.request.urlopen('http://127.0.0.1:8080/login',d).read().decode())" 2>/dev/null | grep -q 'ARS-HYDRA-IN' && ok "loginbox http form admin:letmein flag" || no "loginbox http form"
( cd "$ROOT/dlc/d6/arena" && compose -f compose.yaml down -v )

echo "== DLC finale proving-ground (web + edge banners) =="
( cd "$ROOT/dlc/final/arena" && compose -f compose.yaml up -d --build )
sleep 3
httpget sq-final-web 127.0.0.1 80 "/admin" | grep -q 'provingpass' && ok "proving-ground leaked credential" || no "proving-ground cred"
docker exec sq-final-web python3 -c "import socket;s=socket.create_connection(('edge',7777),4);print(s.recv(64).decode('latin1'))" 2>/dev/null | grep -q 'ARS-PROVING-DONE' && ok "finale edge flag beacon" || no "finale flag beacon"
( cd "$ROOT/dlc/final/arena" && compose -f compose.yaml down -v )

echo
echo "RESULT: $pass passed, $fail failed"
exit $fail
