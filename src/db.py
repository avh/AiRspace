# (c)2018, Arthur van Hoff
# Redis database wrapper

import redis, json, datetime, dateutil.parser

#
# json
#

def unpack_json(value):
    return json.loads(value) if value is not None else None

def pack_json(value):
    return json.dumps(value).encode('utf-8')

#
# timestamps
#

def get_timestamp_value(value):
    if isinstance(value, str):
        value = dateutil.parser.parse(value)
    if isinstance(value, datetime.datetime):
        value = value.timestamp()
    return value

def get_timestamp_key(value):
    return datetime.datetime.utcfromtimestamp(value).isoformat() + "Z"

#
# Redis database
#

class Database:
    def __init__(self, name, host="127.0.0.1", port=6379, password=None):
        self.name = name
        self.redis = redis.Redis(host=host, port=port, password=password)

    def hash_table(self, name):
        return HashTable(self, name)

    def time_table(self, name):
        return TimeTable(self, name)

    def geo_table(self, name):
        return GeoTable(self, name)

#
# Hashtable, maps keys to values.
# Keys are prefixed by the table name.
#

class HashTable:
    def __init__(self, db, name):
        self.db = db
        self.redis = db.redis
        self.name = name
        self.prefix = db.name + ":hashtab:" + name + ":"

    def get(self, key):
        return unpack_json(self.redis.get(self.prefix + key))

    def set(self, key, val):
        if val is None:
            self.delete(key)
        else:
            self.redis.set(self.prefix + key, pack_json(val))

    def keys(self, pattern="*"):
        return [key[len(self.prefix):] for key in self.redis.keys(self.prefix + pattern)]

    def all(self, pattern="*", count=100):
        pattern = self.prefix + pattern
        offset = 0
        while True:
            offset, keys = self.redis.scan(offset, match=pattern, count=count)
            for key in keys:
                yield unpack_json(self.redis.get(key))
            if offset == 0:
                break

    def count(self, pattern="*"):
        return len(self.keys(pattern))

    def delete(self, key):
        self.redis.delete(self.prefix + key)

    def clear(self, pattern="*"):
        keys = list(self.redis.keys(self.prefix + pattern))
        if len(keys) > 0:
            self.redis.delete(*keys)

#
# Timeline, UTC time ordered set
#

class TimeTable:
    def __init__(self, db, name):
        self.db = db
        self.redis = db.redis
        self.name = name
        self.list_name = db.name + ":timelist:" + name
        self.hash_name = db.name + ":timehash:" + name

    def set(self, utc, value):
        if value is None:
            self.delete(utc)
        else:
            score = get_timestamp_value(utc)
            key = get_timestamp_key(score)
            self.redis.zadd(self.list_name, key, score)
            self.redis.hset(self.hash_name, key, pack_json(value))

    def get(self, utc):
        score = get_timestamp_value(utc)
        key = get_timestamp_key(score)
        return unpack_json(self.redis.hget(self.hash_name, key))

    def find(self, from_utc=float("-inf"), to_utc=float("inf")):
        from_score = get_timestamp_value(from_utc)
        to_score = get_timestamp_value(to_utc)
        for key, score in self.redis.zrangebyscore(self.list_name, from_score, to_score, withscores=True):
            yield unpack_json(self.redis.hget(self.hash_name, key))

    def all(self, count=100):
        offset = 0
        while True:
            offset, results = self.redis.zscan(self.list_name, offset, count=count)
            for key, score in results:
                yield unpack_json(self.redis.hget(self.hash_name, key))
            if offset == 0:
                break

    def count(self):
        return self.redis.zcard(self.list_name)

    def delete(self, utc):
        score = get_timestamp_value(utc)
        key = get_timestamp_key(score)
        self.redis.hdel(self.hash_name, key)
        self.redis.zremrangebyscore(self.list_name, score, score)

    def clear(self):
        self.redis.hdel(self.hash_name, self.redis.hgetall(self.hash_name))
        self.redis.zremrangebyrank(self.list_name, 0, -1)

#
# Geography, store (lonlat, key, value) triples
# lookup values near a lonlat
#

class GeoTable:
    def __init__(self, db, name):
        self.db = db
        self.redis = db.redis
        self.name = name
        self.list_name = db.name + ":geolist:" + name
        self.hash_name = db.name + ":geohash:" + name

    def set(self, lonlat, key, value):
        if value is None:
            self.delete(key)
        else:
            self.redis.geoadd(self.list_name, lonlat[0], lonlat[1], key)
            self.redis.hset(self.hash_name, key, pack_json(value))

    def get(self, key):
        return unpack_json(self.redis.hget(self.hash_name, key))

    def find(self, lonlat, radius=float('inf'), unit='m', count=None):
        results = self.redis.georadius(self.list_name, lonlat[0], lonlat[1], radius, unit=unit, sort='ASC', count=count)
        for key in results:
            yield unpack_json(self.redis.hget(self.hash_name, key))

    def all(self, count=100):
        offset = 0
        while True:
            offset, results = self.redis.zscan(self.list_name, offset, count=count)
            for key, score in results:
                yield unpack_json(self.redis.hget(self.hash_name, key))
            if offset == 0:
                break

    def count(self):
        return self.redis.zcard(self.list_name)

    def delete(self, key):
        self.redis.zrem(self.list_name, self.redis.geohash(self.list_name, key))
        self.redis.hdel(self.hash_name, key)

    def clear(self):
        self.redis.hdel(self.hash_name, self.redis.hgetall(self.hash_name))
        self.redis.zremrangebyrank(self.list_name, 0, -1)

#
# Testing
#

if False:
    db = Database("hash_test")
    people = db.hash_table("people")
    people.set("arthur", [1,2,3, "4", True])
    people.set("marleen", ["flowers", ["trees"], 1.23])
    print("arthur", people.get("arthur"))
    print("marleen", people.get("marleen"))
    print("count", people.count())
    print("keys", list(people.keys()))
    print("values", list(people.all()))
    people.delete("marleen")
    print("count", people.count())
    print("keys", list(people.keys()))
    print("values", list(people.all()))
    people.clear()
    print("count", people.count())
    print("values", list(people.all()))

if False:
    db = Database("time_test")
    now = datetime.datetime.utcnow()
    print("now", now)
    val = get_timestamp_value(now)
    print("val", val, type(val))
    key = get_timestamp_key(val)
    print("key", key, type(key))

    then = get_timestamp_key(val-1)
    print("thn", then, type(then))
    val = get_timestamp_value(then)
    print("val", val, type(val))

    tm = db.time_table("dates")
    tm.clear()
    print("count", tm.count())
    tm.set(now, "FOOBAR")
    print("ADD", then)
    tm.set(then, "BIZZAR")
    tm.set(then, "ZANZIBAR")
    print("get", tm.get(now))
    print(list(tm.all()))
    print(list(tm.find()))
    print("count", tm.count())
    tm.delete(then)
    print(list(tm.all()))
    print("count", tm.count())

if False:
    db = Database("geo_test")
    geo = db.geo_table("place")
    geo.clear()

    ll1 = (-122.00, 37.18)
    geo.set(ll1, "San Jose", ["San Jose", ll1])
    ll2 = (-122.25, 37.25)
    geo.set(ll2, "Palo Alto", ["Palo Alto", ll2])
    ll2 = (-122.25, 37.25)
    geo.set(ll2, "KPAO", ["KPAO", ll2])
    ll3 = (-122.45, 37.75)
    geo.set(ll3, "San Francisco", ["San Francisco", ll3])
    print("near ll1", ll1, list(geo.find(ll1)))
    print("near ll2", ll2, list(geo.find(ll2)))
    print("near ll3", ll3, list(geo.find(ll3)))
    print("near ll3", ll3, list(geo.find(ll3, count=2)))
    print("all", list(geo.all()))
