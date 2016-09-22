# -*- coding:utf-8 -*-

'''
url handlers

这里面的每一个方法都添加了get或者post的装饰器
装饰器把给每一个方法添加了path和method

本模块在add_routes中被添加
然后对handlers中的每一个方法都add_route(method, path, RequestHandlers(func)(request))
'''

import re
import time
import json
import logging
import hashlib
import base64
import asyncio

from coroweb import get, post
from models import User, Comment, Blog, next_id

@get('/')
@asyncio.coroutine
def index(request):
    users = (yield from User.findAll())
    return {'__template__':'test.html',
            'users':users,
    }