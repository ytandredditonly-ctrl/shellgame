# John the Ripper / Hashcat — офлайн-подбор паролей (DLC «Арсенал», d5)

Пароли хранят хешами. Слабые схемы (быстрый несолёный MD5) ломаются словарём за
секунды; медленные солёные ($6$ sha512crypt, bcrypt) держатся на порядки дольше.

## John
- `john --wordlist=wordlist.txt hashes.txt` — словарная атака.
- `john --show hashes.txt` — показать взломанное (и счётчик).
- `unshadow passwd.sample shadow.sample > h && john --wordlist=wordlist.txt h`.
- `hashid '<hash>'` — опознать алгоритм.

## Hashcat (альтернатива)
- `hashcat -m 0 hashes.txt wordlist.txt` (0 = MD5), `--show`.

## Почему соль и медленность
Соль ломает радужные таблицы; медленный хеш ограничивает перебор. Поэтому
солёный/медленный хеш переживает ту же атаку, под которой падает голый MD5.
