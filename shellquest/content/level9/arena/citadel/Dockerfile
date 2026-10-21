FROM debian:stable-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server python3 sudo \
 && rm -rf /var/lib/apt/lists/* && mkdir -p /run/sshd

# Unprivileged foothold account with a weak password (the vulnerable service
# path; searchsploit/exploit discovery is modelled by this weak login).
RUN useradd -m -s /bin/bash svc && echo 'svc:svc123' | chpasswd

# Flags (re-randomised by sq-helperd at arena_up in a real run).
RUN echo 'CITADEL-USER-7A' > /home/svc/user.txt && chown svc:svc /home/svc/user.txt \
 && echo 'CITADEL-ROOT-FF' > /root/root.txt && chmod 600 /root/root.txt

# PRIVESC MISCONFIG (intentional, training): svc can run find as root without a
# password -> `sudo find . -exec /bin/sh \; ` yields a root shell (GTFOBins).
RUN echo 'svc ALL=(root) NOPASSWD: /usr/bin/find' > /etc/sudoers.d/svc \
 && chmod 440 /etc/sudoers.d/svc

# Allow password SSH for the foothold (lab only).
RUN sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
 && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
EXPOSE 22
CMD ["/usr/sbin/sshd","-D","-e"]
