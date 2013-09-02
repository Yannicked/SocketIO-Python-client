#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
------------------------------------------------------------------------------
 Socket.io client - Python class sending and receiving messages from a socket.io server
 Copyright (c) 2013 Yannick de Jong <yannickdejong@me.com>

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
------------------------------------------------------------------------------'''

#Protocol: https://github.com/LearnBoost/socket.io-spec


'''
Usage:
import socketio

sio = socketio.socketio(server ip, server port) # define the server

sio.connect() # connect
sio.receiveMsg(timeout) # receive timeout is not tested
sio.sendMsg(string) # send
sio.disconnect() to disconnect
'''

import httplib, thread, threading, json, atexit, socket
from time import sleep

try:
    import websocket
except:
    try:
        import websocket
    except:
        raise ImportError("websocket-client is not found, please install or put websocket.py in the same folder as socketio.py")

class SocketIOError(Exception): #Just my own error
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class socketio(object): #the socketio class, the main framework of this library

    def __init__(self, host, port, **kwargs):
        debug = False
        secure = False
        for key in kwargs:
            if key == 'debug':
                debug = kwargs[key]
            if key == 'secure':
                secure = kwargs[key]
        #checking if the port number and the ip is vailid
        if not isinstance( port, ( int, long, basestring ) ):
            raise SocketIOError('%s is not a vailid port' % str(port))
        if not isinstance(host, basestring):
            raise SocketIOError('%s is not a vailid address' % str(host))
        #checking if there are only numbers in the ip
        try:
            int(''.join(host.split('.')))
        except:
            try:
                #if the user entered a hostname like wwww.google.com it will resolve the ip
                host = socket.gethostbyname(host)
            except:
                raise SocketIOError('%s is not a vailid address' % str(host))
        #defining all the variables
        self.host = host
        self.port = port
        self.stop = False
        self.connected = False
        self.ws = None
        self.data = ''
        self.heartbeatTimeout = 20
        self.datanew = False
        self.debug = debug
        self.secure = secure

    #The heartbeat process, if you connect to a socket.io server, it returns a heartbeat timeout. If you don't send a heartbeat the server will terminate the connection between you and the server
    def heartbeat(self):
        time = 0
        while not self.stop:
            if self.data == '2::' and self.datanew:
                self.datanew = False
                while not self.stop:
                    time += 1
                    if time == self.heartbeatTimeout:
                        self.ws.send(self.encode('heartbeat'))
                        time = 0
                        break
                
    #The receiver process will keep receiving and storing the received values in the data variable. When it receives data it will also set the datanew to True
    def receiver(self):
        while not self.stop:
            self.data = self.ws.recv()
            self.datanew = True
            if self.data[0] == '1':
                self.connected = True
            if self.debug:
                print('Received packet from server which contains: %s' % str(self.data))

    #Just call socketio.socketio.data for the most recent received data

    #receiving a message from the receiver process, wait for new data which is also a message packet
    def receiveMsg(self, timeout = 0):
        #set the datanew to false so you dont get old messages
        self.datanew = False
        time = 0
        while not self.datanew or not self.data[0] == '3':
            #wait 0.5 seconds for checking again
            sleep(0.5)
            time += 0.5
            if not timeout == 0 and time == timeout:
                return
        self.datanew = False
        return self.decode(self.data)

    #Thread for receiving events and calling the callback
    def eventHandler(self, event, callback):
        while not self.stop:
            self.datanew = False
            listenFor = '5'
            if event == 'message':
                listenFor = '3'
            while True:
                sleep(0.5)
                if self.datanew and self.data[0] == listenFor:
                    if listenFor == '5':
                        #check if the event we received was the event we were looking for.
                        if json.loads(self.decode(self.data))['name'] == event:
                            break
                    else:
                        break
            #run the callback as a thread, so we can go on receiving
            if listenFor == '5':
                threading.Thread(target=callback, args=json.loads(self.decode(self.data))['args']).start()
            else:
                threading.Thread(target=callback, args=self.decode(self.data)).start()

    #simple starter for the eventHandler thread
    def on(self, event, callback):
        threading.Thread(target=self.eventHandler, args=(event, callback)).start()
        return True
    
    #same as the receiveMsg but for Json packages
    def receiveJson(self, timeout = 0):
        self.datanew = False
        time = 0
        while not self.datanew or not self.data[0] == '4':
            sleep(0.5)
            time += 0.5
            if not timeout == 0 and time == timeout:
                return
        #return a json packet
        return json.loads(self.decode(self.data))

    #same as receiveJson, but for Event packages
    def receiveEvent(self, timeout = 0):
        self.datanew = False
        time = 0
        while not self.datanew or not self.data[0] == '5':
            sleep(0.5)
            time += 0.5
            if not timeout == 0 and time == timeout:
                return
        #return a json packet
        return json.loads(self.ecode(self.data))['args']                
    
    #remove the header from a package
    def decode(self, m):
        m = str(m)
        m = m.split(':', 3)
        m.pop(0)
        m.pop(0)
        m.pop(0)
        m = ''.join(i for i in m)
        return m
        
        
    
    def connect(self):
        #before connecting to the server we need to get a client id
        self.stop = False
        conn = httplib.HTTPConnection(self.host, self.port)
        conn.request('POST','/socket.io/1/')
        resp = conn.getresponse().read()
        hskey = resp.split(':')[0]
        self.heartbeatTimeout = int(resp.split(':')[1])
        if self.heartbeatTimeout <= 5:
            self.heartbeatTimeout = 1
        else:
            self.heartbeatTimeout -= 5
        protocol = 'ws'
        if self.secure:
            protocol = 'wss'
        socketIOUrl = '%s://%s:%i/socket.io/1/websocket/%s' % (protocol, self.host, self.port, hskey)
        self.ws = websocket.create_connection(socketIOUrl)
        threading.Thread(target=self.receiver).start()
        if self.heartbeatTimeout:
            threading.Thread(target=self.heartbeat).start()
        #Optional, check if server approved connection/respond
        sleep(0.75)
        if self.connected:
            atexit.register(self.disconnect) #Doesn't work?
            return
        else:
            self.disconnect()
            raise SocketIOError('Server didn\'t respond')

    #Disconnect, just to be complete
    def disconnect(self):
        #set the stop variable to true so the other Threads stop asap
        self.stop = True
        self.connected = True
        #send a disconnect message to the server
        if self.ws:
            self.ws.send(self.encode('disconnect'))

    #Easy to understand, example: if you send 0::: the server will know you want to disconnect
    def encode(self, sort, message = 'Hello, World'):
        if sort == 'disconnect':
            return '0:::'
        elif sort == 'heartbeat':
            return '2:::'
        elif sort == 'message':
            return '3:::%s' % message
        elif sort == 'json':
            return '4:::%s' % json.dumps(message)
        elif sort == 'event':
            return '5:::%s' % json.dumps(message)
    #simple wrapper for sending a string
    def sendMsg(self, m='Hello, World'):
        self.ws.send(self.encode('message', m))
    #simple wrapper for sending json encoded strings (experimental)
    def sendJson(self, m={'Hello':'World'}):
        self.ws.send(self.encode('json', m))
    #wrapper for sending events, 
    def sendEvent(self, m={'name' : 'Hello', 'args' : 'World'}):
        self.ws.send(self.encode('event', m))
