# ss — сокеты и порты

- `ss -tlnp` — слушающие TCP с процессами
- `ss -tunap` — TCP+UDP со всеми
- фильтр: `ss -tlnp | grep 8080`

Замена netstat. `man ss`.
