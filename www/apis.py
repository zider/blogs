# -*- coding:utf-8 -*-

import json
import logging
import inspect
import functools

class APIError(Exception):
    def __init__(self, error, data='', message=''):
        