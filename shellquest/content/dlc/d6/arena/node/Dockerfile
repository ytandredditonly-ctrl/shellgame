FROM debian:12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server python3 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -s /bin/bash admin \
 && echo 'admin:password1' | chpasswd \
 && echo 'ARS-HYDRA-IN' > /home/admin/flag.txt \
 && mkdir -p /run/sshd
COPY app.py /opt/app.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 22 8080
CMD ["/entrypoint.sh"]
