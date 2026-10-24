# Wireshark / tshark — анализ трафика (DLC «Арсенал», d2)

Wireshark показывает, что реально идёт по сети, пакет за пакетом. `tshark` — его
консольный близнец. В этом курсе разбор идёт по готовым дампам (`.pcap`) и по
локальному учебному контейнеру — наружу ничего не уходит.

## Чтение дампа
- `tshark -r sample.pcap` — вывести пакеты из файла.
- `tshark -r sample.pcap | wc -l` — посчитать пакеты.
- `tshark -r f.pcap -Y 'dns'` — дисплей-фильтр: только DNS.
- `tshark -r f.pcap -Y 'http.request.method == POST' -T fields -e http.file_data`
  — тело POST-запросов (ищи `pwd=`).
- `tshark -r f.pcap -Y 'tls.handshake.type == 1'` — TLS ClientHello (хендшейки).
- `tshark -r f.pcap -Y 'tls.handshake.extensions_server_name'
  -T fields -e tls.handshake.extensions_server_name` — домены из SNI.

## Follow TCP stream
В GUI: ПКМ по пакету → Follow → TCP Stream — собирает весь диалог (GET/POST и
ответ). В консоли: `tshark -r f.pcap -z follow,tcp,ascii,0 -q`.

## Безопасность
Снифинг — только по своему учебному трафику. Перехват чужих коммуникаций без
согласия противоправен.
