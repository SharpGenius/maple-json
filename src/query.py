#!/usr/bin/env python
# -*- coding: utf-8 -*-
# **************************************************************************
# Copyright © 2017 jianglin
# File Name: query.py
# Author: jianglin
# Email: xiyang0807@gmail.com
# Created: 2017-02-04 23:40:02 (CST)
# Last Update:星期六 2017-2-4 23:42:5 (CST)
#          By:
# Description:
# **************************************************************************
from sqlalchemy import or_, and_
from sqlalchemy.orm import Query, joinedload, joinedload_all, load_only
from sqlalchemy.orm.base import _entity_descriptor
from sqlalchemy.util import to_list
from sqlalchemy.sql import operators, extract
from sqlalchemy.ext.declarative import declared_attr


class QueryMixin(Query):
    _underscore_operators = {
        'gt': operators.gt,
        'lte': operators.lt,
        'gte': operators.ge,
        'le': operators.le,
        'contains': operators.contains_op,
        'in': operators.in_op,
        'exact': operators.eq,
        'iexact': operators.ilike_op,
        'startswith': operators.startswith_op,
        'istartswith': lambda c, x: c.ilike(x.replace('%', '%%') + '%'),
        'iendswith': lambda c, x: c.ilike('%' + x.replace('%', '%%')),
        'endswith': operators.endswith_op,
        'isnull': lambda c, x: x and c is not None or c is None,
        'range': operators.between_op,
        'year': lambda c, x: extract('year', c) == x,
        'month': lambda c, x: extract('month', c) == x,
        'day': lambda c, x: extract('day', c) == x
    }

    def filter_by(self, **kwargs):
        return self._filter_or_exclude(False, kwargs)

    def exclude_by(self, **kwargs):
        return self._filter_or_exclude(True, kwargs)

    def select_related(self, *columns, **options):
        depth = options.pop('depth', None)
        if options:
            raise TypeError('Unexpected argument %r' % iter(options).next())
        if depth not in (None, 1):
            raise TypeError('Depth can only be 1 or None currently')
        need_all = depth is None
        columns = list(columns)
        for idx, column in enumerate(columns):
            column = column.replace('__', '.')
            if '.' in column:
                need_all = True
            columns[idx] = column
        func = (need_all and joinedload_all or joinedload)
        return self.options(func(*columns))

    def order_by(self, *args):
        args = list(args)
        joins_needed = []
        for idx, arg in enumerate(args):
            q = self
            if not isinstance(arg, str):
                continue
            if arg[0] in '+-':
                desc = arg[0] == '-'
                arg = arg[1:]
            else:
                desc = False
            q = self
            column = None
            for token in arg.split('__'):
                column = _entity_descriptor(q._joinpoint_zero(), token)
                if column.impl.uses_objects:
                    q = q.join(column)
                    joins_needed.append(column)
                    column = None
            if column is None:
                raise ValueError('Tried to order by table, column expected')
            if desc:
                column = column.desc()
            args[idx] = column

        q = super(QueryMixin, self).order_by(*args)
        for join in joins_needed:
            q = q.join(join)
        return q

    def _filter_or_exclude(self, negate, kwargs):
        q = self

        def negate_if(expr):
            return expr if not negate else ~expr

        column = None

        for arg, value in kwargs.items():
            for token in arg.split('__'):
                if column is None:
                    column = _entity_descriptor(q._joinpoint_zero(), token)
                    if column.impl.uses_objects:
                        q = q.join(column)
                        column = None
                elif token in ['in']:
                    if value == []:
                        value = ['']
                    op = self._underscore_operators[token]
                    q = q.filter(negate_if(op(column, value)))
                    column = None
                elif token in self._underscore_operators:
                    op = self._underscore_operators[token]
                    q = q.filter(negate_if(op(column, *to_list(value))))
                    column = None
                else:
                    raise ValueError('No idea what to do with %r' % token)
            if column is not None:
                q = q.filter(negate_if(column == value))
                column = None
            q = q.reset_joinpoint()
        return q

    def load_only(self, *columns):
        return self.options(load_only(*columns))

    def or_(self, *kwargs):
        return self.filter(or_(*kwargs))

    def and_(self, *kwargs):
        return self.filter(and_(*kwargs))

    def exists(self):
        session = self.session
        return session.query(super(QueryMixin, self).exists()).scalar()
