# -*- coding: : utf-8 -*-

import orm as models

class User(models.Model):
    __table__ = 'users'
    id = models.IntegerField(primary_key=True)
    name = StringField()
    password = StringField()