# -*- coding:utf-8 -*-

import aiomysql
import asyncio
import logging

def log(sql, args=()):
    logging.info('SQL: %s' % sql)
    
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['pwd'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop,
    )
    
    
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs

# insert， update， delete都可以用这个执行
# 因为与select不同， 这三个命令只需要返回结果数        
@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            yield from cur.close()
        except BaseException as e:
            raise
        return affected
        
# 下面开始弄models相关类
# 原文件里，是直接建立的Model和Field类

def create_args_string(num):
    L = []
    for i in range(num):
        L.append('?')
    return ', '.join(L)
    
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
        
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)
        
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)
        
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)
        
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)
        
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)
        
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
            
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            # 对attrs中的field取出来重新摆放,建立mapping
            # 分两部分，一个是主键，一个是主键外的其他属性
            if isinstance(v, Field):
                logging.info(' found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise StandardError('Duplicate primary key is found at %s' % k)
                    else:
                        primaryKey = k
                else:
                    # fields中只保存了属性名
                    fields.append(k)
        # 检查表中是否包含primaryKey
        if not primaryKey:
            raise StandardError('Primary Key not found.')
            
        # 将原本直接存于attrs(类的属性)中的field删除
        # 这样类的相关field属性不存在于类的属性列表，而是存在于mappings中
        # 别弄错了，mappings并不是原有的属性，而是自己声明的属性
        # 因此相关的mappings操作会在Model类中的相关方法执行，不影响到类的外部
        for k in mappings.keys():
            attrs.pop(k)
        # 例如，f是'abc',输出的是`abc`
        # python3取消了`， 这里用这个是为了输出sql语句
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings
        attrs['__table__'] == tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        # 就是一个选择tablename中所有属性的select语句
        # 因为主键和其他属性分开了，需要注意
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        # insert into `User`(`name`, `age`, `id`) values(?, ?, ?)
        # 但是主键不是自增嘛？
        attrs['__insert__'] = 'insert into `%s`(%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, 
                                ', '.join(map(lambda i: '`%s`=?' % (mappings.get(i).name or i), fields)),
                                primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
            
        return type.__new__(cls, name, bases, attrs)
        
class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
    
    # 这里的get,set只是为了方便
    # 因为父类是dict,所以只有m['name']这样的用法，不能m.name
    # 现在重写了get,set之后才可以用m.name
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r'"Model" object has no attribute "%s"' % key)
            
    def __setattr__(self, key, value):
        try:
            self[key] = value
        except Exception:
            pass
        
    def getValue(self, key):
        # getattr，如果没有该属性或属性不存在，返回第三个参数
        return getattr(self, key, None)
        
    # 那么，这个意思是说，在field中，始终没有存放数据的值，最多最多，存放了默认值
    # 当我没有定义数据内容时，可以通过特定的field获取相应的默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            # 看有没有对这个key设定默认值
            if field.default is not None:
                # 这个默认值是数据还是函数返回值
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' %(key, str(value)))
                setattr(self, key, value)
        return value
        
    # attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        sql = [cls.__select__]
        # 回头熟悉下sql语句去
        # select * from User where id=2
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
            
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.append(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]
        
    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key. '
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        print(self.__primary_key__)
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)