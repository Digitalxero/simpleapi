# -*- coding: utf-8 -*-

import copy
import inspect
import re

from request import Request, RequestException
from response import Response, ResponseException
from namespace import NamespaceException
from feature import __features__, Feature
from formatter import __formatters__
from wrapper import __wrappers__
from utils import glob_list

__all__ = ('Route', )

class RouteException(Exception): pass
class Route(object):
    
    def __init__(self, *namespaces):
        nmap = {}
        
        for namespace in namespaces:
            version = getattr(namespace, '__version__', 'default')
            assert isinstance(version, int) or version == 'default', \
                u'version must be either an integer or not set'
            
            # make sure no version is assigned twice
            assert not nmap.has_key(version), u'version is assigned twice'
            
            # determine public and published functions
            functions = filter(lambda item: '__' not in item[0] and 
                getattr(item[1], 'published', False) == True,
                inspect.getmembers(namespace))
            
            # determine arguments of each function
            functions = dict(functions)
            for function_name, function_method in functions.iteritems():
                # ArgSpec(args=['self', 'a', 'b'], varargs=None, keywords=None, defaults=None)
                raw_args = inspect.getargspec(function_method)
                
                # does the function allows kwargs?
                kwargs_allowed = raw_args[2] is not None
                
                # get all arguments
                all_args = raw_args[0][1:] # exclude `self´
                
                # build a dict of optional arguments
                if raw_args[3] is not None:
                    default_args = zip(
                        raw_args[0][-len(raw_args[3]):],
                        raw_args[3]
                    )
                    default_args = dict(default_args)
                else:
                    default_args = {}
                
                # build a list of obligatory arguments
                obligatory_args = list(set(all_args) - set(default_args.keys()))
                
                # determine constraints for function
                if hasattr(function_method, 'constraints'):
                    constraints = function_method.constraints
                    assert isinstance(constraints, dict) or callable(constraints)
                    
                    if isinstance(constraints, dict):
                        def check_constraint(constraints):
                            def check(namespace, key, value):
                                constraint = constraints.get(key)
                                if not constraint:
                                    return value
                                if hasattr(constraint, 'match'):
                                    if constraint.match(value):
                                        return value
                                    else:
                                        raise ValueError(u'%s does not match constraint')
                                else:
                                    if isinstance(constraint, bool):
                                        return bool(int(value))
                                    else:
                                        return constraint(value)
                            return check
                        
                        constraint_function = check_constraint(constraints)
                    elif callable(constraints):
                        constraint_function = constraints
                else:
                    constraints = None
                    constraint_function = lambda namespace, key, value: value
                
                # determine allowed methods
                if hasattr(function_method, 'methods'):
                    allowed_methods = function_method.methods
                    assert isinstance(allowed_methods, (list, tuple))
                    method_function = lambda method: method in allowed_methods
                else:
                    allowed_methods = None
                    method_function = lambda method: True
                
                functions[function_name] = {
                    'method': function_method,
                    'name': function_name,
                    'args': {
                        'raw': raw_args,
                        'all': all_args,
                        
                        'obligatory': obligatory_args,
                        'defaults': default_args,
                        
                        'kwargs_allowed': kwargs_allowed
                    },
                    'constraints': {
                        'function': constraint_function,
                        'raw': constraints,
                    },
                    'methods': {
                        'function': method_function,
                        'allowed_methods': allowed_methods,
                    }
                }
            
            # configure authentication
            if hasattr(namespace, '__authentication__'):
                authentication = namespace.__authentication__
                if isinstance(authentication, basestring):
                    authentication = lambda namespace, access_key: \
                        namespace.__authentication__ == access_key
            else:
                # grant allow everyone access
                authentication = lambda namespace, access_key: True
            
            # configure ip address based access rights
            if hasattr(namespace, '__ip_restriction__'):
                ip_restriction = namespace.__ip_restriction__
                assert isinstance(ip_restriction, list) or callable(ip_restriction)
                
                if isinstance(ip_restriction, list):
                    # make the ip address list wildcard searchable
                    namespace.__ip_restriction__ = glob_list(namespace.__ip_restriction__)
                    
                    # restrict access to the given ip address list
                    ip_restriction = lambda namespace, ip: ip in namespace.__ip_restriction__
            else:
                # accept every ip address
                ip_restriction = lambda namespace, ip: True
            
            # configure input formatters
            input_formatters = copy.deepcopy(__formatters__)
            if hasattr(namespace, '__input__'):
                allowed_formatters = namespace.__input__
                input_formatters = filter(lambda i: i[0] in allowed_formatters,
                    input_formatters.items())
                input_formatters = dict(input_formatters)
            
            # configure output formatters
            output_formatters = copy.deepcopy(__formatters__)
            if hasattr(namespace, '__output__'):
                allowed_formatters = namespace.__output__
                output_formatters = filter(lambda i: i[0] in allowed_formatters,
                    output_formatters.items())
                output_formatters = dict(output_formatters)
            
            # configure wrappers
            wrappers = copy.deepcopy(__wrappers__)
            if hasattr(namespace, '__wrapper__'):
                allowed_wrapper = namespace.__wrapper__
                wrappers = filter(lambda i: i[0] in allowed_wrapper,
                    wrappers.items())
                wrappers = dict(wrappers)
            
            nmap[version] = {
                'class': namespace,
                'functions': functions,
                'ip_restriction': ip_restriction,
                'authentication': authentication,
                'input_formatters': input_formatters,
                'output_formatters': output_formatters,
                'wrappers': wrappers,
            }
            
            # set up all features
            features = []
            if hasattr(namespace, '__features__'):
                raw_features = namespace.__features__
                for feature in raw_features:
                    assert isinstance(feature, basestring) or issubclass(feature, Feature)
                    if isinstance(feature, basestring):
                        assert feature in __features__.keys()
                        features.append(__features__[feature](nmap[version]))
                    elif issubclass(feature, Feature):
                        features.append(__features__[feature](nmap[version]))

            
            nmap[version]['features'] = features
        
        # if map has no default version, determine namespace with the 
        # highest version 
        if not nmap.has_key('default'):
            nmap['default'] = nmap[max(nmap.keys())]
        
        self.nmap = nmap
    
    def __call__(self, http_request):
        request_items = dict(http_request.REQUEST.items())
        version = request_items.pop('_version', 'default')
        callback = request_items.pop('_callback', None)
        output_formatter = request_items.pop('_output', 'json')
        input_formatter = request_items.pop('_input', 'value')
        wrapper = request_items.pop('_wrapper', 'default')
        mimetype = request_items.pop('_mimetype', None)
        
        input_formatter_instance = None
        output_formatter_instance = None
        wrapper_instance = None
        
        try:
            try:
                version = int(version)
            except (ValueError, TypeError):
                pass
            if not self.nmap.has_key(version):
                raise RouteException(u'Version %s not found (possible: %s)' % \
                    (version, ", ".join(map(lambda i: str(i), self.nmap.keys()))))
            
            namespace = self.nmap[version]
            
            # check input formatter
            if input_formatter not in namespace['input_formatters']: 
                raise RequestException(u'Input formatter not allowed or unknown: %s' % input_formatter)
            
            # get input formatter
            input_formatter_instancec = namespace['input_formatters'][input_formatter](http_request, callback)
            
            # check output formatter
            if output_formatter not in namespace['output_formatters']: 
                raise RequestException(u'Output formatter not allowed or unknown: %s' % output_formatter)
            
            # get output formatter
            output_formatter_instance = namespace['output_formatters'][output_formatter](http_request, callback)
            
            # check wrapper
            if wrapper not in namespace['wrappers']:
                raise RequestException(u'Wrapper unknown or not allowed: %s' % wrapper)
            
            # get wrapper
            wrapper_instance = namespace['wrappers'][wrapper]
            
            request = Request(
                http_request=http_request,
                namespace=namespace,
                input_formatter=input_formatter_instancec,
                output_formatter=output_formatter_instance,
                wrapper=wrapper_instance,
                callback=callback,
                mimetype=mimetype
            )
            response = request.run(request_items)
        except (NamespaceException, RequestException, ResponseException,
                RouteException), e:
            response = Response(
                http_request,
                errors=unicode(e),
                output_formatter=output_formatter_instance,
                wrapper=wrapper_instance,
                mimetype=mimetype
            )
        except:
            raise # TODO handling
        
        http_response = response.build()
        
        return http_response