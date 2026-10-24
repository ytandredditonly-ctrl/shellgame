# Hydra — онлайн-подбор к службам входа (DLC «Арсенал», d6)

В отличие от John (офлайн по хешам) Hydra стучится в живой сервис. Поэтому на
стороне защиты нужны rate-limit и блокировки.

## Примеры
- SSH: `hydra -L users.txt -P wordlist.txt ssh://loginbox`.
- HTTP POST-форма:
  `hydra -l admin -P wordlist.txt loginbox http-post-form "/login:user=^USER^&pass=^PASS^:F=FAIL"`
  где `F=` — строка-признак неудачи.
- Успех — строка `[22][ssh] host: ... login: ... password: ...`.

## Защита (связка с ур.5)
`fail2ban` банит источник после серии неудач → Hydra упирается (HTTP 429 /
обрывы). Это и есть смысл лимитов.

## Безопасность
Только по арене `loginbox`. Брут чужих сервисов противоправен.
