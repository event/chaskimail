import unittest
import os
from lxml import etree

import chaski_plugin
from chaski_const import PROCESS_OK, PROCESS_FAIL

FETCH_MSG = etree.XML('''<?xml version='1.0' encoding='UTF-8'?>
<chaski:Fetch xmlns:chaski="http://www.some.com/chaski">
  <chaski:Credentials>
    <chaski:Username>event</chaski:Username>
    <chaski:Password>Chaski</chaski:Password>
  </chaski:Credentials>

  <chaski:To>user1</chaski:To>
  <chaski:To>user2</chaski:To>
  <chaski:To>user3</chaski:To>

</chaski:Fetch>
''')

USER_MSG = etree.XML('''<?xml version='1.0' encoding='UTF-8'?>
<chaski:Mail xmlns:chaski="http://www.some.com/chaski">
  <chaski:Credentials>
    <chaski:Username>event</chaski:Username>
    <chaski:Password>Chaski</chaski:Password>
  </chaski:Credentials>
  <chaski:Message>
      <chaski:From>spam</chaski:From>
      <chaski:To>maps@sgge.org</chaski:To>
      <chaski:To>sgge@localhost</chaski:To>
      <chaski:SecretTo>spameggs@sggemaps.org</chaski:SecretTo>
  </chaski:Message>
</chaski:Mail>''')

USER_MSG_AFTER = '''<chaski:Mail xmlns:chaski="http://www.some.com/chaski">
  <chaski:Credentials>
    <chaski:Username>event</chaski:Username>
    <chaski:Password>Chaski</chaski:Password>
  </chaski:Credentials>
  <chaski:Message>
      <chaski:From>spam@localhost</chaski:From>
      <chaski:To>maps@sgge.org</chaski:To>
      <chaski:To>sgge@localhost</chaski:To>
      <chaski:SecretTo>spameggs@sggemaps.org</chaski:SecretTo>
  </chaski:Message>
</chaski:Mail>'''


EXTERNAL_MSG_POS = etree.XML('''<?xml version='1.0' encoding='UTF-8'?>
<chaski:Mail xmlns:chaski="http://www.some.com/chaski">
  <chaski:Message>
      <chaski:From>spam@localhost</chaski:From>
      <chaski:To>maps@sgge.org</chaski:To>
      <chaski:To>sgge@localhost</chaski:To>
      <chaski:SecretTo>spameggs@sggemaps.org</chaski:SecretTo>
  </chaski:Message>
</chaski:Mail>''')

EXTERNAL_MSG_NEG = etree.XML('''<?xml version='1.0' encoding='UTF-8'?>
<chaski:Mail xmlns:chaski="http://www.some.com/chaski">
  <chaski:Message>
      <chaski:From>spam@not.me</chaski:From>
      <chaski:To>maps@sgge.org</chaski:To>
      <chaski:To>sgge@localhost</chaski:To>
      <chaski:SecretTo>spameggs@sggemaps.org</chaski:SecretTo>
  </chaski:Message>
</chaski:Mail>''')

USERCONF = '''event, f4d5d8f67597b3166b042c81a581bfea, user1,user2,user3\n
sgge, f4d5d8f67597b3166b042c81a581bfea, sgge'''

EXTERNAL_FAIL_MES = 'There are senders from third server(s): [\'not.me\']'

class DummyConf(object) :
    __slots__ = ['users', 'my_name']
    
class AuthPluginTest(unittest.TestCase) :
    def setUp(self) :
        userconf = open('user.conf', 'wb')
        userconf.write(USERCONF)
        userconf.close()
        self.plugin = chaski_plugin.SimpleUserAuth(
            {'userconf': 'user.conf'})
        conf = DummyConf()
        conf.my_name = 'localhost'
        self.plugin.conf = conf

    def tearDown(self) :
        os.remove('user.conf')
    
    def test_fetch_auth(self) :
        status, out = self.plugin.process(FETCH_MSG, None)
        self.assertEquals(PROCESS_OK, status)
        self.assertEquals(FETCH_MSG, out)

    def test_user_auth(self) :
        status, out = self.plugin.process(USER_MSG, None)
        self.assertEquals(PROCESS_OK, status)
        self.assertEquals(USER_MSG_AFTER, etree.tostring(out, encoding=unicode))


    def test_ext_auth_pos(self) :
        class FakeSock(object) :
            def getpeername(self):
                return ('127.0.0.1', 1234)
        status, out = self.plugin.process(EXTERNAL_MSG_POS, FakeSock())
        self.assertEquals(PROCESS_OK, status)
        self.assertEquals(EXTERNAL_MSG_POS, out)
         
    def test_ext_auth_neg(self) :
        class FakeSock(object) :
            def getpeername(self):
                return ('127.0.0.1', 1234)
        status, out = self.plugin.process(EXTERNAL_MSG_NEG, FakeSock())
        self.assertEquals(PROCESS_FAIL, status)
        self.assertEquals(EXTERNAL_FAIL_MES, out)



if __name__ == '__main__' :
    unittest.main()
