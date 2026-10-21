# chown — владелец и группа файла

Меняет владельца (и группу) файла. Обычно требует sudo.

- `sudo chown user f` — сменить владельца
- `sudo chown user:group f` — владельца и группу
- `sudo chown -R user dir` — рекурсивно

Посмотреть текущего владельца — `ls -l` или `stat`. `man chown`.
