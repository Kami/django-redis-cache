# -*- coding: utf-8 -*-

import time
import unittest

try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.core.cache import get_cache
from models import Poll, expensive_calculation

# functions/classes for complex data type tests
def f():
    return 42
class C:
    def m(n):
        return 24

class RedisCacheTests(unittest.TestCase):
    """
    A common set of tests derived from Django's own cache tests

    """
    def setUp(self):
        # use DB 16 for testing and hope there isn't any important data :->
        self.cache = get_cache('redis_cache.cache://127.0.0.1:6379?db=15')

    def tearDown(self):
        self.cache.clear()

    def test_simple(self):
        # Simple cache set/get works
        self.cache.set("key", "value")
        self.assertEqual(self.cache.get("key"), "value")

    def test_add(self):
        # A key can be added to a cache
        self.cache.add("addkey1", "value")
        result = self.cache.add("addkey1", "newvalue")
        self.assertEqual(result, False)
        self.assertEqual(self.cache.get("addkey1"), "value")

    def test_non_existent(self):
        # Non-existent cache keys return as None/default
        # get with non-existent keys
        self.assertEqual(self.cache.get("does_not_exist"), None)
        self.assertEqual(self.cache.get("does_not_exist", "bang!"), "bang!")

    def test_get_many(self):
        # Multiple cache keys can be returned using get_many
        self.cache.set('a', 'a')
        self.cache.set('b', 'b')
        self.cache.set('c', 'c')
        self.cache.set('d', 'd')
        self.assertEqual(self.cache.get_many(['a', 'c', 'd']), {'a' : 'a', 'c' : 'c', 'd' : 'd'})
        self.assertEqual(self.cache.get_many(['a', 'b', 'e']), {'a' : 'a', 'b' : 'b'})

    def test_delete(self):
        # Cache keys can be deleted
        self.cache.set("key1", "spam")
        self.cache.set("key2", "eggs")
        self.assertEqual(self.cache.get("key1"), "spam")
        self.cache.delete("key1")
        self.assertEqual(self.cache.get("key1"), None)
        self.assertEqual(self.cache.get("key2"), "eggs")

    def test_has_key(self):
        # The cache can be inspected for cache keys
        self.cache.set("hello1", "goodbye1")
        self.assertEqual(self.cache.has_key("hello1"), True)
        self.assertEqual(self.cache.has_key("goodbye1"), False)

    def test_in(self):
        # The in operator can be used to inspet cache contents
        self.cache.set("hello2", "goodbye2")
        self.assertEqual("hello2" in self.cache, True)
        self.assertEqual("goodbye2" in self.cache, False)

    def test_incr(self):
        # Cache values can be incremented
        self.cache.set('answer', 41)
        self.assertEqual(self.cache.get('answer'), 41)
        self.assertEqual(self.cache.incr('answer'), 42)
        self.assertEqual(self.cache.get('answer'), 42)
        self.assertEqual(self.cache.incr('answer', 10), 52)
        self.assertEqual(self.cache.get('answer'), 52)
        self.assertRaises(ValueError, self.cache.incr, 'does_not_exist')

    def test_decr(self):
        # Cache values can be decremented
        self.cache.set('answer', 43)
        self.assertEqual(self.cache.decr('answer'), 42)
        self.assertEqual(self.cache.get('answer'), 42)
        self.assertEqual(self.cache.decr('answer', 10), 32)
        self.assertEqual(self.cache.get('answer'), 32)
        self.assertRaises(ValueError, self.cache.decr, 'does_not_exist')

    def test_data_types(self):
        # Many different data types can be cached
        stuff = {
            'string'    : 'this is a string',
            'int'       : 42,
            'list'      : [1, 2, 3, 4],
            'tuple'     : (1, 2, 3, 4),
            'dict'      : {'A': 1, 'B' : 2},
            'function'  : f,
            'class'     : C,
        }
        self.cache.set("stuff", stuff)
        self.assertEqual(self.cache.get("stuff"), stuff)

    def test_cache_read_for_model_instance(self):
        # Don't want fields with callable as default to be called on cache read
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        my_poll = Poll.objects.create(question="Well?")
        self.assertEqual(Poll.objects.count(), 1)
        pub_date = my_poll.pub_date
        self.cache.set('question', my_poll)
        cached_poll = self.cache.get('question')
        self.assertEqual(cached_poll.pub_date, pub_date)
        # We only want the default expensive calculation run once
        self.assertEqual(expensive_calculation.num_runs, 1)

    def test_cache_write_for_model_instance_with_deferred(self):
        # Don't want fields with callable as default to be called on cache write
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        Poll.objects.create(question="What?")
        self.assertEqual(expensive_calculation.num_runs, 1)
        defer_qs = Poll.objects.all().defer('question')
        self.assertEqual(defer_qs.count(), 1)
        self.assertEqual(expensive_calculation.num_runs, 1)
        self.cache.set('deferred_queryset', defer_qs)
        # cache set should not re-evaluate default functions
        self.assertEqual(expensive_calculation.num_runs, 1)

    def test_cache_read_for_model_instance_with_deferred(self):
        # Don't want fields with callable as default to be called on cache read
        expensive_calculation.num_runs = 0
        Poll.objects.all().delete()
        Poll.objects.create(question="What?")
        self.assertEqual(expensive_calculation.num_runs, 1)
        defer_qs = Poll.objects.all().defer('question')
        self.assertEqual(defer_qs.count(), 1)
        self.cache.set('deferred_queryset', defer_qs)
        self.assertEqual(expensive_calculation.num_runs, 1)
        runs_before_cache_read = expensive_calculation.num_runs
        self.cache.get('deferred_queryset')
        # We only want the default expensive calculation run on creation and set
        self.assertEqual(expensive_calculation.num_runs, runs_before_cache_read)

    def test_expiration(self):
        # Cache values can be set to expire
        self.cache.set('expire1', 'very quickly', 1)
        self.cache.set('expire2', 'very quickly', 1)
        self.cache.set('expire3', 'very quickly', 1)

        time.sleep(2)
        self.assertEqual(self.cache.get("expire1"), None)

        self.cache.add("expire2", "newvalue")
        self.assertEqual(self.cache.get("expire2"), "newvalue")
        self.assertEqual(self.cache.has_key("expire3"), False)

    def test_set_expiration_timeout_None(self):
        key, value = 'key', 'value'
        self.cache.set(key, value);
        self.assertTrue(self.cache._cache.ttl(key) > 0)

    def test_set_expiration_timeout_0(self):
        key, value = 'key', 'value'
        self.cache.set(key, value);
        self.assertTrue(self.cache._cache.ttl(key) > 0)
        self.cache.expire(key, 0)
        self.assertEqual(self.cache.get(key), value)
        self.assertTrue(self.cache._cache.ttl(key) < 0)

    def test_set_expiration_first_expire_call(self):
        key, value = self.cache.prepare_key('key'), 'value'
        # bypass public set api so we don't set the expiration
        self.cache._cache.set(key, pickle.dumps(value))
        self.cache.expire(key, 1)
        time.sleep(2)
        self.assertEqual(self.cache.get('key'), None)

    def test_set_expiration_mulitple_expire_calls(self):
        key, value = 'key', 'value'
        self.cache.set(key, value, 1)
        time.sleep(2)
        self.assertEqual(self.cache.get('key'), None)
        self.cache.set(key, value, 100)
        self.assertEqual(self.cache.get('key'), value)
        time.sleep(2)
        self.assertEqual(self.cache.get('key'), value)
        self.cache.expire(key, 1)
        time.sleep(2)
        self.assertEqual(self.cache.get('key'), None)

    def test_unicode(self):
        # Unicode values can be cached
        stuff = {
            u'ascii': u'ascii_value',
            u'unicode_ascii': u'Iñtërnâtiônàlizætiøn1',
            u'Iñtërnâtiônàlizætiøn': u'Iñtërnâtiônàlizætiøn2',
            u'ascii': {u'x' : 1 }
        }
        for (key, value) in stuff.items():
            self.cache.set(key, value)
            self.assertEqual(self.cache.get(key), value)

    def test_binary_string(self):
        # Binary strings should be cachable
        from zlib import compress, decompress
        value = 'value_to_be_compressed'
        compressed_value = compress(value)
        self.cache.set('binary1', compressed_value)
        compressed_result = self.cache.get('binary1')
        self.assertEqual(compressed_value, compressed_result)
        self.assertEqual(value, decompress(compressed_result))

    def test_set_many(self):
        # Multiple keys can be set using set_many
        self.cache.set_many({"key1": "spam", "key2": "eggs"})
        self.assertEqual(self.cache.get("key1"), "spam")
        self.assertEqual(self.cache.get("key2"), "eggs")

    def test_set_many_expiration(self):
        # set_many takes a second ``timeout`` parameter
        self.cache.set_many({"key1": "spam", "key2": "eggs"}, 1)
        time.sleep(2)
        self.assertEqual(self.cache.get("key1"), None)
        self.assertEqual(self.cache.get("key2"), None)

    def test_delete_many(self):
        # Multiple keys can be deleted using delete_many
        self.cache.set("key1", "spam")
        self.cache.set("key2", "eggs")
        self.cache.set("key3", "ham")
        self.cache.delete_many(["key1", "key2"])
        self.assertEqual(self.cache.get("key1"), None)
        self.assertEqual(self.cache.get("key2"), None)
        self.assertEqual(self.cache.get("key3"), "ham")

    def test_clear(self):
        # The cache can be emptied using clear
        self.cache.set("key1", "spam")
        self.cache.set("key2", "eggs")
        self.cache.clear()
        self.assertEqual(self.cache.get("key1"), None)
        self.assertEqual(self.cache.get("key2"), None)

    def test_long_timeout(self):
        '''
        Using a timeout greater than 30 days makes memcached think
        it is an absolute expiration timestamp instead of a relative
        offset. Test that we honour this convention. Refs #12399.
        '''
        self.cache.set('key1', 'eggs', 60*60*24*30 + 1) #30 days + 1 second
        self.assertEqual(self.cache.get('key1'), 'eggs')

        self.cache.add('key2', 'ham', 60*60*24*30 + 1)
        self.assertEqual(self.cache.get('key2'), 'ham')

        self.cache.set_many({'key3': 'sausage', 'key4': 'lobster bisque'}, 60*60*24*30 + 1)
        self.assertEqual(self.cache.get('key3'), 'sausage')
        self.assertEqual(self.cache.get('key4'), 'lobster bisque')

if __name__ == '__main__':
    unittest.main()
