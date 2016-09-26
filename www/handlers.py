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

from aiohttp import web

import markdown2
from apis import APIError, APIValueError, APIResourceNotFoundError, APIPermissionError, Page
from coroweb import get, post
from models import User, Comment, Blog, next_id
from config import configs

_EMAIL = re.compile(r'^[a-z0-9\-\.\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_SHA1 = re.compile(r'^[0-9a-f]{40}$')

COOKIE_NAME = 'zider'
_COOKIE_KEY = configs.session.secret

def user2cookie(user, max_age):
    '''
    通过user生产cookie语句
    '''
    expires = str(int(time.time()+max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)
    
@asyncio.coroutine
def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()
        
def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)
    
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p
        
@get('/')
@asyncio.coroutine
def index(request):
    blogs = (yield from Blog.findAll())
    return {'__template__':'blogs.html',
            'blogs':blogs,
    }
    
@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id)
    comments =yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    if len(comments) > 0:
        for c in comments:
            c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }
    
@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog
    
@get('/api/blogs')
def api_blogs(*, page='1', page_size=5):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, page_index, int(page_size) if (int(page_size) > 1) else 1)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)
    
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }
    
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs',
    }
    
@get('/manage/blogs/edit/{id}')
def manage_edit_blog(id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs',
    }
    
@get('/register')
@asyncio.coroutine
def register():
    return {'__template__': 'register.html'}
    
@get('/signin')
@asyncio.coroutine
def signin():
    return {'__template__': 'signin.html'}
    
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r
    
@get('/test')
@asyncio.coroutine
def test():
    users = yield from User.findAll();
    return {
        '__template__': 'test.html',
        'users': users,
    }

@post('/api/authenticate')
def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid Email')
    if not passwd:
        raise APIValueError('password', 'Invalid Password')
    users = yield from User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not Exist.')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
        
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
    
@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, 
                    user_image=request.__user__.image, name=name.strip(), 
                    summary=summary.strip(), content=content.strip())
    yield from blog.save()
    return blog
    
@post('/api/blogs/delete')
def api_blogs_delete(request, *, id):
    check_admin(request)
    blog = yield from Blog.find(id)
    yield from blog.remove()
    return dict(id=id)
    
@post('/api/users')
def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _SHA1.match(passwd):
        raise APIValueError('password')
    
    users = (yield from User.findAll('email=?',[email]))
    if len(users) > 0:
        raise APIError('register failed,', 'email', 'Email is already used.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, 
                    passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='')
    yield from user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r