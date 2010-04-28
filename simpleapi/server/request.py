# -*- coding: utf-8 -*-

from response import Response
from session import Session
from feature import FeatureContentResponse
from simpleapi.message import formatters

__all__ = ('Request', 'RequestException')

class RequestException(Exception): pass
class Request(object):

    def __init__(self, http_request, namespace, input_formatter,
                 output_formatter, wrapper, callback, mimetype):
        self.http_request = http_request
        self.namespace = namespace
        self.input_formatter = input_formatter
        self.output_formatter = output_formatter
        self.wrapper = wrapper
        self.callback = callback
        self.mimetype = mimetype

        self.session = Session()

    def run(self, request_items):
        # set all required simpleapi arguments
        access_key = request_items.pop('_access_key', None)
        method = request_items.pop('_call', None)
        data = request_items.pop('_data', None)

        # update session
        self.session.request = self.http_request
        self.session.mimetype = self.mimetype
        self.session.callback = self.callback
        self.session.access_key = access_key

        # instantiate namespace
        local_namespace = self.namespace['class'](self)
        self.session.namespace = {
            'nmap': self.namespace,
            'instance': local_namespace
        }
        
        # check the method
        if not method:
            raise RequestException(u'Method must be provided.')

        # check whether method exists
        if not self.namespace['functions'].has_key(method):
            raise RequestException(u'Method %s does not exist.' % method)

        # check authentication
        if not self.namespace['authentication'](local_namespace, access_key):
            raise RequestException(u'Authentication failed.')

        # check ip address
        if not self.namespace['ip_restriction'](local_namespace, \
                                                self.http_request.META.get('REMOTE_ADDR')):
            raise RequestException(u'You are not allowed to access.')

        function = self.namespace['functions'][method]
        self.session.function = function

        # check allowed HTTP methods
        if not function['methods']['function'](self.http_request.method):
            raise RequestException(u'Method not allowed: %s' % self.http_request.method)

        # if data is set, make sure input formatter is not ValueFormatter
        if data:
            if isinstance(self.input_formatter, formatters['value']):
                raise RequestException(u'If you\'re using _data please make ' \
                                        'sure you set _input and _input is not ' \
                                        '\'value\'.')
            try:
                request_items = self.input_formatter.kwargs(data, 'parse')
            except ValueError, e:
                raise RequestException(u'Data couldn\'t be decoded. ' \
                                        'Please check _input and your _data')
            else:
                if not isinstance(request_items, dict):
                    raise RequestException(u'_data must be an array/dictionary')

        # check whether all obligatory arguments are given
        ungiven_obligatory_args = list(set(function['args']['obligatory']) - \
            set(request_items.keys()))
        if ungiven_obligatory_args:
            raise RequestException(u'Obligatory argument(s) missing: %s' % \
                ", ".join(ungiven_obligatory_args))

        # check whether there are more arguments than needed
        if not function['args']['kwargs_allowed']:
            unsued_arguments = list(set(request_items.keys()) - \
                set(function['args']['all']))

            if unsued_arguments:
                raise RequestException(u'Unused arguments: %s' % \
                ", ".join(unsued_arguments))

        # decode incoming variables (only if _data is not set!)
        if not data:
            new_request_items = {}
            for key, value in request_items.items():
                try:
                    new_request_items[str(key)] = self.input_formatter.kwargs(value, 'parse')
                except ValueError, e:
                    raise
                    raise RequestException(u'Value for %s couldn\'t be decoded.' % \
                        key)
            request_items = new_request_items
        else:
            # make sure all keys are strings, not unicodes (for compatibility 
            # issues: Python < 2.6.5)
            new_request_items = {}
            for key, value in request_items.items():
                new_request_items[str(key)] = value
            request_items = new_request_items

        # check constraints
        for key, value in request_items.iteritems():
            try:
                request_items[key] = function['constraints']['function'](
                    local_namespace, key, value)
            except:
                raise RequestException(u'Constraint failed for argument: %s' % key)

        # we're done working on arguments, pass it to the session
        self.session.arguments = request_items

        # call feature: handle_request
        try:
            for feature in self.namespace['features']:
                feature._handle_request(self)
        except FeatureContentResponse, e:
            result = e
        else:
            # make the call
            result = getattr(local_namespace, method)(**request_items)

        # if result is not a Response, create one
        if not isinstance(result, Response):
            response = Response(
                http_request=self.http_request,
                namespace=self.namespace,
                result=result,
                output_formatter=self.output_formatter,
                wrapper=self.wrapper,
                mimetype=self.mimetype,
                session=self.session,
            )
        else:
            response = result

        return response