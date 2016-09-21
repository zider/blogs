# -*- coding:utf-8 -*-

import time
import uuid

import orm

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
    
class User(orm.Model):
    __table__ = 'users'
    # 这种传入函数，只有在真正使用的时候才调用
    # 明明更麻烦，难道更高效？
    id = orm.StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = orm.StringField(ddl='varchar(50)')
    passwd = orm.StringField(ddl='varchar(50)')
    admin = orm.BooleanField()
    name = orm.StringField(ddl='varchar(50)')
    image = orm.StringField(ddl='varchar(500)')
    created_at = orm.FloatField(default=time.time)
    
class Blog(orm.Model):
    __table__ = 'blogs'

    id = orm.StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = orm.StringField(ddl='varchar(50)')
    user_name = orm.StringField(ddl='varchar(50)')
    user_image = orm.StringField(ddl='varchar(500)')
    name = orm.StringField(ddl='varchar(50)')
    summary = orm.StringField(ddl='varchar(200)')
    content = orm.TextField()
    created_at = orm.FloatField(default=time.time)

class Comment(orm.Model):
    __table__ = 'comments'

    id = orm.StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = orm.StringField(ddl='varchar(50)')
    user_id = orm.StringField(ddl='varchar(50)')
    user_name = orm.StringField(ddl='varchar(50)')
    user_image = orm.StringField(ddl='varchar(500)')
    content = orm.TextField()
    created_at = orm.FloatField(default=time.time)