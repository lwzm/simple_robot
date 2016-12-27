#!/usr/bin/env python3

import sys

import redis


def main(key):
    redis_cli = redis.StrictRedis(unix_socket_path="etc/.redis.sock")
    dump = redis_cli.dump(key)
    with open(key + ".dump", "wb") as f:
        f.write(dump)


if __name__ == "__main__":
    main(sys.argv[1])
