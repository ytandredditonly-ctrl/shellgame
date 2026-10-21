# kill / pkill — остановить процесс

- `kill <PID>` — послать TERM (мягко)
- `kill -9 <PID>` — KILL (жёстко, крайний случай)
- `pkill -f name` — по имени/аргументам

Сначала узнай PID (`ps`/`pgrep`). `man kill`.
