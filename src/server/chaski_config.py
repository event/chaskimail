
import urllib
import socket
import logging
import logging.config

from lxml import etree

from chaski_const import NAMESPACE, CHASKI_PORT, DEFAULT_LOG_LEVEL

__all__ = ['ChaskiConfig']

SIZE_TO_SUFFIX = {'b': 1, 'k': 2**10, 'm': 2**20, \
                  'g': 2**30, 't': 2**40} #should be sufficient :)

def str_to_map(data, dict_sep, pair_sep) :
    result = {}
    tokens = data.split(dict_sep)
    for token in tokens :
        kv = token.split(pair_sep, 2)
        key = kv[0].strip()
        if len(kv) > 1 :
            value = kv[1].strip()
        else :
            value = None
        result[key] = value

    if result.has_key('') :
        del result['']
    return result

def parse_plugin(plugin) :
    def get_by_full_path(path) :
        import_fail = True
        imp_package = path
        while import_fail and len(imp_package) > 0 :
            try:
                p = __import__(imp_package)
            except ImportError :
                imp_package = imp_package[:imp_package.rfind('.')]
            else :
                import_fail = False
        if import_fail :
            raise ImportError('Failed to import plugin %s' % path)
        subpackages = path.split('.')[1:]
        return reduce(lambda x,y: x.__dict__[y], subpackages, p)
        
        
    import_path = plugin.findtext(NAMESPACE + 'path')

    param_str = plugin.findtext(NAMESPACE + 'parameters')
    param_dict = str_to_map(param_str, ',', '=')

    plugin_class = get_by_full_path(import_path)
    return plugin_class(param_dict)

def parse_size(size) :
    size = size.strip()
    suffix = size[-1].lower()
    if SIZE_TO_SUFFIX.has_key(suffix) :
        factor = SIZE_TO_SUFFIX[suffix]
        size = size[:-1]
    else :
        factor = 1
    return int(size) * factor
    

class ChaskiConfig (object):
    __slots__ = ['port', 'maildir', 'max_message_size'\
                 , 'log_conf', 'plugins', 'schema', 'my_name']

    def __init__(self, raw_config) :

        xml_config = etree.XML(raw_config)
        params = {}

        port = xml_config.findtext(NAMESPACE + 'port')
        if port is not None :
            params['port'] = int(port)

        message_size = xml_config.findtext(NAMESPACE + 'message_size')
        if message_size is not None :
            params['max_message_size'] = parse_size(message_size)

        log_conf = xml_config.findtext(NAMESPACE + 'log_conf')
        if log_conf is not None :
            logging.config.fileConfig(log_conf)
        else :
            logging.basicConfig(level=DEFAULT_LOG_LEVEL)

        my_name = xml_config.findtext(NAMESPACE + 'my_name')
        if my_name is not None :
            params['my_name'] = my_name

        schema_uri = xml_config.findtext(NAMESPACE + 'schema_uri')
        if schema_uri is not None :
            params['schema'] = etree.XMLSchema(\
                etree.parse(urllib.urlopen(schema_uri)))

        plugin_xml_conf = xml_config.findall(\
            NAMESPACE + 'plugin_modules/' + NAMESPACE + 'plugin') 
        params['plugins'] = map(parse_plugin, plugin_xml_conf)
        self.from_params(**params)

    def from_params(self, port = CHASKI_PORT
                    , max_message_size = 10*1024*1024 # 10Mb
                    , my_name = socket.gethostname()
                    , schema = None
                    , plugins = []) :
        self.port = port
        self.max_message_size = max_message_size
        self.schema = schema
        self.my_name = my_name
        self.plugins = plugins

        for plugin in plugins :
            plugin.conf = self
    
    def __str__(self) :
        return 'ChaskiConfig:\nport:%d\nsize:%d\nplugins:%s' \
               % (self.port, self.max_message_size\
                  , [x.__class__ for x in self.plugins])
