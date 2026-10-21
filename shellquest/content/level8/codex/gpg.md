# gpg — шифрование и подписи

- `gpg -c file` — симметрично (пароль)
- `gpg -d file.gpg` — расшифровать
- `gpg --verify sig file` — проверить подпись
- для подбора: `gpg2john file.gpg > h; john h`

`man gpg`.
