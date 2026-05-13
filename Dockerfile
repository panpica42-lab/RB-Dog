FROM ubuntu:20.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        libjsoncpp-dev \
        make \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/quadruped_dev_sdk

COPY . .

RUN make clean && make

FROM ubuntu:20.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV DOG_IP=192.168.96.2
ENV DOG_PORT=8080
ENV LISTEN_HOST=0.0.0.0
ENV LISTEN_PORT=9001
ENV WEB_ROOT=/opt/quadruped_dev_sdk/web

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        iproute2 \
        libjsoncpp1 \
        python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/quadruped_dev_sdk

COPY --from=builder /opt/quadruped_dev_sdk /opt/quadruped_dev_sdk
COPY scripts/docker-entrypoint.sh /usr/local/bin/quadruped-entrypoint

RUN chmod +x /usr/local/bin/quadruped-entrypoint

EXPOSE 9001/tcp
EXPOSE 9001/udp

ENTRYPOINT ["quadruped-entrypoint"]
CMD ["ws"]
