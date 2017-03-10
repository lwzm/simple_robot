#!/usr/bin/env python3

import collections
import threading
import time
import json

import leveldb
import redis

import tornado.gen
import tornado.ioloop
import tornado.options
import tornado.web


class BaseHandler(tornado.web.RequestHandler):
    ldb = leveldb.LevelDB("ldb")
    redis_cli = redis.StrictRedis(unix_socket_path="etc/.redis.sock",
                                  decode_responses=True)

    def set_default_headers(self):
        #self.set_header("Content-Type", "application/octet-stream")
        self.set_header("Content-Type", "text/plain; charset=UTF-8")


class DataHandler(BaseHandler):
    def head(self, key):
        key = key.encode()
        it = self.ldb.RangeIter(key, key, include_value=False, fill_cache=False)
        try:
            next(it)
        except StopIteration:
            raise tornado.web.HTTPError(404)

    def get(self, key):
        key = key.encode()
        try:
            value = self.ldb.Get(key)
        except KeyError:
            raise tornado.web.HTTPError(404)
        #self._write_buffer.append(value)
        self.write(bytes(value))

    def put(self, key):
        key = key.encode()
        value = self.request.body
        self.ldb.Put(key, value)
        info = json.loads(value.decode())
        hosts_found = info.get("hosts_found")
        if hosts_found:
            self.redis_cli.sadd("hosts_found", *hosts_found)


    def delete(self, key):
        self.ldb.Delete(key.encode())


class QueueHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        task = self.redis_cli.lpop("queue")
        if task:
            self.write(task)
        else:
            yield tornado.gen.sleep(1)

    def post(self):
        tasks = self.request.body.split()
        self.redis_cli.lpush("queue", *tasks)


class IterHandler(BaseHandler):
    iterators_cache = {}

    def get(self):
        key_from = self.get_argument("from", None)
        key_to = self.get_argument("to", None)
        key = (key_from, key_to)
        if key not in self.iterators_cache:
            if isinstance(key_from, str):
                key_from = key_from.encode()
            if isinstance(key_to, str):
                key_to = key_to.encode()
            self.iterators_cache[key] = self.ldb.RangeIter(key_from, key_to)
        it = self.iterators_cache[key]
        try:
            k, v = next(it)
        except StopIteration:
            #del self.iterators_cache[key]
            raise tornado.web.HTTPError(404)
        self.write(bytes(k))
        self.write(b'\n')
        self.write(bytes(v))

    def delete(self):
        key_from = self.get_argument("from", None)
        key_to = self.get_argument("to", None)
        key = (key_from, key_to)
        if key in self.iterators_cache:
            del self.iterators_cache[key]
        else:
            raise tornado.web.HTTPError(404)


class MainHandler(BaseHandler):
    def head(self):
        pass

    def get(self):
        self.set_header("Content-Type", "text/plain")
        self.write(self.ldb.GetStats())


application = tornado.web.Application([
    (r"/data/(.*)", DataHandler),
    (r"/queue", QueueHandler),
    (r"/iter", IterHandler),
    (r"/", MainHandler),
])


def main():
    from tornado.options import define, parse_command_line, options
    define("port", 1111, int)
    parse_command_line()
    application.listen(options.port, xheaders=True)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
