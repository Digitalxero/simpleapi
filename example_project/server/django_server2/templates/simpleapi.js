(function( window, undefined ) {

// Define a local copy of jQuery
var Client = function(namespace, kwargs) {
        // The Client object is actually just the init constructor "enhanced"
        return new Client.fn.init(namespace, kwargs);
    };

Client.fn = Client.prototype = {
    init: function(namespace, kwargs) {
        this.namespace = namespace;
        console.log("Connecting to: " + namespace);
        console.log(kwargs);
        for(var i in kwargs) {
            console.log(i);
            if(i == "transport_type") {
                this.data._output = kwargs[i];
                this.data._input = kwargs[i];
            } else if(i == "wrapper_type") {
                this.data._wrapper = kwargs[i];
                console.log(this.data._wrapper);
            } else {
                this.data["_" + i] = kwargs[i];
            }
        }

        return this;
    },

    // Start with an empty namespace
    namespace: "",
    data: {_call: "",
           _output: "json",
           _input: "json",
           _wrapper: "default",
           _access_key: "",
           _version: "default"},


    // The current version of Client being used
    version: "0.0.1",
    isFunction: function(obj) {
        return toString.call(obj) === "[object Function]";
    },

    isArray: function(obj) {
        return toString.call(obj) === "[object Array]";
    },
    isPlainObject: function(obj) {
        // Must be an Object.
        // Because of IE, we also have to check the presence of the constructor property.
        // Make sure that DOM nodes and window objects don"t pass through, as well
        if(!obj || toString.call(obj) !== "[object Object]" || obj.nodeType || obj.setInterval) {
            return false;
        }

        // Not own constructor property must be Object
        if(obj.constructor
            && !hasOwnProperty.call(obj, "constructor")
            && !hasOwnProperty.call(obj.constructor.prototype, "isPrototypeOf")) {
            return false;
        }

        // Own properties are enumerated firstly, so to speed up,
        // if last one is own, then all properties are own.

        var key;
        for (key in obj) {}

        return key === undefined || hasOwnProperty.call(obj, key);
    },
    isEmptyObject: function(obj) {
        for(var name in obj) {
            return false;
        }
        return true;
    },
    formatters: {
               register: function(name, func, override) {
                    if(Client.formatters[name] === undefined || overide === true) {
                        Client.formatters[name] = func;
                    }
               },
               json: function JSONFormatter() {
                    JSONFormatter.fn = JSONFormatter.prototype = {
                        init: function() {return this;},
                        build: function(value) {
                            return JSON.stringify(value);
                        },
                        kwargs: function(value, action) {
                            if(action === undefined || action == "build") {
                                return this.build(value);
                            } else if(action == "parse") {
                                return this.parse(value);
                            }
                        },
                        parse: function(value) {
                            return JSON.parse(value);
                        }
                    };

                    JSONFormatter.fn.init.prototype = JSONFormatter.fn;

                    return new JSONFormatter.fn.init();
                 },
                 jsonp: function JSONPFormatter() {
                    JSONPFormatter.fn = JSONPFormatter.prototype = {
                        init: function() {return this;},
                        build: function(value) {
                            if(Client.defaults._callack === undefined) {
                                return JSON.stringify(value);
                            } else {
                                return Client.defaults._callack + "(" + JSON.stringify(value) + ")";
                            }
                        },
                        kwargs: function(value, action) {
                            if(action === undefined || action == "build") {
                                return JSON.stringify(value);
                            } else if(action == "parse") {
                                return JSON.parse(value);
                            }
                        },
                        parse: function(value) {
                            return eval(value);
                        }
                    };

                    JSONPFormatter.fn.init.prototype = JSONPFormatter.fn;

                    return new JSONPFormatter.fn.init();
                 }
    },
    wrappers: {
               register: function(name, func, override) {
                    if(Client.wrappers[name] === undefined || overide === true) {
                        Client.wrappers[name] = func;
                    }
               },
               "default": function DefaultWrapper(errors, result) {
                    DefaultWrapper.fn = DefaultWrapper.prototype = {
                        init: function(errors, result) {
                            this.errors = errors;
                            this.result = result;
                        },
                        errors: [],
                        result: "",
                        build: function() {
                            result = {sucess: true,
                                      result: this.result,
                                      errors: []};
                            if(this.errors.length > 0) {
                                result.sucess = false;
                                result.errors = this.errors;
                            }
                            return result;
                        }
                    };

                    DefaultWrapper.fn.init.prototype = DefaultWrapper.fn;

                    return new DefaultWrapper.fn.init(errors, result);
                },
                extjsform: function ExtJSFormWrapper(errors, result) {
                    ExtJSFormWrapper.fn = ExtJSFormWrapper.prototype = {
                        init: function(errors, result) {
                            this.errors = errors;
                            this.result = result;
                        },
                        errors: [],
                        result: "",
                        build: function() {
                            result = {sucess: true};
                            if(this.errors.length > 0) {
                                result.sucess = false;
                                result.errormsg = this.errors[0];
                                result.errors = this.errors[1];
                            } else {
                                result.data = this.result;
                            }
                            return result;
                        }
                    };

                    ExtJSFormWrapper.fn.init.prototype = ExtJSFormWrapper.fn;

                    return new ExtJSFormWrapper.fn.init(errors, result);
                }
    }
};

// Give the init function the Client prototype for later instantiation
Client.fn.init.prototype = Client.fn;

Client.extend = Client.fn.extend = function() {
    // copy reference to target object
    var target = arguments[0] || {}, i = 1, length = arguments.length, deep = false, options, name, src, copy;

    // Handle a deep copy situation
    if ( typeof target === "boolean" ) {
        deep = target;
        target = arguments[1] || {};
        // skip the boolean and the target
        i = 2;
    }

    // Handle case when target is a string or something (possible in deep copy)
    if ( typeof target !== "object" && !Client.isFunction(target) ) {
        target = {};
    }

    // extend Client itself if only one argument is passed
    if ( length === i ) {
        target = this;
        --i;
    }

    for ( ; i < length; i++ ) {
        // Only deal with non-null/undefined values
        if ( (options = arguments[ i ]) != null ) {
            // Extend the base object
            for ( name in options ) {
                src = target[ name ];
                copy = options[ name ];

                // Prevent never-ending loop
                if ( target === copy ) {
                    continue;
                }

                // Recurse if we"re merging object literal values or arrays
                if ( deep && copy && ( Client.isPlainObject(copy) || Client.isArray(copy) ) ) {
                    var clone = src && ( Client.isPlainObject(src) || Client.isArray(src) ) ? src
                        : Client.isArray(copy) ? [] : {};

                    // Never move original objects, clone them
                    target[ name ] = Client.extend( deep, clone, copy );

                // Don"t bring in undefined values
                } else if ( copy !== undefined ) {
                    target[ name ] = copy;
                }
            }
        }
    }

    // Return the modified object
    return target;
};

Client.fn.extend({
    call: function(method, args) {
        if(this.formatters[this.data._output] === undefined) {
            throw "Unknown Formatter";
        }
        var formatter = this.formatters[this.data._output]();
        for(var i in args) {
            args[i] = formatter.kwargs(args[i]);
        }
        var data = Client.extend(this.data, args);
        data._call = method;

        var ret = null;
        var options = {url: this.namespace,
                    async: false,
                    data: data,
                    dataType: 'json',
                    type: 'post',
                    success: function (response, textStatus, XMLHttpRequest) {
                        console.log(textStatus);
                        console.log(response);
                        //response = formatter.parse(response);
                        try {
                            if(response.get("success")) {
                                ret = response.get("result");
                            } else {
                                var errs = "";
                                var errors = response.get("errors");
                                for(var i=0; i<errors.length; i++) {
                                    if(errs == "") {
                                        errs = errors[i];
                                        continue;
                                    }
                                    errs = errs + ". " + errors[i];
                                }
                                throw errs;
                            }
                        } catch(e) {
                            if(response.success) {
                                ret = response.result;
                            } else {
                                var errs = "";
                                for(var i=0; i<response.errors.length; i++) {
                                    if(errs == "") {
                                        errs = response.errors[i];
                                        continue;
                                    }
                                    errs = errs + ". " + response.errors[i];
                                }
                                throw errs;
                            }
                        }
                    }};
        if(data._output == "jsonp") {
            options.jsonp = "_callback"; // needed since simpleapi names his callback-identifier "_callback"
        }

        try {
            jQuery.ajax(options);
        } catch(e) {
            console.error(e);
        }

        if(ret !== null) {
            return ret;
        }
    }
});

// Expose Client to the global object
window.Client = Client;

})(window);