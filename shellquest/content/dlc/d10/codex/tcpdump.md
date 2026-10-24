# tcpdump — захват трафика из терминала (DLC «Арсенал», d10)

Когда есть только SSH и нет GUI — tcpdump снимает пакеты прямо в консоли.
Терминальный «кузен» Wireshark. Арена `serverbox`.

## Примеры
- `sudo tcpdump -i <iface>` — захват; Ctrl+C → «N packets captured».
- `tcpdump -A port 80` — только порт 80, ASCII-нагрузка (ищи `GET`, токены).
- `tcpdump host <ip>` — трафик с конкретным хостом.
- `tcpdump -w out.pcap` — запись в файл; `tcpdump -r out.pcap` — чтение.

## Безопасность
Только по своему учебному трафику на `serverbox`.
