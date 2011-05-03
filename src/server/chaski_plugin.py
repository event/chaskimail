"""Basic chaski plugins"""

import re
import os
import md5
import stat
import socket
import copy
import select
from datetime import date
import time
import logging
from lxml import etree

from chaski_const import PROCESS_OK, PROCESS_FAIL, ADDRESS_DELIM\
     , NAMESPACE, CHASKI_PORT, XSD_BOOL_TRUE, XSD_DATE_FORMAT\
     , XPATH_NAMESPACES


EMPTY_MAIL_PATTERN = '''<chaski:Mail xmlns:chaski="urn:chaski:org">
%s</chaski:Mail>'''


class ChaskiPlugin(object) :
    """Base class for all plugins.

    Methods defined:
    xpath_exists(message) -- check if child_xpath attribute defines any nodes
    xpath_doesnt_exist(message) -- reverses the previous
    match_any(message) -- returns True
    match(message) -- used by server to decide whether to call process()
    process(mail, src_sock) -- does actual processing

    Attributes defined:
    conf -- reference to conf structure

    """

    def __init__(self, params) :
        """Take params dict and store as attributes"""
        for k, v in params.items() :
            self.__dict__[k] = v
        self.logger = logging.getLogger(self.__class__.__name__)

    def xpath_exists(self, message) :
        """Checks if at least one child specified by 'child_xpath' exist."""
        return bool(message.getroottree().xpath(\
            self.match_xpath, namespaces=XPATH_NAMESPACES))

    def xpath_doesnt_exist(self, message) :
        """Checks if no children specified by 'child_xpath' exist."""
        return not self.xpath_exists(message)
        
    def match_any(self, message) :
        """Matches any message"""
        return True

    def match(self, message) :
        """Interface method to check if the message 
        should be processed with a plugin. 
        Sample methods could be found above.

        message - an Element(Tree) object containing a message
        
        """
        return False

    def process(self, mail, src_sock) :
        """Interface method containing real processing of message by plugin.
        Should return tuple (status, result) where :
         status - PROCESS_OK or PROCESS_FAIL
         result - if PROCESS_OK then message for futher processing,
                  string error message otherwise.
        
        mail -- an Element(Tree) object containing a mail to process
        src_sock -- socket to mail sender. process() is
                    NOT REQUIRED to send anything over this socket
                    and MUST NOT close it as it used for result message
                    when all plugins finished
        
        """
        pass

class _StoreMail(ChaskiPlugin) :
    """Stores mail to file specified by 'fname' parameter.
    Intended primarely for testing."""
    match = ChaskiPlugin.match_any

    def __init__(self, params) :
        ChaskiPlugin.__init__(self, params)
        self.out_file = file(self.fname, 'wb+')

    def process(self, mail, src_sock) :
        self.out_file.write(etree.tostring(mail))
        self.out_file.flush()
        return PROCESS_OK, mail


class SimpleUserAuth(ChaskiPlugin) :
    """Simple file based authentifiaction plugin

    Check chaski:Credentials (if available) and all recepients
    
    """
    match = ChaskiPlugin.match_any

    def __init__(self, params) :
        def parseusers(data):
            userlines = data.split('\n')
            result = {}
            for line in userlines :
                tokens = [x.strip() for x in line.split(',')]
                if len(tokens) >= 2:
                    result[tokens[0]] = (tokens[1], tokens[2:])
            return result
        def getaccountset(users) :
            result = []
            for v in users.values() :
                result.extend(v[1])
            return set(result)

        ChaskiPlugin.__init__(self, params)
        self.users = parseusers(open(self.userconf).read())
        self.accountset = getaccountset(self.users)
        

    def recepientsok(self, mail) :
        mail_host = ADDRESS_DELIM + self.conf.my_name
        recepients = mail.findall(NAMESPACE + 'Message/' + NAMESPACE + 'To')
        recepient_names = [node.text for node in recepients]
        self.logger.debug('here are recepients: %s', recepient_names)
        local = filter(lambda x: x.endswith(mail_host), recepient_names)
        self.logger.debug('here are local recepients: %s', local)
        local_names = [name[:name.rfind(ADDRESS_DELIM)] for name in local]
        names_set = set(local_names)
        return self.accountset.issuperset(names_set)

    def credsok(self, uname, passwd) :
        self.logger.debug('User %s tries to login', uname)
        if self.users.has_key(uname) : 
            pwd_hash = md5.new(passwd).hexdigest()
            self.logger.debug('providing hash %s', pwd_hash)
            return self.users[uname][0] == pwd_hash
        else :
            return False

    def accountsok(self, mail) :
        accnames = [node.text for node in mail.findall(NAMESPACE + 'To')]
        registred_accnames = set(self.users[mail.findtext(\
                NAMESPACE + 'Credentials/' + NAMESPACE + 'Username')][1])
        self.logger.debug('registred accounts: %s', registred_accnames)
        return set(accnames).issubset(registred_accnames)
        
        
    def usermail_auth(self, mail, uname) :
        passwd = mail.findtext(NAMESPACE + 'Credentials/' \
                                   + NAMESPACE + 'Password')
        if passwd is None :
            passwd = ''
        if not self.credsok(uname, passwd) :
            return PROCESS_FAIL, 'No such user "%s" or wrong password "%s"'\
                   % (uname, password)
        if mail.tag == NAMESPACE + 'Fetch' :
            if not self.accountsok(mail) :
                return PROCESS_FAIL, '''Some requested accounts
                       do not exist or assigned to another user'''
        else :
            if not self.recepientsok(mail) :
                return PROCESS_FAIL, 'Some recepients do not exist'

            senders = mail.findall(NAMESPACE + 'Message/' + NAMESPACE + 'From')
            mail_host = ADDRESS_DELIM + self.conf.my_name
            for sender in senders :
                sender.text = sender.text + mail_host
        return PROCESS_OK, mail


    def external_auth(self, mail, ip) :
        def getdnsinfo(ip) :
            hosts = socket.gethostbyaddr(ip)
            result = hosts[1]
            result.append(hosts[0])
            return result

        senders = [node.text for node \
                   in mail.findall(NAMESPACE + 'Message/' \
                                   + NAMESPACE + 'From')]
        sender_domains = [name[name.rfind(ADDRESS_DELIM)+1:] \
                          for name in senders]
        
        peer_domains = getdnsinfo(ip)
        
        excessive = set(sender_domains).difference(set(peer_domains)) 
        if excessive :
            return PROCESS_FAIL\
                   , 'There are senders from third server(s): %s' \
                   % (list(excessive))
        if not self.recepientsok(mail) :
            return PROCESS_FAIL, 'Some recepients do not exist'
        return PROCESS_OK, mail
        
    def process(self, mail, src_sock) :
        """If credentials exist then uname/password checked 
        and server dns-name added to the rightmost part of all the From's.
        If credentials aren't there then all the From's are checked
        to be from the peer (domainnames checked with DNS)
        In both cases all the local To's are checked for existense.
        
        """
        username = mail.find(NAMESPACE + 'Credentials/' + NAMESPACE + 'Username')
        if username is not None :
            self.logger.debug('Mail from user')
            return self.usermail_auth(mail, username.text)
        else :
            self.logger.debug('Mail from another server')
            return self.external_auth(mail, src_sock.getpeername()[0])
            

class ReceiveMessage(ChaskiPlugin) :
    """Base plugin for saving messages.
    Subclasses should implement:

    store(usernames, message)->None -- store one message for all users
    
    """
    def __init__(self, params) :
        ChaskiPlugin.__init__(self, params)
        self.match_xpath = '/chaski:Mail'
    
    match = ChaskiPlugin.xpath_exists

    def process(self, mail, src_sock) :
        """Process whole chaski mail (chaski:Mail element)"""
        result = PROCESS_OK
        result_mes = None
        mesiter = mail.iter(tag=NAMESPACE + 'Message')
        try:
            while result == PROCESS_OK : 
                result, result_mes =  self.process_a_message(mesiter.next())
        except StopIteration :
            return PROCESS_OK, mail
        except Exception, err_mes:
            return PROCESS_FAIL, err_mes
        else :
            return PROCESS_FAIL, 'bad message: ' + result_mes

    def process_a_message(self, message) :
        """Process one message (chaski:Message element)"""
        def getmyusernames(mailaddrs, myhost) :
            unames = []
            for receiver in mailaddrs :
                user = receiver.text
                if user.endswith(myhost) :
                    unames.append(user[:user.find(ADDRESS_DELIM)])
            return unames
            
        receivers = message.findall(NAMESPACE + 'To')
        secret = message.findall(NAMESPACE + 'SecretTo')
        map(lambda node: message.remove(node), secret)
        myusernames = getmyusernames(receivers, self.conf.my_name)
        mysecrets = getmyusernames(secret, self.conf.my_name)
        myusernames.extend(mysecrets)
        status, out_message = self.store(myusernames, message)
        if status != PROCESS_OK :
            return status, out_message
        subjectnode = message.find(NAMESPACE + 'Subject')
        for node in secret :
            subjectnode.addprevious(node)
        return PROCESS_OK, message
        

    def store(self, usernames, message) :
        """Store message in some storage.

        usernames -- list of strings representing one username each
        message -- message (chaski:Message) as a etree.Element
        returns same as process()

        """
        pass

class ReceiveMessageToPlainFile(ReceiveMessage) :
    """Plugin for storing messages on filesystem.
    It's brother plugin for FetchMessagesFromPlainFile

    User should configure 'base_dir' parameter specifying
    base folder for mail storage. The plugin works in assumption
    that authentification is done by previous plugin(s).
    If user have no directory in 'base_dir' it will be created. 
    If there are more than one recepient than hard link (os.link())
    to original message is created in all other folders
    (so it doesn't metter if the message would be deleted in other folder). 
    
    Plugin parameters:
      base_dir -- root directory for user directories
                  where messages will be stored
    
    """
    def store(self, usernames, message) :
        folders = [self.basedir + os.sep + uname for uname in usernames]
        not_exist = filter(lambda dir: not os.access(dir, os.F_OK), folders)
        for folder in not_exist :
            os.mkdir(folder)
            

        rawdata = etree.tostring(message)
        filename = md5.new(rawdata).hexdigest() + '.xml'
        
        fullname = folders[0] + os.sep + filename
        while os.access(fullname, os.F_OK) :
            filename = '_' + filename;
            fullname = folders[0] + os.sep + filename
        file(fullname, 'wb').write(rawdata)

        for folder in folders[1:] :
            os.link(fullname, folder + os.sep + filename)
        return PROCESS_OK, message
    
class FetchConditions(object) :
    __slots__ = ['onlyheaders', 'maxdate', 'mindate', 'removeafter']

    def __init__(self, onlyheaders = 'false'\
                 , maxdate = None, mindate = None, removeafter = 'false') :
        """arguments are in the same order
        as in chaski.xsd:chaski_fetch_restrictions"""
        
        self.onlyheaders = onlyheaders in XSD_BOOL_TRUE
        self.removeafter = removeafter in XSD_BOOL_TRUE

        if maxdate is None :
            maxdate = date.max
        else :
            maxdate = date.fromtimestamp(time.mktime(\
                time.strptime(maxdate, XSD_DATE_FORMAT)))

        if mindate is None :
            mindate = date.min
        else :
            mindate = date.fromtimestamp(time.mktime(\
                time.strptime(mindate, XSD_DATE_FORMAT)))
            
        self.maxdate = maxdate
        self.mindate = mindate
    
class FetchMessage(ChaskiPlugin) :
    """Base plugin for fetching messages.
    Subclasses should implement:

    fetch(recepients, conditions)->chaski:Mail -- fetch a batch by conditions
    
    """

    def __init__(self, params) :
        ChaskiPlugin.__init__(self, params)
        self.match_xpath = '/chaski:Fetch'

    match = ChaskiPlugin.xpath_exists


    def process(self, mail, src_sock) :
        def parseconditions(conds) :
            result = {}
            result['onlyheaders'] = conds.findtext(NAMESPACE + 'OnlyHeader')
            result['mindate'] = conds.findtext(NAMESPACE + 'MinReceiveDate')
            result['maxdate'] = conds.findtext(NAMESPACE + 'MaxReceiveDate')
            result['removeafter'] = conds.findtext(NAMESPACE + 'RemoveAfterFetch')
            return result
        recepients = [node.text for node in mail.findall(NAMESPACE + 'To')]
        conditions = FetchConditions(**parseconditions(\
            mail.find(NAMESPACE + 'Conditions')))
        result = self.fetch(recepients, conditions)
        self.logger.debug('Sending mail %s', result)
        src_sock.send(result)
        return PROCESS_OK, mail

    def fetch(self, recepients, restr) :
        """Fetch messages by conditions for recepients

        recepients -- list of strings representing e-mail account names
        restr -- FetchRestrions object representing conditions which
                   should be met by message to put it to result
        returns xml string to be sent over network
        
        """
        pass

class FetchMessagesFromPlainFile(FetchMessage) :
    """Plugin for fetching messages from filesystem.
    It's brother plugin for ReceiveMessageToPlainFile

    User should configure 'base_dir' parameter specifying
    base folder for mail storage. The plugin works in assumption
    that authentification is done by previous plugin(s). The file
    with message will be deleted after read. 
    
    Plugin parameters:
      base_dir -- root directory for user directories
                  where messages will be stored
    
    """
    
    def fetch(self, recepients, cond) :
        def fetchheader(fname) :
            wholemail = etree.parse(fname).getroot()
            chapters = wholemail.findall(NAMESPACE + 'Chapter')
            [wholemail.remove(ch) for ch in chapters]
            return etree.tostring(wholemail)

        def fetchwhole(fname) :
            return open(fname).read()
                
        mesfnames = []
        for account in recepients :
            accountdir = ''.join([self.basedir, os.sep, account])
            for fname in os.listdir(accountdir) :
                fullfname = ''.join([accountdir, os.sep, fname])
                modtime = date.fromtimestamp(os.stat(fullfname).st_mtime)
                if cond.mindate <= modtime <= cond.maxdate :
                    mesfnames.append(fullfname)
        self.logger.debug('fetching files: %s', mesfnames)
        if cond.onlyheaders :
            fetchfunc = fetchheader
        else :
            fetchfunc = fetchwhole
        messages = []
        toremove = []
        for f in mesfnames :
            try:
                data = fetchfunc(f)
                messages.append(data)
            except (etree.Error, OSError), errmes :
                self.logger.error(errmes)
            else :
                toremove.append(f)
        
        mail = EMPTY_MAIL_PATTERN % ''.join(messages)
        if cond.removeafter :
            try:
                map(os.remove, toremove)
            except OSError, err :
                self.logger.error(err)
        return mail
        

class SendMessage(ChaskiPlugin) :
    """Plugin for sending message to other servers over network.
    No configuration required."""

    def __init__(self, params) :
        self.port = CHASKI_PORT
        ChaskiPlugin.__init__(self, params)
        self.match_xpath = 'chaski:Credentials'

    match = ChaskiPlugin.xpath_exists

    def process(self, mail, src_sock) :
        def getdesthosts(message) :
            destusernodes = message.findall(NAMESPACE + 'To')
            destusernodes.extend(message.findall(NAMESPACE + 'SecretTo'))
            destusers = [node.text for node in destusernodes]
            desthosts = [user[user.find(ADDRESS_DELIM) + 1:] \
                         for user in destusers]
            return list(set(desthosts))
        
        messages = mail[1:] # take all children except chaski:Credentials
        mes_to_serv = {}
        for message in messages :
            hosts = getdesthosts(message)
            try:
                hosts.remove(self.conf.my_name)
            except ValueError, ve:
                pass
            data = etree.tostring(message)
            print hosts
            for host in hosts :
                if not mes_to_serv.has_key(host) :
                    mes_to_serv[host] = []
                mes_to_serv[host].append(data)

        ### TODO: allow only dedicated chaski:SecretTo to be sent to servers
        ###          i.e. no SecretTo for server1 should be sent to server2
        waitingsockets = select.poll()
        openedconns = 0
        for host, messages in mes_to_serv.iteritems() :
            s = socket.socket()
            try:
                self.logger.debug('Connecting to %s:%d', host, self.port)
                s.connect((host, self.port))
                s.setblocking(False)
                mail = EMPTY_MAIL_PATTERN % ''.join(messages)
                s.send(mail)
            except socket.error, e:
                self.logger.error('Network error occured: %s', e)
                s.close()
            else :
                waitingsockets.register(s, select.POLLOUT)
                openedconns += 1
        while openedconns > 0 :
            finished = waitingsockets.poll()
            self.logger.debug(finished)
            fds = [fin[0] for fin in finished]
            for fd in fds :
                waitingsockets.unregister(fd)
                openedconns -= 1
                try:
                    os.close(fd)
                except OSError:
                    pass
        return PROCESS_OK, mail
            
        
class SizePlugin(ChaskiPlugin) :
    """Plugin that loggs out the size of the message on the INFO level"""
    
    match = ChaskiPlugin.match_any


    def process(self, mail, sock) :
        self.logger.info('Mail size is %d', len(etree.tostring(mail)))
        return PROCESS_OK, mail
