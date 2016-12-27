#!/usr/bin/env python3

import sys

import redis


def main(key):
    redis_cli = redis.StrictRedis(unix_socket_path="etc/.redis.sock")
    with open(key + ".dump", "rb") as f:
        redis_cli.restore(key, 0, f.read())


if __name__ == "__main__":
    main(sys.argv[1])
