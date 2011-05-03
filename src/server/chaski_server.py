#!/usr/bin/env python

"""Chaski (XML-based mail protocol) server implementation

Usage: chaski.py [-c configfile]
"""

import os
import sys
import thread
import select
import socket
import array
from getopt import getopt
import logging
from lxml import etree

from chaski_config import ChaskiConfig
from chaski_const import DEFAULT_CFG, PROCESS_FAIL, PROCESS_OK, RESULT_MESSAGE


class SockWrapper(object) :
    """A socket wrapper implementing read amount limitation and read() method"""
    
    def __init__(self, sock, max_size) :
        self.s = sock
        self.max_size = max_size
        self.current = 0

    def read(self, size=256) :
        """Read at most 'size' data from socket raising MemoryError
        if overall data read exceeds max_size

        """
        if (self.current >= self.max_size) :
            raise MemoryError('Read to much data %d/%d' \
                              % (self.current, self.max_size))
        data = self.s.recv(size)
        self.current += len(data)
        return data


def fetch_message(sock, max_message_len, schema) :
    w = SockWrapper(sock, max_message_len)
    context = etree.iterparse(w, events=("start", "end"), schema=schema)
    act, root_elem = context.next()
    elem = None
    while elem != root_elem:
        act, elem = context.next()
    return root_elem

def get_success_response(descriprion_text='Success') :
    return RESULT_MESSAGE % ('Success', descriprion_text)

def get_fail_response(descriprion_text) :
    return RESULT_MESSAGE % ('Fail', descriprion_text)

def send_mes_and_close(sock, mes) :
    try:
        sock.send(mes)
    except socket.error :
        pass
    finally:
        try:
            sock.close()
        except socket.error :
            pass

def run_plugins(plugins, message, sock, logger) :
    if len(plugins) > 0 :
        head = plugins[0]
        logger.debug('running plugin %s', head.__class__)
        status, out_message = head.process(message, sock)
        if status == PROCESS_OK :
            return run_plugins(plugins[1:], out_message, sock, logger)
        else :
            send_mes_and_close(sock, get_fail_response(out_message))
            logger.info('%s plugin refused message with status %s: %s'\
                     , head, status, out_message)
            if logger.getEffectiveLevel() <= logging.DEBUG :
                logger.debug('on message %s', etree.tostring(message))
            return False
    else :
        send_mes_and_close(sock, get_success_response())
        return True

def process_message(connection, logger, conf) :
    """Process one chaski message.

    connection -- result of socket.accept()
    logger -- an open logger class
    conf -- ChaskiConfig instance
    returns None
    
    """

    sock, address_info = connection
    logger.debug('Starting message processing from %s:%d', *address_info)
    try:
        message = fetch_message(sock, conf.max_message_size, conf.schema)
    except Exception, ex :
        logger.info('Failed to fetch message from %s. Reason: %s'
                  , address_info[0], ex)
        send_mes_and_close(sock, get_fail_response('Bad xml: %s' % ex))
    else :
        # these 2 actions could be pipelined 
        # i.e. run match()es fully parallel and run process()es upon
        # match() end if possible
        actual_plugins = filter(lambda plugin: plugin.match(message) \
                                , conf.plugins)
        run_plugins(actual_plugins, message, sock, logger)
    logger.debug('Message processing finished')

        
def demonize() :
    """Demonize current process"""
    pass

def exit_gently():
    """Exit from application waiting all threads to finish"""
    sys.exit()

def init_serv_sock(portnum, listen_backlog) :
    """Init listening TCP socket"""
    s = socket.socket()
    s.bind(('', portnum)) # INADDR_ANY
    s.listen(listen_backlog)
    return s

def get_config(filename) :
    return ChaskiConfig(file(filename).read())

# here routines are finished and real code starts
OPTION_STRING = 'c:'
USAGE = 'Usage:  %s [-c <configfile>]' % (sys.argv[0])

if len(sys.argv) > 1 :
    try:
        result = getopt(sys.argv[1:], OPTION_STRING)
        config_file = result[0][0][1]
    except IndexError :
        print USAGE
        sys.exit(1)
else :
    config_file = DEFAULT_CFG


print 'fetch configuration from file %s' % config_file
conf = get_config(config_file)
print conf
logger = logging.getLogger('chaski_server')

demonize()

logger.info('Creating server socket on port %d', conf.port)
serv_sock = init_serv_sock(conf.port, 10)
poller = select.poll()
poller.register(serv_sock)
logger.info('Start listening');

ERROR_MASK = select.POLLHUP | select.POLLNVAL | select.POLLERR
while True :
    poll_res = poller.poll()
    # poll returns list of (fd, bitmask)
    res_mask = poll_res[0][1]
    if res_mask & ERROR_MASK :
        logger.error('An error occured while waiting for connection.'\
                  + ' Error mask: %x', res_mask)
        exit_gently()
    thread.start_new_thread(process_message, (serv_sock.accept(), logger, conf))
