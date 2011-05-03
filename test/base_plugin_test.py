
import unittest
from chaski_plugin import ChaskiPlugin
from elementtree.ElementTree import fromstring

# the example is borrowed from http://www.w3schools.com/xml/xml_tree.asp
xml_test_text = """<?xml version="1.0" encoding="ISO-8859-1"?>
<note>
<to>Tove</to>
<from>Jani</from>
<heading>Reminder</heading>
<body>Don't forget me this weekend!</body>
</note>
"""
#print xml_test_text
xml_test_etree = fromstring(xml_test_text)

class ChaskiPluginTest(unittest.TestCase) :

    def do_test(self, method, plugin_params) :
        plugin = ChaskiPlugin(plugin_params)
        self.assertTrue(method(plugin, xml_test_etree))

    def test_xpath_exists_true(self) :
        params = {'child_xpath': u'to'}
        self.do_test(ChaskiPlugin.xpath_exists, params)

    def test_xpath_exists_false(self) :
        params = {'child_xpath': u'no/such/path'}
        self.do_test(ChaskiPlugin.xpath_dont_exist, params)

    def test_any_child_text_matches_re_true(self) :
        params = {'child_xpath': u'to'\
                  , 'child_text_re': u'\\w'}
        self.do_test(ChaskiPlugin.any_child_text_matches_re, params)
        

    def test_any_child_text_matches_re_false0(self) : 
        params = {'child_xpath': u'no/such/nude'\
                  , 'child_text_re': u'^$'}
        self.do_test(ChaskiPlugin.any_child_text_dont_match_re, params)

    def test_any_child_text_matches_re_false1(self) : 
        params = {'child_xpath': u'to'
                  , 'child_text_re': u'^$'}
        self.do_test(ChaskiPlugin.any_child_text_dont_match_re, params)

if __name__ == '__main__' :
    unittest.main()
