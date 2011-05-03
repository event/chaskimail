"""Constant container for chaski server"""
import logging
from lxml.etree import XML

DEFAULT_LOG_LEVEL = logging.DEBUG
class ProcessResult (object):
    __slots__ = ['name']
    def __init__(self, name) :
        self.name = name
    def __str__(self) :
        return self.name
PROCESS_OK = ProcessResult('PROCESS_OK')
PROCESS_FAIL = ProcessResult('PROCESS_FAIL')
DEFAULT_CFG = '/etc/chaski.conf'
RESULT_MESSAGE = '''
<chaski:Result xmlns:chaski="http://www.some.com/chaski"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<chaski:Status>%s</chaski:Status>
<chaski:Description>%s</chaski:Description>
</chaski:Result>
'''
NAMESPACE='{urn:chaski:org}'
XPATH_NAMESPACES = {'chaski': 'urn:chaski:org'}
ADDRESS_DELIM = '@'
CHASKI_PORT=25
XSD_BOOL_TRUE = ['true', '1']
XSD_DATE_FORMAT = '%Y-%m-%d'
