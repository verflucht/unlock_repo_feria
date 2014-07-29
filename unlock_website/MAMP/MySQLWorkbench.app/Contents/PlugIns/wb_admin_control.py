# Copyright (c) 2007, 2013, Oracle and/or its affiliates. All rights reserved.
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

import os
import socket
import threading
import time
import Queue
import StringIO

from workbench.utils import server_version_str2tuple
from wb_admin_ssh import SSHDownException
from workbench.db_utils import MySQLConnection, MySQLError, QueryError, strip_password

from wb_common import OperationCancelledError, Users, PermissionDeniedError, InvalidPasswordError

from wb_server_control import PasswordHandler, ServerControlShell, ServerControlWMI
from wb_server_management import ServerManagementHelper, SSH, wbaOS

import mforms

import wb_variables

from grt import log_info, log_error, log_warning, log_debug
_this_file = os.path.basename(__file__)

MYSQL_ERR_ACCESS_DENIED = 1045
MYSQL_ERR_PASSWORD_EXPIRED = 1820

#===============================================================================
#
#===============================================================================
# Handling object should have corresponding method if the object wants to receive
# events. For event shutdown method name must be shutdown_event
class EventManager(object):
    valid_events = ['server_started_event', 'server_stopped_event', 'shutdown_event']

    def __init__(self):
        self.events = {}
        self.defer = False
        self.deferred_events = []

    def add_event_handler(self, event_name, handler):
        event_name += "_event"
        if hasattr(handler, event_name):
            handlers_list = None

            if event_name in self.events:
                handlers_list = self.events[event_name]
            else:
                handlers_list = []
                self.events[event_name] = handlers_list

            handlers_list.append(handler)
            log_debug(_this_file, "Added " + handler.__class__.__name__ + " for event " + event_name + '\n')
        else:
            print "Error! ", handler.__class__, " does not have method", event_name
            log_error(_this_file, handler.__class__.__name__ + " does not have method " + event_name + '\n')

    def defer_events(self):
        self.defer = True

    def continue_events(self):
        self.defer = False
        for ev_name in self.deferred_events:
            self.event(ev_name)
        self.deferred_events = []

    def event(self, name):
        if self.defer:
            self.deferred_events.append(name)
            return

        name += "_event"
        if name not in self.valid_events:
            print "EventManager: invalid event", name
            log_error(_this_file, 'EventManager: invalid event: ' + name + '\n')
        elif name in self.events:
            log_debug(_this_file, "Found event " + name + " in list" + '\n')
            for obj in self.events[name]:
                if hasattr(obj, name):
                    log_debug(_this_file, "Passing event " + name + " to " + obj.__class__.__name__ + '\n')
                    getattr(obj, name)()
        else:
            log_debug(_this_file, "Found valid but unrequested event " + name + " in list" + '\n')

#===============================================================================
#import thread
class SQLQueryExecutor(object):
    dbconn = None
    mtx     = None

    def __init__(self, dbconn):
        log_debug(_this_file, "Constructing SQL query runner, dbconn (" + repr(dbconn) + ')\n')
        self.mtx = threading.Lock()
        self.dbconn = dbconn

    def is_connected(self):
        return self.dbconn is not None and self.dbconn.is_connected

    def close(self):
        if self.is_connected():
            self.mtx.acquire()
            try:
                if self.dbconn:
                    self.dbconn.disconnect()
            finally:
                self.mtx.release()
        self.dbconn = None

    def exec_query(self, query):
        result = None
        self.mtx.acquire()
        try:
            if self.is_connected():
                log_debug(_this_file, "Executing query %s\n" % strip_password(query))
                result = self.dbconn.executeQuery(query)
        finally:
            self.mtx.release()
        return result

    def execute(self, query):
        result = None
        self.mtx.acquire()
        try:
            if self.is_connected():
                log_debug(_this_file, "Executing statement %s\n" % strip_password(query))
                result = self.dbconn.execute(query)
        finally:
            self.mtx.release()
        return result


#===============================================================================

#-------------------------------------------------------------------------------
def wba_arithm(linenr, line, op, value):
    fv = line
    # We shoould have get two numbers
    try:
        fv = float(line.strip(" \r\t\n,.:"))
        value = float(value)
        if (op == "/"):
            if value != 0:
                fv /= value
        elif (op == "*"):
            fv *= value
        elif (op == "+"):
            fv += value
        elif (op == "-"):
            fv -= value
    except ValueError:
        fv = line

    return (str(fv), 0) # text and status. 0 - success

#-------------------------------------------------------------------------------
def wba_token(linenr, line, sep, nrs):
    tokens = [ token for token in line.split(sep) if len(token) > 0 ]
    out = ""
    l = len(tokens)
    for nr in nrs:
        if -l <= nr < l:
            out += tokens[nr] + sep
    return (out.strip(sep+','), 0)

#-------------------------------------------------------------------------------
def wba_filter(linenr, line, pattern):
    if pattern in line:
        return (line, 0)
    return ("", 1)

#-------------------------------------------------------------------------------
def wba_line(linenr, line, expected_linenr):
    if linenr == expected_linenr:
        return (line, 0)
    return ("", 1)

#-------------------------------------------------------------------------------
def parse_wba_token(text):
    f = None
    p = text[9:].strip(" |\r\n\t()").split(",")
    try:
        args = [ int(x) for x in p[1:] ]
        f = (wba_token, (p[0].strip(" ").strip("'"), tuple(args)))
    except ValueError:
        print "Wrong filter format: ", text, ". Required format is wba_token('pattern_symbol', # of token, optional # of tokens)"
        log_error(_this_file, "parse_wba_token: Wrong filter format: " + text + ". Required format is wba_token('pattern_symbol', # of token, optional # of tokens)\n")
        f = None

    return f

#-------------------------------------------------------------------------------
def parse_wba_filter(text):
    f = None

    if len(text) > 11:
        p = text.strip(" |\r\n\t")[11:][:-1]
        f = (wba_filter, (p,))

    return f

#-------------------------------------------------------------------------------
def parse_wba_line(text):
    f = None

    try:
        if len(text) > 8:
            p = int(text[8:].strip(" |\r\n\t()"))
            f = (wba_line, (p,))
    except ValueError, e:
        print str(e), " in filter line ", text
        log_error(_this_file, 'parse_wba_line: Exception caught: "%s" in filter line "%s"\n' % (str(e), text))
        f = None

    return f

#-------------------------------------------------------------------------------
def parse_wba_arithm(text):
    f = None

    if len(text) > 10:
        p = text[10:].strip(" |\r\n\t()").split(",")
        f = (wba_arithm, tuple(p))

    return f

#-------------------------------------------------------------------------------
filter_parsers = [("wba_token", parse_wba_token), ("wba_filter", parse_wba_filter), ("wba_line", parse_wba_line), ("wba_arithm", parse_wba_arithm)]

#-------------------------------------------------------------------------------
def build_filters(script):
    filters = []
    text = script
    leave = False

    if text is None:
        return (text, filters)

    while not leave:
        filter_was_parsed = False
        idx = text.rfind('|')
        if idx >= 0:
            raw_filter = text[idx:].strip(" \r\t\n|")
            for (pattern, parser) in filter_parsers:
                if raw_filter.find(pattern) == 0:
                    parsed_filter = parser(raw_filter)
                    if parsed_filter is not None:
                        filters.insert(0, parsed_filter)
                        filter_was_parsed = True
                        break
                    else:
                        text = script
                        filters = []
                        leave = True
                        break

            if filter_was_parsed:
                text = text[:idx]
            else:
                leave = True
        else:
            leave = True

    return (text, filters)


#-------------------------------------------------------------------------------
def empty_dbg(x):
    pass

def apply_filters(raw_text, filters, dbg = None):
    if dbg is None:
        dbg = empty_dbg

    if raw_text is None:
        return (None, 1)

    out = ""
    code = None
    lines = raw_text.split("\n")

    for f in filters:
        filter_status_code = 1
        new_lines = []
        dbg(f[0].__name__ + " " + str(f[1:]) + "\n")
        for i,line in enumerate(lines):
            line = line.strip("\r")
            orig_line = line
            (line, cur_code) = f[0](i, line, *f[1])
            dbg("   " + str(i) + " '" + orig_line + "' -> '" + line + "'. cur_code = " + str(cur_code) + "\n")
            if len(line) > 0:
                new_lines.append(line)

            if cur_code == 0:
                filter_status_code = 0

        lines = new_lines

        if code is None:
            code = filter_status_code
        elif code == 0:
            code = filter_status_code
        dbg(f[0].__name__ + " exec code = " + str(code) + "\n-------------\n")

    dbg("Filtered text:\n")
    for line in lines:
        if len(line) > 0:
            out += line + '\n'
            dbg(line + '\n')

    dbg("Filters execution code = " + str(code) + "\n===================\n")
    return (out, code) # return last code from filters


#===============================================================================

class WbAdminControl(object):
    server_helper = None # Instance of ServerManagementHelper for doing file and process operations on target server
    server_control = None # Instance of ServerControlBase to do start/stop/status of MySQL server

    ssh = None
    sql = None

    raw_version = "unknown"
    server_version = "unknown"

    def __init__(self, server_profile, connect_sql=True):

        self.server_control = None
        self.events   = EventManager()
        self.defer_events() # continue events should be called when all listeners are registered, that happens later in the caller code
                          # Until then events are piled in the queue

        self.server_profile = server_profile
        self.server_control_output_handler = None

        self.task_queue = Queue.Queue(512)

        self.sql_enabled = connect_sql
        self.password_handler = PasswordHandler(server_profile)

        self.server_active_plugins = set()

        self.running = True

        self.add_me_for_event("server_started", self)
        self.add_me_for_event("server_stopped", self)
        # We'll use server_status to store information from self.sql_status_callback
        # The callback is called on success and failure of execution of a query
        self.server_status = {}
        self.variables_pool = wb_variables.WBAVariables(self)

        self.server_variables = {}


    def get_variables_pool(self):
        return self.variables_pool

    @property
    def admin_access_available(self):
        return self.server_control is not None

    def acquire_admin_access(self):
        """Make sure we have access to the instance for admin (for config file, start/stop etc)"""
        if self.server_control or not self.server_profile.admin_enabled:
            return
        if self.server_profile.uses_ssh:
            try:
                self.ssh = SSH(self.server_profile, self.password_handler)
            except OperationCancelledError:
                self.ssh = None
                raise OperationCancelledError("SSH connection cancelled")

            except SSHDownException:
                import traceback
                log_error(_this_file, "SSHDownException: %s\n" % traceback.format_exc())
                self.ssh = None
                if self.sql_enabled:
                    if mforms.Utilities.show_warning('SSH connection failed',
                                                     "Check if the SSH server is up on the remote side.\nYou may continue anyway, but some functionality will be unavailable",
                                                     "Continue", "Cancel", "") != mforms.ResultOk:
                        raise OperationCancelledError("Could not connect to SSH server")
                else:
                    mforms.Utilities.show_warning('SSH connection failed',
                                                  "Check if the SSH server is up on the remote side.", "OK", "", "")
        else:
            self.ssh = None
        # init server management helper (for doing remote file operations, process management etc)
        self.server_helper = ServerManagementHelper(self.server_profile, self.ssh)
        if self.server_helper:
            self.server_profile.expanded_config_file_path = self.server_helper.shell.expand_path_variables(self.server_profile.config_file_path)
        # detect the exact type of OS we're managing
        os_info = self.detect_operating_system_version()
        if os_info:
            os_type, os_name, os_variant, os_version = os_info
            log_info(_this_file, "Target OS detection returned: os_type=%s, os_name=%s, os_variant=%s, os_version=%s\n" % (os_type, os_name, os_variant, os_version))
            self.server_profile.set_os_version_info(os_type or "", os_name or "", os_variant or "", os_version or "")
        else:
            log_warning(_this_file, "Could not detect target OS details\n")
        # init server control instance appropriate for what we're connecting to
        if self.server_profile.uses_wmi:
            self.server_control = ServerControlWMI(self.server_profile, self.server_helper, self.password_handler)
            self.server_control.set_filter_functions(build_filters, apply_filters)
        elif self.server_profile.uses_ssh or self.server_profile.is_local:
            self.server_control = ServerControlShell(self.server_profile, self.server_helper, self.password_handler)
            self.server_control.set_filter_functions(build_filters, apply_filters)
        else:
            log_error(_this_file, """Unknown management method selected. Server Profile is possibly inconsistent
uses_ssh: %i uses_wmi: %i\n""" % (self.server_profile.uses_ssh, self.server_profile.uses_wmi))
            raise Exception("Unknown management method selected. Server Profile is possibly inconsistent")

    def init(self):
        # connect SQL
        while self.sql_enabled:
            try:
                self.connect_sql()
                break
            except MySQLError, err:
                if err.code == MYSQL_ERR_ACCESS_DENIED:
                    # Invalid password, request password
                    r = mforms.Utilities.show_error("Could not connect to MySQL Server at %s" % err.location,
                            "Could not connect to MySQL server: %s\nClick Continue to proceed without functionality that requires a DB connection." % err,
                            "Retry", "Cancel", "Continue")
                    if r == mforms.ResultOk:
                        continue
                    elif r == mforms.ResultCancel:
                        raise OperationCancelledError("Connection cancelled")
                    else:
                        # continue without a db connection
                        self.sql_enabled = False
                elif err.code == MYSQL_ERR_PASSWORD_EXPIRED:
                    import grt
                    if not grt.modules.WbAdmin.handleExpiredPassword(self.server_profile.db_connection_params):
                        raise OperationCancelledError("Connection cancelled")
                else:
                    self.sql_enabled = False
                    if not self.server_profile.admin_enabled:  # We have neither sql connection nor management method
                        raise Exception('Could not connect to MySQL Server and no management method is available')


    def shutdown(self):
        self.events.event('shutdown')
        self.running = False
        self.disconnect_sql()
        if self.ssh:
            self.ssh.close()

    #---------------------------------------------------------------------------
    def is_server_running(self, verbose = 0, force_process_check = False):
        # Check recent information from query runs. If last query (not older than 4 secs)
        # was performed successfully, then we imply that server is up.
        ret = "unknown"

        use_process_check = True

        if not self.server_control:
            use_process_check = False
            force_process_check = False

        if not force_process_check:
            ts = time.time()
            connid = self.server_profile.db_connection_params.hostIdentifier
            if connid is not None:
                (status, stime) = self.server_status.get(connid, (False, 0))
                # time diff is not sufficient for MacOS->RemoteWin, so WBA
                # has recurring sql connection drop with follwing re-connect.
                if ts - stime < 8 and status:
                    ret = 'running'
                    use_process_check = False

        if use_process_check:
            ret = self.server_control.get_status(verbose=verbose)

        return ret

    #---------------------------------------------------------------------------
    def uitask(self, task, *args):
        self.task_queue.put((task, args))

    #---------------------------------------------------------------------------
    def process_ui_task_queue(self):
        while not self.task_queue.empty():
            func, args = self.task_queue.get()
            func(*args)
            self.task_queue.task_done()

    """
      Adds object for event named @event. In order for object to handle event
    it needs to conform to some requirements. For example if there is a need for
    some object to handle an event named 'server_started', the object's class must
    have method named server_started_event. Valid event names can be found in
    EventManager class.

    param event: name of the event, for example 'server_started'
    param obj: object which method named <event_name>_event will be called
    """
    def add_me_for_event(self, event, obj):
        self.events.add_event_handler(event, obj)

    #---------------------------------------------------------------------------
    """
      Tells to notify all listener objects that event occured.
    """
    def event(self, name):
        self.events.event(name)


    def event_from_main(self, event_name):
        self.uitask(self.event, event_name)

    #---------------------------------------------------------------------------
    """
    This method should not be used outside of MyCtrl. The aim of the method to
    queue coming events for later processing. This is used when events start tp
    appear at load stage, but all listeners may not be registered yet.
    """
    def defer_events(self):
        self.events.defer_events()

    #---------------------------------------------------------------------------
    """
    This method should not be used outside of MyCtrl. It indicate that deferred
    events can be delivered to listeners and resumes normal events flow processing.
    """
    def continue_events(self):
        self.events.continue_events()


    def expand_path_variables(self, path):
        ret = path
        if self.server_helper:
            ret = self.server_helper.shell.expand_path_variables(self.server_profile.config_file_path)
        return ret

    #---------------------------------------------------------------------------
    def server_started_event(self):
        self.uitask(self.connect_sql)


    #---------------------------------------------------------------------------
    def server_stopped_event(self):
        self.uitask(self.disconnect_sql)


    #---------------------------------------------------------------------------
    def get_new_sql_connection(self):
        connection = None
        try:
            connection = MySQLConnection(self.server_profile.db_connection_params, self.sql_status_callback)
            connection.connect()
        except MySQLError, err:
            log_error(_this_file, "Error creating SQL connection for monitoring: %r\n" % err)
            connection = None
            return None

        return connection

    #---------------------------------------------------------------------------
    """
    This method is passed to MySQLConnection.__init__. MySQLConnection will call
    this method when connection created/destroyed, also on success or error when
    executing query
    """
    def sql_status_callback(self, code, error, connect_info):
        connid = connect_info.hostIdentifier
        self.server_status = {}
        ts = time.time()

        if connid is not None:
            if code == 0:
                self.server_status[connid] = (True, ts)
        else:
            e = QueryError(code, error)
            if e.is_connection_error():
                self.server_status[connid] = (False, ts)

    #---------------------------------------------------------------------------
    def connect_sql(self): # from GUI thread only, throws MySQLError
        def get_config_options():
            if self.server_profile.config_file_path:
                try:
                    cfg_file = StringIO.StringIO(self.server_helper.get_file_content(self.server_profile.config_file_path))
                except PermissionDeniedError:
                    log_debug(_this_file, 'Could not open the file "%s" as the current user. Trying as admin' % self.server_profile.config_file_path)
                    while True:
                        try:
                            password = self.password_handler.get_password_for('file')
                            cfg_file = StringIO.StringIO(self.server_helper.get_file_content(self.server_profile.config_file_path,
                                              as_user=Users.ADMIN, user_password = password))
                            break
                        except InvalidPasswordError:
                            self.password_handler.reset_password_for('file')
                        except Exception, err:
                            log_error(_this_file, 'Could not open the file "%s": %s' % (self.server_profile.config_file_path, str(err)))
                            return {}
                except Exception, err:
                    log_error(_this_file, 'Could not open the file "%s": %s' % (self.server_profile.config_file_path, str(err)))
                    return {}

                opts = {}
                section = 'root'
                for line in cfg_file:
                    line = line.strip()
                    if line == '' or line.startswith('#'):
                        continue
                    elif line.startswith('[') and line.endswith(']'):
                        section = line[1:-1].strip()
                    else:
                        k, d, v = line.partition('=')
                        val = v.strip() or 'ON'
                        opts.setdefault(section, {})[k.strip()] = val
                return opts
            return {}

        normpath = self.server_profile.path_module.normpath

        if not self.is_sql_connected():
            connection = MySQLConnection(self.server_profile.db_connection_params, self.sql_status_callback)
            connection.connect()

            self.sql = SQLQueryExecutor(connection)

            if self.is_sql_connected():
                # perform some server capabilities checking

                self.server_variables = {}
                result = self.exec_query("SHOW VARIABLES")
                while result and result.nextRow():
                    self.server_variables[result.stringByName("Variable_name")] = result.stringByName("Value")

                # check version
                result = self.exec_query("select version() as version")
                if result and result.nextRow():
                    self.server_version= result.stringByName("version")
                    self.raw_version = self.server_version
                    if self.server_profile.server_version != self.server_version: # Update profile version with live data from server
                        log_info(_this_file, '%s.connect_sql(): The server version stored in the server instance profile was "%s". '
                                    'Changed to the version reported by the server: "%s"\n' % (self.__class__.__name__,
                                    self.server_profile.server_version, self.server_version) )
                        self.server_profile.server_version = self.server_version
                    self.get_server_version()  # This will convert self.server_version into a version tuple

                if self.server_version >= (5, 1, 5):
                    # The command to retrieve plugins was 'SHOW PLUGIN' for v. [5.1.5, 5.1.9)
                    # and was changed to 'SHOW PLUGINS' from MySQL Server v. 5.1.9 onwards:
                    plugin_var = 'PLUGIN' if self.server_version < (5, 1, 9) else 'PLUGINS'
                    result = self.exec_query('SHOW %s' % plugin_var)
                    # check whether Windows authentication plugin is available
                    while result and result.nextRow():
                        name = result.stringByName("Name")
                        status = result.stringByName("Status")
                        plugin_type = result.stringByName("Type")
                        if status == "ACTIVE":
                            self.server_active_plugins.add((name, plugin_type))

                opts = get_config_options()
                config_section = self.server_profile.config_file_section or 'mysqld'

                request_save_profile = False

                hostname = self.server_variables.get('hostname', '')
                if not hostname and self.server_profile.is_local:
                    hostname = socket.gethostname()

                datadir = self.server_variables.get('datadir', '')
                if datadir and self.server_profile.datadir != datadir:
                    self.server_profile.datadir = datadir
                    request_save_profile = True

                basedir = self.server_variables.get('basedir', '')
                if basedir and self.server_profile.basedir != basedir:
                    self.server_profile.basedir = basedir
                    request_save_profile = True

                try:
                    general_log_enabled = self.server_variables.get('general_log') in ('ON', '1')
                    if self.server_profile.general_log_enabled != general_log_enabled:
                        self.server_profile.general_log_enabled = general_log_enabled
                        request_save_profile = True
                except ValueError:
                    pass

                try:
                    if self.server_version < (5, 1, 29):
                        slow_query_var = 'log_slow_queries'
                    else:
                        slow_query_var = 'slow_query_log'
                        
                    slow_log_enabled = self.server_variables.get(slow_query_var) in ('ON', '1')
                    if self.server_profile.slow_log_enabled != slow_log_enabled:
                        self.server_profile.slow_log_enabled = slow_log_enabled
                        request_save_profile = True
                except ValueError:
                    pass

                if self.server_version < (5, 1, 29):
                    general_log_file_path = opts[config_section].get('log', '').strip(' "') if opts.has_key(config_section) else ''
                    general_log_file_path = normpath(general_log_file_path)
                    if self.server_profile.general_log_file_path != general_log_file_path:
                        self.server_profile.general_log_file_path = general_log_file_path or os.path.join(self.server_profile.datadir, hostname + '.log')
                        request_save_profile = True

                    slow_query_log_file = opts[config_section].get('log-slow-queries', '').strip(' "') if opts.has_key(config_section) else ''
                    slow_query_log_file = normpath(slow_query_log_file)
                    if self.server_profile.slow_log_file_path != slow_query_log_file:
                        self.server_profile.slow_log_file_path = slow_query_log_file or os.path.join(self.server_profile.datadir, hostname + '.slow')
                        request_save_profile = True

                    error_log_file_path = opts[config_section].get('log-error', '').strip(' "') if opts.has_key(config_section) else ''
                    error_log_file_path = normpath(error_log_file_path)
                    if self.server_profile.error_log_file_path != error_log_file_path:
                        self.server_profile.error_log_file_path = error_log_file_path or os.path.join(self.server_profile.datadir, hostname + '.err')
                        request_save_profile = True

                else:
                    path = self.server_variables.get('general_log_file')
                    general_log_file_path = normpath(path) if path and path != '0' else ''
                    if self.server_profile.general_log_file_path != general_log_file_path:
                        self.server_profile.general_log_file_path = general_log_file_path
                        request_save_profile = True

                    path = self.server_variables.get('slow_query_log_file')
                    slow_query_log_file_path = normpath(path) if path and path != '0' else ''
                    if self.server_profile.slow_log_file_path != slow_query_log_file_path:
                        self.server_profile.slow_log_file_path = slow_query_log_file_path
                        request_save_profile = True

                    path = self.server_variables.get('log_error')
                    log_error_path = normpath(path) if path and path != '0' else ''
                    if self.server_profile.error_log_file_path != log_error_path:
                        self.server_profile.error_log_file_path = log_error_path
                        request_save_profile = True

                log_info(_this_file, "Created SQL connection to MySQL server. Server version is " + repr(self.server_version) +
                         ", conn status = " + repr(self.is_sql_connected()) +
                         ", active plugins = " + str([x[0] for x in self.server_active_plugins]) + '\n')

                # Save the server profile if at least one of its values has changed:
                if request_save_profile:
                    from grt.modules import Workbench
                    Workbench.saveInstances()
            else:
                print "Failed to connect to MySQL server"
        else:
            print "Already connected to MySQL server"

    #---------------------------------------------------------------------------
    def disconnect_sql(self):
        if self.sql:
            self.sql.close()
        self.sql = None
        self.server_version = "unknown"

    #---------------------------------------------------------------------------
    def is_sql_connected(self):
        return self.sql and self.sql.is_connected()

    #---------------------------------------------------------------------------
    def sql_ping(self):
        ret = False
        if self.is_sql_connected():
            try:
                self.sql.exec_query("select 1")
                ret = True
            except QueryError, e:
                if not e.is_connection_error():
                    ret = True # Any other error except connection ones is from server
        else:
            try:
                self.connect_sql()
            except MySQLError, e:
                pass # ignore connection errors, since it likely means the server is down

            # Do not do anything for now, connection status check will be perfomed
            # on the next sql_ping call
        return ret

    #---------------------------------------------------------------------------
    def exec_query(self, q, auto_reconnect=True):
        ret = None
        if self.sql is not None:
            try:
                ret = self.sql.exec_query(q)
            except QueryError, e:
                log_warning(_this_file, "Error executing query %s: %s\n"%(q, strip_password(str(e))))
                if auto_reconnect and e.is_connection_error():
                    log_warning(_this_file, "exec_query: Loss of connection to mysql server was detected.\n")
                    self.handle_sql_disconnection(e)
                else: # if exception is not handled, give a chance to the caller do it
                    raise e
        else:
            log_info(_this_file, "sql connection is down\n")

        return ret

    def exec_sql(self, q, auto_reconnect=True):
        ret = None
        if self.sql is not None:
            try:
                ret = self.sql.execute(q)
            except QueryError, e:
                log_warning(_this_file, "Error executing SQL %s: %s\n"%(strip_password(q), strip_password(str(e))))
                if auto_reconnect and e.is_connection_error():
                    log_warning(_this_file, "exec_sql: Loss of connection to mysql server was detected.\n")
                    self.handle_sql_disconnection(e)
                else:
                    raise e
        else:
            log_info(_this_file, "sql connection is down\n")

        return ret

    def handle_sql_disconnection(self, e):
        self.disconnect_sql()
        if e.is_error_recoverable():
            log_warning(_this_file, "Error is recoverable. Reconnecting to MySQL server.\n")
            try:
                self.connect_sql()
                if self.is_sql_connected():
                    return True
            except MySQLError, er:
                log_warning(_this_file, "Auto-reconnection failed: %s\n" % er)
            return False
        return False

    #---------------------------------------------------------------------------
    def get_server_variable(self, variable, default = None):
        return self.server_variables.get(variable, default)

    #---------------------------------------------------------------------------
    def get_server_version(self):
        if isinstance(self.server_version, (str, unicode)):
            self.server_version = server_version_str2tuple(self.server_version)

        if not self.server_version or not isinstance(self.server_version, tuple):
            log_warning(_this_file, 'Could not parse the server version tuple. Server version set to (5, 1)')
            self.server_version = (5, 1)

        return self.server_version

    #---------------------------------------------------------------------------
    def open_ssh_session_for_monitoring(self):
        ssh = SSH(self.server_profile, self.password_handler)

        return ssh

    #---------------------------------------------------------------------------
    def is_ssh_connected(self):
        return self.ssh is not None

    #---------------------------------------------------------------------------
    def detect_operating_system_version(self):
        """Try to detect OS information in the remote server, via SSH connection.
            
        The information returned is (os_type, os_name, os_variant, os_version)
            
            
            os_type: one of the main types of OS supported (one of wbaOS.windows, wbaOS.linux, wbaOS.darwin)
            os_name: the exact name of the OS (eg Windows, Linux, Mac OS X, Solaris)
            os_variant: the variant of the OS, esp for Linux distributions (eg Ubuntu, Fedora etc)
            os_version: the version of the OS (eg 12.04, XP etc)
        """
        if self.ssh or self.server_profile.is_local:
            o = StringIO.StringIO()
            # check if windows
            rc = self.server_helper.execute_command('ver', output_handler=o.write)
            if rc == 0 and o.getvalue().strip().startswith("Microsoft Windows"):
                os_type = wbaOS.windows
                os_name = "Windows"
                os_variant = "Windows"
                os_version = o.getvalue().strip()

                o = StringIO.StringIO()
                rc = self.server_helper.execute_command('reg query "HKLM\Software\Microsoft\Windows NT\CurrentVersion" /v "ProductName"', output_handler=o.write)
                if rc == 0:
                    os_name = " ".join(o.getvalue().strip().split("\n")[-1].split()[2:])
                return os_type, os_name, os_variant, os_version
            else:
                os_type, os_name, os_variant, os_version = (None, None, None, None)

                o = StringIO.StringIO()
                if self.server_helper.execute_command("uname", output_handler=o.write) == 0:
                    ostype = o.getvalue().strip()
                    log_debug(_this_file, "uname in remote system returned %s\n"%ostype)
                    if ostype == "Darwin":
                        os_type = wbaOS.darwin
                        o = StringIO.StringIO()
                        if self.server_helper.execute_command("sw_vers", output_handler=o.write) == 0:
                            for line in o.getvalue().strip().split("\n"):
                                line = line.strip()
                                if line:
                                    k, v = line.split(":", 1)
                                    if k == "ProductName":
                                        os_name = v.strip()
                                        os_variant = v.strip()
                                    elif k == "ProductVersion":
                                        os_version = v.strip()
                    else:
                        os_type = wbaOS.linux

                        o = StringIO.StringIO()
                        if self.server_helper.execute_command("lsb_release -a", output_handler=o.write) == 0:
                            os_name = "Linux"
                            for line in o.getvalue().strip().split("\n"):
                                line = line.strip()
                                if line:
                                    k, sep, v = line.partition(":")
                                    if k == "Distributor ID":
                                        os_variant = v.strip()
                                    elif k == "Release":
                                        os_version = v.strip()
                        else:
                            log_warning(_this_file, "lsb_release utility not found in target server. Consider installing its package if possible\n")
                            # some distros don't install lsb things by default
                            try:
                                info = self.server_helper.get_file_content("/etc/fedora-release")
                                if info:
                                    os_name = "Linux"
                                    os_variant = "Fedora"
                                    os_version = info[info.find("release")+1:].split()[0].strip()
                            except (IOError, OSError):
                                pass
                            try:
                                info = self.server_helper.get_file_content("/etc/debian_version")
                                if info:
                                    os_name = "Linux"
                                    os_variant = "Debian"
                                    os_version = info.strip()
                            except (IOError, OSError):
                                pass
                            try:
                                info = self.server_helper.get_file_content("/etc/oracle-release")
                                if info:
                                    os_name = "Linux"
                                    os_variant = "Oracle Linux"
                                    os_version = info[info.find("release")+1:].split()[0].strip()
                            except (IOError, OSError):
                                pass
                    return os_type, os_name, os_variant, os_version
                else:
                    log_error(_this_file, "Could not execute uname command on remote server, system type is unknown\n")
        return None


