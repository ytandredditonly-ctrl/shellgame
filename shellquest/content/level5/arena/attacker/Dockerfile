FROM alpine:3.19
RUN apk add --no-cache openssh-client sshpass
COPY brute.sh /brute.sh
RUN chmod +x /brute.sh
ENTRYPOINT ["/brute.sh"]
