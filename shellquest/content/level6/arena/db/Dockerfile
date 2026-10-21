FROM alpine:3.19
RUN apk add --no-cache socat
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 5432
ENTRYPOINT ["/entrypoint.sh"]
