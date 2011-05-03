
import unittest
import chaski_config
import chaski_plugin
from elementtree.ElementTree import \
     fromstring as xml_fromstr, tostring as xml_tostr

class TestPlugin(chaski_plugin.ChaskiPlugin) :

    def __init__(self, params) :
        self.params = params

    def __eq__(self, other) :
        return self.params == other.params



class ConfigRoutinesTest(unittest.TestCase) :

    def test_str_to_map0(self) :
        data = ' ab = cd ,ba=dc,abcd'
        expects = {'ab': 'cd', 'ba': 'dc', 'abcd': None}
        result = chaski_config.str_to_map(data, ',', '=')
        self.assertEqual(expects, result)

    def test_str_to_map1(self) :
        data = ''
        expects = {}
        result = chaski_config.str_to_map(data, ',', '=')
        self.assertEqual(expects, result)

    def test_str_to_map2(self) :
        data = ',,'
        expects = {}
        result = chaski_config.str_to_map(data, ',', '=')
        self.assertEqual(expects, result)
        
    def test_parse_size0(self) :
        data = '2G'
        expects = 2*1024*1024*1024
        self.assert_(expects == chaski_config.parse_size(data)) 

    def test_parse_size1(self) :
        data = '5m'
        expects = 5*1024*1024
        self.assert_(expects == chaski_config.parse_size(data))

    def test_parse_size2(self) :
        data = '1024 K '
        expects = 1024*1024
        self.assert_(expects == chaski_config.parse_size(data))

    def test_parse_size3(self) :
        data = ' 1024 '
        expects = 1024
        self.assert_(expects == chaski_config.parse_size(data))

    def test_parse_size_bad0(self) :
        data = '2gb'
        self.assertRaises(ValueError, chaski_config.parse_size, data)

    def test_parse_size_bad1(self) :
        data = ''
        self.assertRaises(IndexError, chaski_config.parse_size, data)

    plugin_conf = """<?xml version='1.0' encoding='UTF-8'?>
    <chaski:plugin xmlns:chaski="chaski">
      <chaski:path>chaski_conf_test.TestPlugin</chaski:path>
      <chaski:parameters>
          a=1, b=2, c=3
      </chaski:parameters>
    </chaski:plugin>
    """

    def test_parse_plugin(self) :
        data = xml_fromstr(self.plugin_conf)
        result = chaski_config.parse_plugin(data)
        expect = TestPlugin({'a': '1', 'b': '2', 'c': '3'})
        self.assertEqual(expect, result)


if __name__ == '__main__' :
    unittest.main()
