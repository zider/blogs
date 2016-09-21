# -*- coding:utf-8 -*-


import functools
import asyncio
import os
import logging
import inspect

from urrlib import parse
from aiohttp import web

from apis import APIError

def get(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator
    
def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator
# 所有没有定义default的关键字参数
def get_required_kw_args(func):
    args = []
    # inspect.signature函数，传入一个函数，返回这个函数所需的参数列表
    params = inspect.signature(func).parameters
    for name, param in params.items():
        # 是关键字参数且没有定义default
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty：
            args.append(name)
    return tuple(args)
# 所有关键字参数
def get_named_kw_args(func):
    args = []
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)
# 是否有关键字参数
def has_named_kw_args(func):
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
# 是否有可变关键字**kw
def has_var_kw_arg(func):
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
# 是否有request参数            
def has_request_arg(func):
    sig = inspect.signature(func)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind in [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD]):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found
    
# 在初始化的时候就传入了参数
# aiohttp的app.route.add_route在调用这个handler时，再把request传入
class RequestHandler(object):
    def __init__(self, app, func):
        self._app = app
        self._func = func
        self._has_request_arg = has_request_arg(func)
        self._has_var_kw_arg = has_var_kw_arg(func)
        self._has_named_kw_arg = has_named_kw_args(func)
        self._named_kw_args = get_named_kw_args(func)
        self._required_kw_args = get_required_kw_args(func)
        
    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_arg or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type')
                ctype = request.content_type.lower()
                if ctype.startswith('application/json'):
                    params = yield from request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('Json body must be object')
                    kw = params
                elif ctype.startswith('application/x-www-form-urlencoded') or ctype.startswith('multipart/form-data'):
                    params = yield from request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # 移除非命名参数
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        # 检查没有default的关键字参数是否已经赋值
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)
            
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))
    
def add_route(app, func):
    # 实际上，web.Application的app，本身就是有app.route.add_route方法的
    # 传入的三个参数，一个是请求的method，一个是页面路径，一个是处理方法
    # 这里在add_route之前，先做相应检查处理
    method = getattr(func, '__method__', None)
    path = getattr(func, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(func))
    if not asyncio.iscoroutinefunction(func) and not inspect.isgeneratorfunction(func):
        func = asyncio.coroutine(func)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.route.add_route(method, path, RequestHandler(app, func))
    
def add_routes(app, module_name):
    n = module_name.rfind('.')
    # 不太了解__import__用法
    # 
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        func = getattr(mod, attr)
        if isinstance(func, types.FunctionType):
            method = getattr(func, '__method__', None)
            path = getattr(func, '__route__', None)
            if method and path:
                add_route(app, func)