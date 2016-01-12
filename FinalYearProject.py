#!/usr/bin/python


import os,sys
sys.path.insert(0, os.getcwd())
#twistd work around to be able import modules from current directory

from ivrlib import *

import logging
import logging.handlers

from twisted.enterprise import adbapi
from twisted.internet.protocol import Protocol

import MySQLdb,MySQLdb.cursors
import httplib
import datetime

config = MyConfigParser()
config.read("/opt/lectureInfo/config.conf")

soundsdir = config.get("paths", "sounds", "lectures/")

smshost = config.get("sms", "host")
smsdb = config.get("sms", "db")
smsuser = config.get("sms", "user")
smspasswd = config.get("sms","passwd")


ltime=datetime.datetime.now().strftime("%H:%M:%S")
lday= datetime.datetime.now().strftime("%A")

class Lecture(ivrlib):


    def __init__(self, agi):
        """constructor for class Lecture"""
        self.agi = agi
        self.agi.status = "NEW"
        ivrlib.__init__(self)
        self.initLogger()
        self.agi.onClose().addErrback(self.onHangup) #register a callback to clean up on Hangup.
        self.dbtries = 0
        self.times = None
        self.welcome()

    def welcome(self):
        df = self.agi.streamFile(soundsdir+'welcome')
        df.addCallbacks(self.language)


    def language(self, agi):
        self.lang = "english" # set a language to the channel for streaming audio.
        self.log.info("Caller chose english")
        self.agi.execute('Set', 'CHANNEL(language)=en').addCallbacks(self.mainMenu)

    def mainMenu(self, option):
        return LectureInfo(self.agi, self.uniqueid)

    def onHangup(self, reason):
        self.log.debug("Call hungup cleaning up")
        self.agi.incall = False
        self.dbtries =0
class beginBodyCollection(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10
        self.display = None

    def dataReceived(self, bytes):
        """Called whenever data is received.

        Use this method to translate to a higher-level message.  Usually, some
        callback will be made upon the receipt of each complete protocol
        message.

        @param data: a string of indeterminate length.  Please keep in mind
            that you will probably need to buffer some data, as partial
            (or multiple) protocol messages may be received!  I recommend
            that unit tests for protocols call through to this method with
            differing chunk sizes, down to one byte at a time.
        """
        if self.remaining:
            self.display = bytes[:self.remaining]
            self.remaining -= len(display)



    def connectionLost(self, reason):
        """Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed.

        @type reason: L{twisted.python.failure.Failure}
        """
        self.finished.callback(self.display)

class LectureInfo(ivrlib):


    def __init__(self, agi, uniqueid):
        """constructor for class LectureInfo.
        The self parameter refers to the instance of the object."""
        self.agi = agi
        self.agi.pinconfirm = False
        self.agi.crmcompno = "None"
        self.agi.responsecode = "None"
        self.agi.contact = "None"
        self.uniqueid = uniqueid
        self.URLflag = False
        ivrlib.__init__(self)
        self.initLogger()
        self.getLecture()
        #self.service()

    def getLecture(self):
        """calculate day and time"""
        # ltime=datetime.datetime.now().strftime("%H:%M:%S")
        # lday= datetime.datetime.now().strftime("%A")
        # log.debug (str(lday))
        # print lday
        # print ltime
        if str(lday)=="Sunday":
            df = self.agi.streamFile(soundsdir+'holiday')
            df.addCallback(self.hangup)
        if str(lday) == ["Monday", "Saturday"]:
            df = self.agi.streamFile(soundsdir+'project')
            df.addCallback(self.hangup)
        else:
            x = """SELECT filename from %s WHERE start_time <= '%s' AND end_time >= '%s'""" % (lday,str(ltime),str(ltime))
            log.debug (x)
            sql = "SELECT filename from %s WHERE start_time <= %s AND end_time >= %s"
            #df = self.runQuery(dbpool,sql,(lday,str(ltime),str(ltime)))
            df = self.runQuery(dbpool,x)
            df.addCallback(self.playFile)

    def sendMessage(self):
        def timepass(res):
            print "data base insert"
        def checkLost(res):
            print "error"
        messagecounter = self.messagecheck()
        if (messagecounter == 0):
            sqlquery="INSERT into CallLog (CallerId,UniqueId,Date,MessageStatus) VALUES(%s,%s,%s,%s)"
            df = self.runQuery(dbpool, sqlquery, (self.callerid[-10:], self.uniqueid, datetime.datetime.now(), "NEW"))
            df.addCallback(timepass)
            message = self.messagefetch()
            print "Message ::"+message[0]
            self.log.debug("Start of Script for number " + self.callerid)
            self.log.debug("sending message to misscaller ::" + self.callerid)
            connection = httplib.HTTPConnection("smsidea.co.in", port=80)
            message = "/sendsms.aspx?mobile=9898396969&pass=100&senderid=LINTEL&to=" + self.callerid + "&msg="+message[0].replace(' ', '%20')
            #log.debug(message)
            #message.request("GET", str(message))
            connection.request("GET", message)
            log.debug(message)
            self.log.debug("Getting SMS response for " + self.callerid)
            reply = connection.getresponse()
            readreply = reply.read()
            sqlquery="UPDATE CallLog SET MessageStatus=%s, ReplyStatus=%s where UniqueId="+self.uniqueid
            df = self.runQuery(dbpool, sqlquery, ("DONE", readreply))
            df.addCallback(timepass)
            df.addErrback(checkLost)
            self.log.debug("Responce for Number " + self.callerid + " :: " + readreply)
        else:
            self.log.debug("Responce for Number " + self.callerid + " :: Message already sent.")
        self.hangup()

    def messagefetch(self):
        x = """SELECT message from %s WHERE start_time <= '%s' AND end_time >= '%s'""" % (lday,str(ltime),str(ltime))
        log.debug (x)
        conn = MySQLdb.connect(host = host, user = user, passwd = passwd, db = db)
        cursor = conn.cursor()
        cursor.execute(x)
        message = cursor.fetchone()
        cursor.close()
        return message

    def messagecheck(self):
        conn = MySQLdb.connect (host = smshost, user = smsuser, passwd = smspasswd, db = "sms")
        cursor = conn.cursor()
        diff = datetime.datetime.now() - datetime.timedelta(hours = 1)
        cursor.execute ("SELECT CallerId, Date FROM CallLog WHERE Date >= %s and CallerId=%s",(diff, self.callerid[-10:],))
        a = cursor.fetchall()
        print len(a)
        return len(a)

    def playFile(self,option):
        """Here option is the value returned from database,
        the file name should be same as the value returned in option else error will be returned.

        example: lecture field in db is electronics for Monday, then there should be file named electronics.wav in
        sounds directory.

        """
        lday= datetime.datetime.now().strftime("%A")
        if option:
            x=option[0].values()
            log.debug (x[0])
            df = self.agi.streamFile(soundsdir+str(lday)+'/'+str(x[0]))
        else:
            df = self.agi.streamFile(soundsdir+'none')
        df.addCallback(self.sendMessage)

    def onHangup(self,option):
        """Cause the server to hang up on the channel
        Returns deferred integer response code
        """
        s = fastagi.InSequence()
        s.append(self.agi.hangup)
        s()

dbpool = None
host = config.get("db", "host")
db = config.get("db", "db")
user = config.get("db", "user")
passwd = config.get("db","passwd")

def onConnect(*args):
    log.debug("Connected to DB ")

def connectDB(cb):
    """Create a new ConnectionPool.

        Any positional or keyword arguments other than those documented here
        are passed to the DB-API object when connecting. Use these arguments to
        pass database names, usernames, passwords, etc.

        cp_noisy: generate informational log messages during operation

        cp_openfun: a callback invoked after every connect() on the
                           underlying DB-API object. The callback is passed a
                           new DB-API connection object.  This callback can
                           setup per-connection state such as charset,
                           timezone, etc.

        cp_reconnect: detect connections which have failed and reconnect
                             (default False). Failed connections may result in
                             ConnectionLost exceptions, which indicate the
                             query may need to be re-sent.
        """
    global dbpool
    dbpool = adbapi.ConnectionPool('MySQLdb',
                                   host=host,
                                   db=db,
                                   user=user,
                                   passwd = passwd,
                                   cursorclass = MySQLdb.cursors.DictCursor,
                                   cp_reconnect=True,
                                   cp_openfun=cb,
                                   cp_noisy=True)

connectDB(onConnect)

logpath = config.get("paths", "log")
rootlogger = logging.getLogger('')
fmt = logging.Formatter('%(asctime)s-%(name)s-%(levelname)s : %(message)s')
sh = logging.StreamHandler()
sh.setFormatter(fmt)
rootlogger.addHandler(sh)
rfh = logging.handlers.RotatingFileHandler(logpath+"lvm.log", maxBytes=50000, backupCount=5)
rfh.setFormatter(fmt)
rootlogger.addHandler(rfh)


def route(agi):
    Lecture(agi)


application = getApp("Lecture", route)

