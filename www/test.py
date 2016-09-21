# -*- coding:utf-8 -*-

'''
test
'''
import asyncio
import sys
import orm
import models

def test(loop):
    # 对相关应用了aiosyncio的方法，必须使用yieldfrom
    # 不然报错 yield from wasn't used with future
    # 不知道怎么回事
    yield from orm.create_pool(loop=loop, user='root', pwd='1990129', db='awesome')
    u = (yield from models.User().findAll())
    print('runing...')
    for i in u:
        print(i)
    #u = models.User(name='yjm', email='yjmin@gmail.com', passwd='123456', image='about:blank')
    #yield from u.save()
    #print(u)
    
loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.close()
if loop.is_closed():
    sys.exit(0)
    