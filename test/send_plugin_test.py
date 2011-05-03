import unittest
import os
import thread
import socket
from lxml import etree
import time
import logging
import sys

import chaski_plugin
from chaski_const import PROCESS_OK, PROCESS_FAIL

res = None
TEST_PORT = 1456

TEST_MSG = '''<?xml version='1.0' encoding='UTF-8'?>
<chaski:Mail xmlns:chaski="urn:chaski:org">
  <chaski:Credentials>
    <chaski:Username>event</chaski:Username>
    <chaski:Password>Chaski</chaski:Password>
  </chaski:Credentials>
  <chaski:Message>
      <chaski:From>spam</chaski:From>
      <chaski:To>sgge@127.0.0.1</chaski:To>
      <chaski:SecretTo>spameggs@localhost</chaski:SecretTo>
      <chaski:Chapter>
	<chaski:ChapterName>Video</chaski:ChapterName>
	<chaski:MIMEType>video/mpeg</chaski:MIMEType>
	<chaski:ChapterContent encoding='base64'>3s5d1g</chaski:ChapterContent>
      </chaski:Chapter>
  </chaski:Message>
</chaski:Mail>'''

RES_MSG = '''<chaski:Mail xmlns:chaski="urn:chaski:org">
  <chaski:Message xmlns:chaski="urn:chaski:org">
      <chaski:From>spam</chaski:From>
      <chaski:To>sgge@127.0.0.1</chaski:To>
      <chaski:SecretTo>spameggs@localhost</chaski:SecretTo>
      <chaski:Chapter>
	<chaski:ChapterName>Video</chaski:ChapterName>
	<chaski:MIMEType>video/mpeg</chaski:MIMEType>
	<chaski:ChapterContent encoding="base64">3s5d1g</chaski:ChapterContent>
      </chaski:Chapter>
  </chaski:Message>
</chaski:Mail>'''


def listen_and_compare(l, port) :
    l.acquire()
    global res
    s = socket.socket()
    try:
        s.bind(('', port))
        s.listen(10)

        sock, addr = s.accept()
    except socket.error, err :
        print 'Error occured %s' % err
    else :
        data = sock.recv(1024)
        res = data
    finally:
        l.release()
        print 'Releasing the lock'
    

class DummyConf(object) :
    __slots__ = ['users', 'my_name']
    
class SendPluginTest(unittest.TestCase) :
    def setUp(self) :
        self.plugin = chaski_plugin.SendMessage({'port': TEST_PORT})
        conf = DummyConf()
        conf.my_name = 'localhost'
        self.plugin.conf = conf
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    def test_mail_send(self) :
        l = thread.allocate_lock()
        thread.start_new_thread(listen_and_compare, (l, TEST_PORT))
        time.sleep(1)
        print 'Awake'
        status, out = self.plugin.process(etree.XML(TEST_MSG), None)
        self.assertEquals(PROCESS_OK, status)
        print 'lock acquisition'
        l.acquire()
        print 'lock acquired'
        self.assertEquals(RES_MSG.replace(' ', ''), res.replace(' ', ''))
        l.release
        

if __name__ == '__main__' :
    unittest.main()
