#!/usr/bin/env python3

import redis


def main():
    redis_cli = redis.StrictRedis(unix_socket_path="etc/.redis.sock",
                                  decode_responses=True)
    while True:
        try:
            s = input()
        except EOFError:
            break
        redis_cli.rpush("queue", s)


if __name__ == "__main__":
    main()
