# Copyright (c) 2012, 2013, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 of the
# License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA

from __future__ import with_statement

import threading
import random
import Queue
import traceback
import socket
import select
import sys
import time
import os

import paramiko
from grt import log_error, log_warning, log_debug, log_debug2
_this_file = os.path.basename(__file__)

SSH_PORT = 22
REMOTE_PORT = 3306

# timeout for closing an unused tunnel
TUNNEL_TIMEOUT = 60

# paramiko 1.6 didn't have this class
if hasattr(paramiko, "WarningPolicy"):
    WarningPolicy = paramiko.WarningPolicy
else:
    class WarningPolicy(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            import binascii
            log_warning(_this_file, 'WARNING: Unknown %s host key for %s: %s\n' % (key.get_name(), hostname, binascii.hexlify(key.get_fingerprint())))


class Tunnel(threading.Thread):
    
    """This class is a threaded implementation of an SSH tunnel.
    
    You should not access the attributes that starts with an underscore outside this thread
    of execution (e.g. self._server) for this could run into race conditions. Even when
    accessing its public attributes (those that don't start with an underscore) you should
    be careful of acquiring the self.lock reentrant lock (and releasing it once done):
    
        with tunnel.lock:
            if tunnel.connecting:
                ... whatever...
                
    """

    def __init__(self, q, server, username, target, password, keyfile):
        super(Tunnel, self).__init__()
        self.daemon = True

        self._server = server
        self._username = username
        self._target = target
        self._password = password
        self._keyfile = keyfile
        
        # Acquire and release this lock while accessing the attributes of objects
        # of this class from the main thread: 
        self.lock = threading.RLock()
        
        # This event marks when a random port is selected to be used:
        self.port_is_set = threading.Event()

        self.local_port = None
        self._listen_sock = None
        self.q = q

        self._shutdown = False
        self.connecting = False
        
        self._client = None
        self._connections = []
    
    def is_connecting(self):
        with self.lock:
            return self.connecting
    
    def run(self):
        sys.stdout.write('Thread started\n')  # sys.stdout.write is thread safe while print isn't
        log_debug2(_this_file,"SSH Tunel thread started\n")
        # Create a socket and pick a random port number for it:
        self._listen_sock = socket.socket()
        while True:
                local_port = random.randint(1024, 65535)
                try:
                    self._listen_sock.bind(('127.0.0.1', local_port))
                    self._listen_sock.listen(2)
                    with self.lock:
                        self.local_port = local_port
                    break
                except socket.error, exc:
                    sys.stdout.write('Socket error: %s for port %d\n' % (exc, local_port) )
                    err, msg = exc.args
                    if err == 22:
                        continue # retry
                    self.notify_exception_error('ERROR',"Error initializing server end of tunnel", sys.exc_info())
                    raise exc
                finally:
                    self.port_is_set.set()

        with self.lock:
            self.connecting = True

        if self._keyfile:
            self.notify('INFO', 'Connecting to SSH server at %s:%s using key %s...' % (self._server[0], self._server[1], self._keyfile) )
        else:
            self.notify('INFO', 'Connecting to SSH server at %s:%s...' % (self._server[0], self._server[1]) )

        if not self._connect_ssh():
            self._listen_sock.close()
            self._shutdown = True
        else:
            self.notify('INFO', 'Connection opened')

        with self.lock:
            self.connecting = False

        del self._password

        while not self._shutdown:
            try:
                socks = [self._listen_sock]
                for sock, chan in self._connections:
                    socks.append(sock)
                    socks.append(chan)
                r, w, x = select.select(socks, [], [], TUNNEL_TIMEOUT)
            except Exception, e:
                if not self._shutdown:
                    self.notify_exception_error('ERROR', 'Error while forwarding data: %r' % e, sys.exc_info())
                break

            if not r and len(socks) <= 1:
                self.notify('INFO', 'Closing tunnel to %s:%s for inactivity...\n' % (self._server[0], self._server[1]) )
                break

            if self._listen_sock in r:
                self.notify('INFO', 'New client connection\n')
                self.accept_client()
            
            closed = []
            for sock, chan in self._connections:
                if sock in r:
                    data = sock.recv(1024)
                    if not data:
                        closed.append((sock, chan))
                    else:
                        chan.send(data)

                if chan in r:
                    data = chan.recv(1024)
                    if not data:
                        closed.append((sock, chan))
                    else:
                        sock.send(data)

            for item in set(closed):  # set() will remove duplicates from closed list
                sock, chan = item
                try:
                    sock.close()
                except:
                    pass
                try:
                    chan.close()
                except:
                    pass
                self.notify('INFO', 'Client for %s disconnected\n' % local_port)
                self._connections.remove(item)

        # Time to shutdown:
        for sock, chan in self._connections:
            try:
                sock.close()
            except:
                pass
            try:
                chan.close()
            except:
                pass
        
        self._listen_sock.close()
        self._client.close()
        
    def notify(self, msg_type, msg_object):
        log_debug2(_this_file, "tunnel_%i: %s %s\n" % (self.local_port, msg_type, msg_object))
        self.q.put((msg_type, msg_object))
        
    def notify_exception_error(self, msg_type, msg_txt, msg_obj = None):
        self.notify(msg_type, msg_txt)
        log_error(_this_file, traceback.format_exc())

    def match(self, server, username, target):
        with self.lock:
            return self._server == server and self._username == username and self._target == target

    def _connect_ssh(self):
        """Create the SSH client and set up the connection.
        
        Any exception coming from paramiko will be notified as an error
        that would cause the failure of the connection. Some of these are:
        
        paramiko.AuthenticationException   --- raised when authentication failed for some reason
        paramiko.PasswordRequiredException --- raised when a password is needed to unlock a private key file;
                                               this is a subclass of paramiko.AuthenticationException
        """
        try:
            
            self._client = paramiko.SSHClient()
            self._client.load_system_host_keys()
            self._client.set_missing_host_key_policy(WarningPolicy())
            has_key = bool(self._keyfile)
            self._client.connect(self._server[0], self._server[1], username=self._username,
                                 key_filename=self._keyfile, password=self._password,
                                 look_for_keys=has_key, allow_agent=has_key)
        except paramiko.BadHostKeyException, exc:
            if sys.platform == "win32":
                self.notify_exception_error('ERROR', "Delete entries for the host from the SSH known hosts file", sys.exc_info())
            else:
                self.notify_exception_error('ERROR', "Delete entries for the host from the ~/.ssh/known_hosts file", sys.exc_info())
            return False
        except paramiko.BadAuthenticationType, exc:
            self.notify_exception_error('ERROR', "Bad authentication type, the server is not accepting this type of authentication.\nAllowed ones are:\n %s" % exc.allowed_types, sys.exc_info());
            return False
        except paramiko.AuthenticationException, exc:
            self.notify_exception_error('ERROR', "Authentication failed, please check credentials.\nPlease refer to logs for details", sys.exc_info())
            return False
        except socket.gaierror, exc:
            self.notify_exception_error('ERROR', "Error connecting to SSH server: %s\nPlease refer to logs for details." % str(exc))
            return False
        except paramiko.ChannelException, exc:
            self.notify_exception_error('ERROR', "Error connecting SSH channel.\nPlease refer to logs for details: %s" % str(exc), sys.exc_info())
            return False
        except Exception, exc:
            print exc
            self.notify_exception_error('ERROR', "Authentication error, unhandled exception caught in tunnel manager, please refer to logs for details", sys.exc_info())
            return False
        else:
            return True

    def close(self):
        self.notify('INFO', 'Closing tunnel')
        self._listen_sock.close()
        self._shutdown = True

    def accept_client(self):
        try:
            local_sock, peeraddr = self._listen_sock.accept()
        except Exception, e:
            self.notify_exception_error('ERROR', 'Error accepting new tunnel client: %r' % e,sys.exc_info())
            return
        self.notify('INFO', 'Client connection established')

        transport = self._client.get_transport()

        try:
            sshchan = transport.open_channel('direct-tcpip', self._target, local_sock.getpeername())
        except paramiko.ChannelException, exc:
            self.notify_exception_error('ERROR', 'Could not open port forwarding SSH channel: %s' % exc)
            local_sock.close()
            return
        except Exception, e:
            self.notify_exception_error('ERROR', 'Remote connection to %s:%d failed: %r' % (self._target[0], self._target[1], e), sys.exc_info())
            local_sock.close()
            return

        if sshchan is None:
            self.notify_exception_error('ERROR', 'Remote connection to %s:%d was rejected by the SSH server.' % (self._target[0], self._target[1]), sys.exc_info())
            local_sock.close()
            return

        self.notify('INFO', 'Tunnel now open %r -> %r -> %r' % (local_sock.getpeername(), sshchan.getpeername(), self._target))

        self._connections.append((local_sock, sshchan))

class TunnelManager:
    def __init__(self):
        self.tunnel_by_port = {}

        self.inpipe = sys.stdin
        self.outpipe = sys.stdout

    def _address_port_tuple(self, raw_address, default_port):
        if type(raw_address) is str:
            if ':' in raw_address:
                address, port = raw_address.split(':', 1)
                try:
                    port = int(port)
                except:
                    port = default_port
                return (address, port)
            else:
                return (raw_address, default_port)
        else:
            return raw_address

    def lookup_tunnel(self, server, username, target):
        server = self._address_port_tuple(server, default_port=SSH_PORT)
        target = self._address_port_tuple(target, default_port=REMOTE_PORT)

        for port, tunnel in self.tunnel_by_port.iteritems():
            if tunnel.match(server, username, target) and tunnel.isAlive():
                with tunnel.lock:
                    return tunnel.local_port
        return None

    def open_tunnel(self, server, username, password, keyfile, target):
        try:
            port = self.open_ssh(server, username, password, keyfile, target)
        except Exception:
            traceback.print_exc()
            return (False, str(traceback.format_exc()))
        return (True, port)
   
    def open_ssh(self, server, username, password, keyfile, target):
        server = self._address_port_tuple(server, default_port=SSH_PORT)
        target = self._address_port_tuple(target, default_port=REMOTE_PORT)
        
        password = password or ''
        keyfile  = keyfile  or None

        found = None
        for tunnel in self.tunnel_by_port.itervalues():
            if tunnel.match(server, username, target) and tunnel.isAlive():
                found = tunnel
                break

        if found:
            with tunnel.lock:
                print 'Reusing tunnel at port %d' % tunnel.local_port
                return tunnel.local_port
        else:
            tunnel = Tunnel(Queue.Queue(), server, username, target, password, keyfile)
            tunnel.start()
            tunnel.port_is_set.wait()
            with tunnel.lock:
                port = tunnel.local_port
            self.tunnel_by_port[port] = tunnel
            return port


    def wait_connection(self, port):
        tunnel = self.tunnel_by_port.get(port)
        if not tunnel:
            return 'Could not find a tunnel for port %d' % port
        error = None
        if tunnel.isAlive():
            while True:
                # Process any message in queue. Every retrieved message is printed.
                # If an error is detected in the queue, exit returning its message:
                try:
                    msg_type, msg = tunnel.q.get_nowait()
                except Queue.Empty:
                    pass
                else:
                    _msg = msg
                    if type(msg) is tuple:
                        msg = '\n' + ''.join(traceback.format_exception(*msg))
                        _msg = str(_msg[1])
                    log_debug(_this_file, "%s: %s\n" % (msg_type, msg))
                    if msg_type == 'ERROR':
                        error = _msg
                        break  # Exit returning the error message

                if not tunnel.is_connecting() or not tunnel.isAlive():
                    break
                time.sleep(0.3)
        log_debug(_this_file, "returning from wait_connection(%s): %s\n" % (port, error))
        return error


    def get_message(self, port):
        tunnel = self.tunnel_by_port[port]
        return tunnel.q.get(block=False)
        

    def close(self, port):
        pass
        # tunnels auto-close when inactive
        #tunnel = self.tunnel_by_port.get(port, None)
        #if tunnel:
        #    tunnel.num_clients -= 1
        #    if tunnel.num_clients == 0:
        #        tunnel.close()
        #        del self.tunnel_by_port[port]

    def send(self, code, arg=''):
        if arg:
            self.outpipe.write(code + ' ' + arg + '\n')
        else:
            self.outpipe.write(code + '\n')
        self.outpipe.flush()

    def shutdown(self):
        for tunnel in self.tunnel_by_port.itervalues():
            tunnel.close()

    # FIXME: It seems that this function is never called. Should we remove it?
    def wait_requests(self):
        #print "SSH Tunnel Manager started, waiting for requests..."
        self.send("READY")
        while True:
            request = self.inpipe.readline()
            if not request:
                #print "Exiting tunnel manager..."
                break
            try:
                cmd, args = eval(request, {}, {})
            except:
                self.send("ERROR", "Invalid request")
                continue
            if cmd == "LOOKUP":
                try:
                    port = self.lookup_tunnel(*args)
                    if port is not None:
                        self.send("OK", str(port))
                    else:
                        self.send("ERROR", "not found")
                except Exception, exc:
                    self.send("ERROR", str(exc))
            elif cmd == "OPENSSH":
                try:
                    port = self.open_ssh(*args)
                    self.send("OK", str(port))
                except Exception, exc:
                    self.send("ERROR", str(exc))
            elif cmd == "CLOSE":
                #self.close(args[0])
                self.send("OK")
            elif cmd == "WAIT":
                # wait for the SSH connection to be established
                error = self.wait_connection(args)
                if not error:
                    self.send("OK")
                else:
                    self.send("ERROR "+error)
            elif cmd == "MESSAGE":
                msg = self.get_message(args)
                if msg:
                    self.send(msg)
                else:
                    self.send("NONE")
            else:
                log_error(_this_file, "Invalid request %s\n" % request)
                self.send("ERROR", "Invalid request")

"""
if "--single" in sys.argv:
    target = sys.argv[2]
    if "-pw" in sys.argv:
        password = sys.argv[sys.argv.index("-pw")+1]
    else:
        password = None
    if "-i" in sys.argv:
        keyfile = sys.argv[sys.argv.index("-i")+1]
    else:
        keyfile = None
    server = sys.argv[-1]

    tunnel = Tunnel(None, False)
    if "@" in server:
        username, server = server.split("@", 1)
    else:
        username = ""
    print "Starting tunnel..."
    if type(server) == str:
        if ':' in server:
            server = server.split(":", 1)
            server = (server[0], int(server[1]))
        else:
            server = (server, SSH_PORT)
    if type(target) == str:
        if ':' in target:
            target = target.split(":", 1)
            target = (target[0], int(target[1]))
        else:
            target = (target, REMOTE_PORT)
    
    tunnel.start(server, username, password or "", keyfile, target)

else:
    tm = TunnelManager()
    sys.stdout = sys.stderr
    try:
        tm.wait_requests()
    except KeyboardInterrupt, e:
	    pass

"""
