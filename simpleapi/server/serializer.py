# -*- coding: utf-8 -*-

import re

try:
    from django.core import serializers
    from django.db.models import Model
    from django.db.models.query import QuerySet
    from django.utils.encoding import smart_str, smart_unicode, is_protected_type
    from django.utils import datetime_safe
except ImportError, e:
    # FIXME: dirty hack? how can we prevent that the
    # Client library raises an error if django settings isn't present
    if not 'DJANGO_SETTINGS_MODULE' in str(e):
        raise

__all__ = ('serialize',)

class SerializedObject(object):
    
    def __init__(self, obj, **options):
        self.obj = obj
        self.options = options
    
    def to_python(self):
        if isinstance(self.obj, Model):
            serializer = ModelSerializer(self.obj, **self.options)
        elif isinstance(self.obj, QuerySet):
            serializer = QuerySetSerializer(self.obj, **self.options)
        return serializer.serialize()

def serialize(obj, **options):
    return SerializedObject(
        obj=obj,
        **options
    )

class SerializerList(list):
    def __contains__(self, value):
        for item in self:
            if hasattr(item, 'match'):
                # regular expression
                if item.match(value):
                    return True
            else:
                if item == value:
                    return True
        return False

class Serializer(object):
    def __init__(self, obj, **options):
        self.obj = obj
        self.options = options
        self.fields = SerializerList(options.get('fields', []))
        self.excludes = SerializerList(options.get('excludes', []))
        
        assert isinstance(self.fields, (tuple, list))
        assert isinstance(self.excludes, (tuple, list))

class ModelSerializer(Serializer):

    def serialize(self):
        assert isinstance(self.obj, Model)

        self.result = {}

        for field in self.obj._meta.local_fields:
            if field.serialize:
                if field.rel is None:
                    if (not self.fields or field.attname in self.fields) and \
                        not field.attname in self.excludes:
                        self.handle_field(field)
                else:
                    if (not self.fields or field.attname[:-3] in self.fields) \
                        and not field.attname in self.excludes:
                        self.handle_fk_field(field)
        for field in self.obj._meta.many_to_many:
            if field.serialize:
                if (not self.fields or field.attname in self.fields) \
                    and not field.attname in self.excludes:
                    self.handle_m2m_field(field)
        return self.result

    def handle_field(self, field):
        value = field._get_val_from_obj(self.obj)
        if is_protected_type(value):
            self.result[field.name] = value
        else:
            self.result[field.name] = field.value_to_string(self.obj)

    def handle_fk_field(self, field):
        related = getattr(self.obj, field.name)
        if related is not None:
            if self.use_natural_keys and hasattr(related, 'natural_key'):
                related = related.natural_key()
            else:
                if field.rel.field_name == related._meta.pk.name:
                    # Related to remote object via primary key
                    related = related._get_pk_val()
                else:
                    # Related to remote object via other field
                    related = smart_unicode(getattr(related, field.rel.field_name), strings_only=True)
        self.result[field.name] = related

    def handle_m2m_field(self, field):
        if field.rel.through._meta.auto_created:
            if self.use_natural_keys and hasattr(field.rel.to, 'natural_key'):
                m2m_value = lambda value: value.natural_key()
            else:
                m2m_value = lambda value: smart_unicode(value._get_pk_val(), strings_only=True)
            self.result[field.name] = [m2m_value(related)
                               for related in getattr(self.obj, field.name).iterator()]

class QuerySetSerializer(Serializer):

    def serialize(self):
        assert isinstance(self.obj, QuerySet)

        result = []
        for obj in self.obj:
            model_serializer = ModelSerializer(obj, **self.options)
            result.append(model_serializer.serialize())
        return result