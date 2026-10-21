FROM debian:stable-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server python3 socat ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd /root/.ssh
# The player's public key (from l4-q07) is injected by the helper at setup time
# into /root/.ssh/authorized_keys; here we just prepare the account + flag.
RUN echo 'GATE-4F2A-OPEN' > /root/flag.txt && chmod 600 /root/flag.txt
COPY web.py /opt/web.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
EXPOSE 22 8080 9000
ENTRYPOINT ["/entrypoint.sh"]
