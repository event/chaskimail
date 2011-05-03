"""
Library defining functions for using by chaski clients.
"""
import socket
import select
from lxml.etree import Element, SubElement\
     , tostring as xml_tostr, fromstring as xml_fromstr

DEFAULT_PORT = 4567
RESPONSE_TIMEOUT = 5000
RECEIVE_BUFLEN = 1024
ENCODING = 'UTF-8'
NAMESPACE = '{http://www.some.com/chaski}'

class ChaskiError(Exception) :
    pass

class ProgressListener(object) :
    def on_progress(self, state) :
        pass

PROGRESS_STATES = {1: 'Creating message' \
                   , 2: 'Message created. Sending message' \
                   , 3: 'Sending failed. Exiting...'\
                   , 4: 'Message sent. Waiting for response'\
                   , 5: 'Server response timeout. Exiting...'\
                   , 6: 'Server respnse failed. Exiting...'\
                   , 7: 'Response received successfully'}

dummy_listener = ProgressListener()

def send_message(server_address, credentials, sndr, \
                 rcpnts, secret_rcpnts, subject, chapters, \
                 progress_listener=dummy_listener) :
    """
    sends message to chaski server. Returns None on success
    server_address -> (address, port) or address as string and default port used
    credentials -> (username, password)
    sndr -> sender account name
    rcpnts -> recepient address or list of recepient addresses
    secret_rcpnts -> same as above but for secret recepients
    chapters -> 4-tuple or list of 4-tuples representing chapters.
    progress_listener (optional) -> ProgressListener instance to notify
    Chapter representation is (name, mime-type, encoding, content)
    if encoding is None or empty string then attribute is ommited in xml.
    returns None on success, string error message otherwise
    """
    def make_list(arg) :
        if arg is None or isinstance(arg, list) :
            return arg
        else :
            return [arg]

    rcpnts = make_list(rcpnts)
    secret_rcpnts = make_list(secret_rcpnts)
    chapters = make_list(chapters)
    progress_listener.on_progress(1)
    message = create_message(sndr, rcpnts, secret_rcpnts, subject, chapters)
    return send_messages(server_address, credentials\
                         , [message], progress_listener)

STATUS_OK = 'Success'
def send_messages(server_address, credentials, messages\
                  , progress_listener=dummy_listener) :

    def transform_response(response) :
        return response.findtext(NAMESPACE + 'Status') == STATUS_OK\
               , response.findtext(NAMESPACE + 'Description')

    mail = create_mail(credentials, messages)
    progress_listener.on_progress(2)
    try:
        response = exchange_messages(server_address, mail, progress_listener)
    except ChaskiError, errmes :
        return False, errmes

    return transform_response(response)


def fetch_messages(server_address, credentials, rcpnts, filters={}\
                   , progress_listener=dummy_listener) :

        
    mail = create_fetch_mail(credentials, rcpnts, filters)
    progress_listener.on_progress(2)
    try:
        response = exchange_messages(server_address, mail, progress_listener)
    except ChaskiError, errmes :
        return False, errmes

    return True, tupelize_mail(response)
    

def exchange_messages(server_address, message, progress_listener) :
    s = socket.socket()
    if isinstance(server_address, str) :
        server_address = (server_address, DEFAULT_PORT)
    try:
        s.connect(server_address)
        s.send(xml_tostr(message, encoding = ENCODING))
    except socket.error, (errno, errtext):
        progress_listener.on_progress(3)
        s.close()
        raise ChaskiError('A network error #%d occured: %s' % (errno, errtext))
    progress_listener.on_progress(4)
    p = select.poll()
    p.register(s, select.POLLIN)
    result = p.poll(RESPONSE_TIMEOUT)
    if len(result) == 0 :
        progress_listener.on_progress(5)
        s.close()
        raise ChaskiError('Timed out while waiting for server response')
    mask = result[0][1]
    if mask & select.POLLIN == 0 :
        progress_listener.on_progress(6)
        s.close()
        if mask & select.POLLHUP != 0 :
            errortext = 'Hang up'
        elif mask & select.POLLNVAL != 0 :
            errortext = 'Bad file descriptor'
        else :
            errortext = 'POLLERR'
        raise ChaskiError('Error while waiting for server response: %s' \
                          % (errortext))
    progress_listener.on_progress(7)
    # TODO: must be changed to something capable to handle huge data with progress
    #       notification.
    response = s.recv(RECEIVE_BUFLEN)
    s.close()
    print response
    return xml_fromstr(response)

def create_elem(tag, text, attribs={}) :
    elem = Element(tag, attribs)
    elem.text = text
    return elem


def create_chapter(title, mime, data, encoding=None) :
    root = Element(NAMESPACE + 'Chapter')
    root.append(create_elem(NAMESPACE + 'ChapterName', title))
    root.append(create_elem(NAMESPACE + 'MIMEType', mime))
    
    if encoding is not None :
        attribs = {'encoding': encoding}
    else :
        attribs = {}

    root.append(create_elem(NAMESPACE + 'ChapterContent', data, attribs))
    return root


def create_message(sndr, rcpnts, secret_rcpnts, subject, chapters) :
    root = Element(NAMESPACE + 'Message')
    root.append(create_elem(NAMESPACE + 'From', sndr))
    if rcpnts is not None :
        map(lambda open: \
            root.append(create_elem(NAMESPACE + 'To', open)), rcpnts)
    if secret_rcpnts is not None:
        map(lambda secret: root.append(\
            create_elem(NAMESPACE + 'SecretTo', secret))\
            , secret_rcpnts)

    root.append(create_elem(NAMESPACE + 'Subject', subject))

    map(lambda chap: root.append(create_chapter(*chap)), chapters)

    return root

def create_mail(credentials, messages) :
    root = Element(NAMESPACE + 'Mail')
    creds = Element(NAMESPACE + 'Credentials')
    creds.append(create_elem(NAMESPACE + 'Username', credentials[0]))
    creds.append(create_elem(NAMESPACE + 'Password', credentials[1]))
    root.append(creds)
    map(lambda mes: root.append(mes), messages)

    return root

def tupelize_chapter(chapter) :
    name = chapter.findtext(NAMESPACE + 'ChapterName')
    mime = chapter.findtext(NAMESPACE + 'MIMEType')
    cont = chapter.find(NAMESPACE + 'ChapterContent')
    enc = cont.get('encoding')
    return (name, mime, cont.text, enc)
    
def tupelize_message(message) :
    sender = message.findtext(NAMESPACE + 'From')
    rcpts = map(lambda node: node.text, message.findall(NAMESPACE + 'To'))
    is_secret = message.find(NAMESPACE + 'IsSecret') is not None
    subj = message.findtext(NAMESPACE + 'Subject')
    chapters = map(tupelize_chapter, message.findall(NAMESPACE + 'Chapter'))
    return (sender, rcpts, is_secret, subj, chapters)
    

def tupelize_mail(mail) :
    return map(tupelize_message, mail)
