#!/usr/bin/env python3

import redis


def main():
    redis_cli = redis.StrictRedis(unix_socket_path="etc/.redis.sock",
                                  decode_responses=True)
    se = set()

    while True:
        try:
            s = input()
        except EOFError:
            break

        if s in se:
            continue
        se.add(s)

        if s.startswith("www."):
            redis_cli.rpush("queue", s)
        else:
            redis_cli.rpush("queue", s, "www." + s)


if __name__ == "__main__":
    main()
