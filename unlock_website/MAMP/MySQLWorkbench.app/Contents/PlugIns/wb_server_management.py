# Copyright (c) 2007, 2012, 2013, Oracle and/or its affiliates. All rights reserved.
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

import platform
import os
import posixpath
import ntpath
import errno
import threading
import tempfile
import StringIO
import pipes
import subprocess
import time
import inspect

default_sudo_prefix       = '/usr/bin/sudo -S -p EnterPasswordHere'

from mforms import App
from workbench.utils import QueueFileMP
from wb_common import InvalidPasswordError, PermissionDeniedError, Users, sanitize_sudo_output, splitpath
from wb_admin_ssh import WbAdminSSH, ConnectionError

from grt import log_info, log_error, log_warning, log_debug, log_debug2, log_debug3
_this_file = os.path.basename(__file__)

from workbench.tcp_utils import CustomCommandListener
from workbench.os_utils import FileUtils, OSUtils, FunctionType

class wbaOS(object):
    unknown = "unknown"
    windows = "windows"
    linux   = "linux"
    darwin  = "darwin"

    def __setattr__(self, name, value):
        raise NotImplementedError



def quote_path(path):
    if path.startswith("~/"):
        # be careful to not quote shell special chars
        return '~/"%s"' % path[2:]
    else:
        return '"%s"' % path.replace('"', r'\"')

def quote_path_win(path):
    return '"%s"' % path.replace("/", "\\").replace('"', r'\"')


def wrap_for_sudo(command, sudo_prefix, as_user = Users.ADMIN):
    if not command:
        raise Exception("Empty command passed to execution routine")
        
    if not sudo_prefix:
        sudo_prefix = default_sudo_prefix
      
    # If as_user is the CURRENT then there's no need to sudo
    if as_user != Users.CURRENT:
        #sudo needs to use -u <user> for non admin
        if as_user != Users.ADMIN:
            sudo_user = "sudo -u %s" % as_user
            sudo_prefix = sudo_prefix.replace('sudo', sudo_user)

        if '/bin/sh' in sudo_prefix or '/bin/bash' in sudo_prefix:
            command = sudo_prefix + " \"" + command.replace('\\', '\\\\').replace('"', r'\"').replace('$','\\$') + "\""
        else:
            command = sudo_prefix + " /bin/bash -c \"" + command.replace('\\', '\\\\').replace('"', r'\"').replace('$','\\$') + "\""

    return command

###



class SSH(WbAdminSSH):
    def __init__(self, profile, password_delegate):
        self.mtx = threading.Lock()
        self.wrapped_connect(profile, password_delegate)

    def __del__(self):
        log_debug(_this_file, "Closing SSH connection\n")
        self.close()

    def get_contents(self, filename):
        self.mtx.acquire()
        try:
            ret = WbAdminSSH.get_contents(self, filename)
        finally:
            self.mtx.release()
        return ret

    def set_contents(self, filename, data):
        self.mtx.acquire()
        try:
            ret = WbAdminSSH.set_contents(self, filename, data)
        finally:
            self.mtx.release()
        return ret

    def exec_cmd(self, cmd, as_user = Users.CURRENT, user_password = None, output_handler = None, read_size = 128, get_channel_cb = None):
        output   = None
        retcode  = None

        self.mtx.acquire()
        log_debug3(_this_file, '%s:exec_cmd(cmd="%s", sudo=%s)\n' % (self.__class__.__name__, cmd, str(as_user)) )
        try:
            (output, retcode) = WbAdminSSH.exec_cmd(self, cmd,
                                            as_user=as_user,
                                            user_password=user_password,
                                            output_handler=output_handler,
                                            read_size = read_size,
                                            get_channel_cb = get_channel_cb)
            log_debug3(_this_file, '%s:exec_cmd(): Done cmd="%s"\n' % (self.__class__.__name__, cmd) )
        finally:
            self.mtx.release()

        return (output, retcode)

##===================================================================================================
## Local command execution
def local_run_cmd_linux(command, as_user = Users.CURRENT, user_password=None, sudo_prefix=default_sudo_prefix, output_handler=None, output_timeout=15):
    # wrap cmd
    if as_user != Users.CURRENT:
        command = wrap_for_sudo(command, sudo_prefix, as_user)

    debug_run_cmd = False
    if debug_run_cmd:
        log_debug2(_this_file, "local_run_cmd_linux: %s (as %s)\n" % (command, as_user))

    script = command.strip(" ")
    if not script:
        return None
    script_to_log = script

    script = "cd; " + script + " ; exit $?"
    result = None

    def read_nonblocking(fd, size, timeout=0, return_on_newline=False):
        import select
        data = []
        t = time.time()
        while len(data) < size:
            try:
                r, _, _ = select.select([fd], [], [], timeout)
            except select.error, e:
                if e.args[0] == 4:
                    timeout -= time.time() - t
                    if timeout < 0:
                        break
                    continue
                raise
            if not r:
                break
            data.append(fd.read(1))
            if return_on_newline and data[-1] == "\n":
                break
        return "".join(data)

    def read_nonblocking_until_nl_or(proc, fd, text, timeout=0):
        import select
        data = ""
        t = time.time()
        while time.time() - t < timeout:
            try:
                r, _, _ = select.select([fd], [], [], timeout - (time.time() - t))
            except select.error, e:
                if e.args[0] == 4:
                    continue
                raise
            if not r:
                break
        
            new_byte = fd.read(1)
            
            if new_byte:
                data += new_byte
                
                if data.endswith(text) or "\n" in data:
                    ndata = sanitize_sudo_output(data)
                    if ndata != data:
                        data = ndata
                        continue
                    break
            elif proc.poll() is not None:
                break
                
        return data

    # script should already have sudo
    child = subprocess.Popen(["/bin/bash", "-c", script], bufsize=0,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             close_fds=True)

    expect_sudo_failure = False
    if as_user != Users.CURRENT:
        # If sudo is being used, we need to input the password
        data = read_nonblocking_until_nl_or(child, child.stdout, "EnterPasswordHere", timeout=output_timeout)
        if data.endswith("EnterPasswordHere"):
            # feed the password
            if debug_run_cmd:
                log_debug2(_this_file, "local_run_cmd_linux: sending password to child...\n")
            child.stdin.write((user_password or "")+"\n")
            expect_sudo_failure = True # we could get a Sorry or the password prompt again
        else:
            log_debug(_this_file, "local_run_cmd_linux: was expecting sudo password prompt, but it never came\n")
            if output_handler and data:
                output_handler(data)

    if debug_run_cmd:
        log_debug2(_this_file, "local_run_cmd_linux: waiting for data...\n")
    read_size = 40
    return_on_newline = True
    while child.poll() is None:
        #t = time.time()
        # read 1KB from stdout, timeout in 15s.. at first time, read just enough to see if password prompt is there again
        current_text = read_nonblocking(child.stdout, read_size, output_timeout, return_on_newline)
        return_on_newline = False
        read_size = 1024
        if debug_run_cmd:
            log_debug2(_this_file, "local_run_cmd_linux: %s: read %i bytes from child [%s...]\n" % (script_to_log, len(current_text), current_text[:50]))

        # If Password prompt shows up again, it means the password we tried earlier was wrong.. so raise an exception
        if expect_sudo_failure and (current_text.find("EnterPasswordHere") >= 0 or current_text.find("Sorry, try again") >= 0):
            child.terminate()
            raise InvalidPasswordError("Incorrect password for sudo")
        else:
            # Not the password prompt
            expect_sudo_failure = False
            if output_handler and current_text:
                output_handler(current_text)

    
    # Try to read anything left, wait exit
    try:
        current_text, _ = child.communicate()
        if current_text and output_handler:
            output_handler(current_text)
    except:
        pass
    
    result = child.returncode
    if debug_run_cmd:
        log_debug2(_this_file, "local_run_cmd_linux: child returned %s\n" % result)
    log_debug3(_this_file, 'local_run_cmd_linux(): script="%s", ret=%s\n' % (script_to_log, result))
    return result


def local_run_cmd_windows(command, as_user=Users.CURRENT, user_password=None, sudo_prefix=None, output_handler=None):
    # wrap cmd
    retcode = 1

    if as_user != Users.CURRENT:

        # Starts the command execution listener
        listener = None

        # When the command output is needed, the command will be executed with the
        # helper script and the output listened on a socket connection
        if output_handler:
            # The TCPCommandListener is missing one thing: the way to turn it off
            # so can't be used yet
            #listener = TCPCommandListener(output_handler)
            listener = CustomCommandListener(output_handler)
            listener.start()
            
            helper_path = ntpath.join(os.getcwd(),App.get().get_resource_path("wbadminhelper.exe"))

            # Creates the command as a call to the bundled python 
            # - The path to the python helper which will receive additionally:
            #   - The port where the command listener is waiting for the helper response
            #   - The handshake to allow it to connect to the listener
            #   - The close_key so it can notify the listener when processing is done
            #   - The original command to be executed

            # Patch to ensure old OS calls get executed properly
            actual_command = command.split(' ')[0]
            if not actual_command in ['LISTDIR','GETFILE','GET_FREE_SPACE', 'CHECK_DIR_WRITABLE', 'CHECK_PATH_EXISTS', 'CREATE_DIRECTORY', 'CREATE_DIRECTORY_RECURSIVE', 'REMOVE_DIRECTORY', 'REMOVE_DIRECTORY_RECURSIVE','DELETE_FILE', 'COPY_FILE', 'GET_FILE_OWNER', 'GETFILE_LINES', 'EXEC']:
                command = "EXEC " + command
            cmdname = helper_path
            cmdparams = '%d %s %s %s' % (listener.port, listener.handshake, listener.close_key, command)
        else:
            cmdname = "cmd.exe"
            cmdparams = "/C" + command

        command = "%s %s" % (cmdname, cmdparams)

        try:
            from ctypes import c_int, WINFUNCTYPE, windll
            from ctypes.wintypes import HWND, LPCSTR, UINT
            prototype = WINFUNCTYPE(c_int, HWND, LPCSTR, LPCSTR, LPCSTR, LPCSTR, UINT)

            paramflags = (1, "hwnd", 0), (1, "operation", "runas"), (1, "file", cmdname), (1, "params", cmdparams), (1, "dir", None), (1, "showcmd", 0)
            SHellExecute = prototype(("ShellExecuteA", windll.shell32), paramflags)
            ret = SHellExecute()

            # If the user chooses to not allow privilege elevation for the operation
            # a PermissionDeniedError is launched
            if ret == 5:
                raise PermissionDeniedError("User did not accept privilege elevation")

            # Waits till everything has been received from the command
            if listener and ret != 5:
                listener.join()

                if listener.exit_status:
                    try:
                        helper_exception = eval(listener.exit_message)
                    except Exception, e:
                        # Some networking exceptions can't be evaluated
                        # So a runtime exception will be created on those cases
                        helper_exception = RuntimeError(listener.exit_message)
                    log_error(_this_file, "Exception received from Windows command helper executing %s %s: %s\n" % (cmdname, cmdparams, helper_exception))
                    raise helper_exception

            # > 32 is OK, < 32 is error code
            
            retcode = 1
            if ret > 32:
                retcode = 0
            else:
                if ret == 0:
                    log_error(_this_file, 'local_run_cmd_windows(): Out of memory executing "%s"\n' % command)
                else:
                    log_error(_this_file, 'local_run_cmd_windows(): Error %i executing "%s"\n' % (ret, command) )
            return retcode
        except Exception, e:
          # These errors will contain information probably sent by the helper so
          # they will be rethrow so they get properly displayed
          raise
    else:
        try:
            retcode = OSUtils.exec_command(command, output_handler)
        except Exception, e:
            import traceback
            log_error(_this_file, "Exception executing local command: %s: %s\n%s\n" % (command, e, traceback.format_exc()))
            retcode = 1
            #out_str = "Internal error: %s" % e

    return retcode


if platform.system() == "Windows":
    local_run_cmd = local_run_cmd_windows
else:
    local_run_cmd = local_run_cmd_linux

def local_get_cmd_output(command, as_user=Users.CURRENT, user_password=None):
    output = []
    output_handler = lambda line, l=output: l.append(line)
    rc = local_run_cmd(command=command, as_user=as_user, user_password=user_password, sudo_prefix=None, output_handler=output_handler)
    return ("\n".join(output), rc)

##===================================================================================================
## Process Execution


_process_ops_classes = []


class ProcessOpsBase(object):
    cmd_output_encoding = ""

    def __init__(self, **kwargs):
        pass

    def post_init(self):
        pass

    def expand_path_variables(self, path):
        return path

    def get_cmd_output(self, command, as_user=Users.CURRENT, user_password=None):
        output = []
        output_handler = lambda line, l=output: l.append(line)
        rc = self.exec_cmd(command, as_user, user_password, output_handler)
        return ("\n".join(output), rc)

    def list2cmdline(self, args):
        return None


class ProcessOpsNope(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return connect == 'none'

    def expand_path_variables(self, path):
        return path

    def exec_cmd(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        return None

    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        raise NotImplementedError("%s must implement spawn_process" % self.__class__.__name__)

    def get_cmd_output(self, command, as_user=Users.CURRENT, user_password=None):
        return ("", None)

_process_ops_classes.append(ProcessOpsNope)


class ProcessOpsLinuxLocal(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return connect == 'local' and (host in (wbaOS.linux, wbaOS.darwin) and target in (wbaOS.linux, wbaOS.darwin))

    def __init__(self, **kwargs):
        ProcessOpsBase.__init__(self, **kwargs)
        self.sudo_prefix= kwargs.get("sudo_prefix", default_sudo_prefix)

    def exec_cmd(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        return local_run_cmd_linux(command, as_user, user_password, self.sudo_prefix, output_handler)

    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        # wrap cmd
        if as_user != Users.CURRENT:
            command = wrap_for_sudo("nohup " + command + "&", self.sudo_prefix, as_user)
      
        script = command.strip(" ")
        if script is None or len(script) == 0:
            return None

        # Creates the process
        process = subprocess.Popen(script, stdin=subprocess.PIPE, shell=True, close_fds=True)
  
        # Passes the password if needed
        if as_user != Users.CURRENT:
            process.stdin.write(user_password + "\n")
            process.stdin.flush()
  
        return 0

    def list2cmdline(self, args):
        return " ".join([pipes.quote(a) or "''" for a in args])


_process_ops_classes.append(ProcessOpsLinuxLocal)


class ProcessOpsLinuxRemote(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        # host doesn't matter
        return connect == 'ssh' and target in (wbaOS.linux, wbaOS.darwin)

    def __init__(self, **kwargs): # Here should be at least commented list of args
        ProcessOpsBase.__init__(self, **kwargs)

        self.sudo_prefix= kwargs.get("sudo_prefix", default_sudo_prefix)
        self.ssh = kwargs["ssh"]

    def exec_cmd(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        #if not self.ssh:
        #    raise Exception("No SSH session active")

        if as_user != Users.CURRENT:
            command = wrap_for_sudo(command, self.sudo_prefix, as_user)

        def ssh_output_handler(chunk, handler):
            if "EnterPasswordHere" in chunk and as_user != Users.CURRENT:
                raise InvalidPasswordError("Invalid password for sudo")
            if chunk is not None and chunk != "":
                handler(chunk)
            
        if output_handler:
            handler = lambda chunk, h=output_handler: ssh_output_handler(chunk, h)
        else:
            handler = None

        if self.ssh:
            # output_handler taken by ssh.exec_cmd is different from the one used elsewhere
            dummy_text, ret = self.ssh.exec_cmd(command,
                    as_user=as_user, user_password=user_password,
                    output_handler=handler)
        else:
            ret = 1
            if output_handler:
                output_handler("No SSH connection is active")
            else:
                print("No SSH connection is active")
                log_info(_this_file, 'No SSH connection is active\n')

        return ret

    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        command.strip()

        # Adds the spawning options
        command = "nohup " + command + " &"

        self.exec_cmd(command, as_user, user_password, output_handler)


    def list2cmdline(self, args):
        return " ".join([pipes.quote(a) or "''" for a in args])

_process_ops_classes.append(ProcessOpsLinuxRemote)




WIN_REG_QUERY_PROGRAMFILES = 'reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion /v "ProgramFilesDir"'
WIN_REG_QUERY_PROGRAMFILES_x86 = 'reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion /v "ProgramFilesDir (x86)"'

WIN_PROGRAM_FILES_VAR = "%ProgramFiles%"
WIN_PROGRAM_FILES_X86_VAR = "%ProgramFiles(x86)%"
WIN_PROGRAM_FILES_X64_VAR = "%ProgramW6432%"
WIN_PROGRAM_DATA_VAR = "%ProgramData%"


class ProcessOpsWindowsLocal(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return (host == wbaOS.windows and target == wbaOS.windows and connect in ('wmi', 'local'))

    def __init__(self, **kwargs):
        ProcessOpsBase.__init__(self, **kwargs)
        self.target_shell_variables = {}

    def post_init(self):
        self.fetch_windows_shell_info()

    def exec_cmd(self, command, as_user, user_password, output_handler=None):
        return local_run_cmd_windows(command, as_user, user_password, None, output_handler)

    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        try:
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(command, shell=True, close_fds = True, creationflags=DETACHED_PROCESS)
            #process = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, shell=True)
        except Exception, exc:
            import traceback
            log_error(_this_file, "Error executing local Windows command: %s: %s\n%s\n" % (command, exc, traceback.format_exc()))
            #out_str = "Internal error: %s"%exc

    def expand_path_variables(self, path):
        """
        Expand some special variables in the path, such as %ProgramFiles% and %ProgramFiles(x86)% in
        Windows. Uses self.target_shell_variables for the substitutions, which should have been
        filled when the ssh connection to the remote host was made.
        """
        for k, v in self.target_shell_variables.iteritems():
            path = path.replace(k, v)
        return path

    def fetch_windows_shell_info(self):
        # get some info from the remote shell
        result, code = self.get_cmd_output("chcp.com")
        if code == 0:
            result = result.strip(" .\r\n").split()
            if len(result) > 0:
                  self.cmd_output_encoding = "cp" + result[-1]
        else:
            log_warning(_this_file, '%s.fetch_windows_shell_info(): WARNING: Unable to determine codepage from shell: "%s"\n' % (self.__class__.__name__, str(result)) )

            # some ppl don't have the system32 dir in PATH for whatever reason, check if that's the case
            _, code = self.get_cmd_output("ver")
            if code != 0:
                # assume this is not Windows
                raise RuntimeError("Target host is configured as Windows, but seems to be a different OS. Please review the connection settings.")
            raise RuntimeError("Unable to execute command chcp. Please make sure that the C:\\Windows\\System32 directory is in your PATH environment variable.")

        result, code = self.get_cmd_output("echo %PROCESSOR_ARCHITECTURE%")
        if result:
            result = result.strip()

        ProgramFilesVar = None
        x86var = None
        if result != "x86":#we are on x64 win in x64 mode
            x86var = WIN_PROGRAM_FILES_X86_VAR
            ProgramFilesVar = WIN_PROGRAM_FILES_VAR
        else:
            result, code = self.get_cmd_output("echo %PROCESSOR_ARCHITEW6432%")
            if result:
                result = result.strip()
            if result == "%PROCESSOR_ARCHITEW6432%":#we are on win 32
                x86var = WIN_PROGRAM_FILES_VAR
                ProgramFilesVar = WIN_PROGRAM_FILES_VAR
            else:#32bit app on x64 win
                x86var = WIN_PROGRAM_FILES_VAR
                ProgramFilesVar = WIN_PROGRAM_FILES_X64_VAR

        result, code = self.get_cmd_output("echo "+ ProgramFilesVar)
        if code == 0:
            self.target_shell_variables["%ProgramFiles%"] = result.strip("\r\n")
            if ProgramFilesVar != "%ProgramFiles%":
                self.target_shell_variables[ProgramFilesVar] = result.strip("\r\n")
        else:
            print "WARNING: Unable to fetch ProgramFiles value in Windows machine: %s"%result
            log_warning(_this_file, '%s.fetch_windows_shell_info(): WARNING: Unable to fetch ProgramFiles value in Windows machine: "%s"\n' % (self.__class__.__name__, str(result)) )

        # this one only exists in 64bit windows
        result, code = self.get_cmd_output("echo "+ x86var)
        if code == 0:
            self.target_shell_variables["%ProgramFiles(x86)%"] = result.strip("\r\n")
        else:
            print "WARNING: Unable to fetch ProgramFiles(x86) value in local Windows machine: %s"%result
            log_warning(_this_file, '%s.fetch_windows_shell_info(): WARNING: Unable to fetch ProgramFiles(x86) value in local Windows machine: "%s"\n' % (self.__class__.__name__, str(result)) )

        # Fetches the ProgramData path
        result, code = self.get_cmd_output("echo "+ WIN_PROGRAM_DATA_VAR)
        if code == 0:
            self.target_shell_variables[WIN_PROGRAM_DATA_VAR] = result.strip("\r\n")
        else:
            # If not found, it will use the %ProgramFiles% variable value
            self.target_shell_variables[WIN_PROGRAM_DATA_VAR] = self.target_shell_variables[ProgramFilesVar]
            print "WARNING: Unable to fetch ProgramData value in local Windows machine: %s, using ProgramFiles path instead: %s" % (result, self.target_shell_variables[WIN_PROGRAM_DATA_VAR])
            log_warning(_this_file, '%s.fetch_windows_shell_info(): WARNING: Unable to fetch ProgramData value in local Windows machine: "%s"\n' % (self.__class__.__name__, str(result)) )

        log_debug(_this_file, '%s.fetch_windows_shell_info(): Encoding: "%s", Shell Variables: "%s"\n' % (self.__class__.__name__, self.cmd_output_encoding, str(self.target_shell_variables)))

    def list2cmdline(self, args):
          return subprocess.list2cmdline(args)


_process_ops_classes.append(ProcessOpsWindowsLocal)


class ProcessOpsWindowsRemoteSSH(ProcessOpsWindowsLocal):
    @classmethod
    def match(cls, (host, target, connect)):
        # host doesn't matter
        return (target == wbaOS.windows and connect == 'ssh')

    def __init__(self, **kwargs):
        ProcessOpsWindowsLocal.__init__(self, **kwargs)

        self.ssh = kwargs["ssh"]


    def post_init(self):
        if self.ssh:
            self.fetch_windows_shell_info()


    def exec_cmd(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        command = "cmd.exe /c " + command

        if not self.ssh:
            raise Exception("No SSH session active")

        def ssh_output_handler(chunk, handler):
            if chunk is not None and chunk != "":
                handler(chunk)
            #else:
            #    loop = False

        if output_handler:
            handler = lambda chunk, h=output_handler: ssh_output_handler(chunk, h)
        else:
            handler = None

        # output_handler taken by ssh.exec_cmd is different from the one used elsewhere
        dummy_text, ret = self.ssh.exec_cmd(command,
                as_user=as_user, user_password=user_password,
                output_handler=handler)
        return ret


    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        raise NotImplementedError("%s must implement spawn_process" % self.__class__.__name__)


    def list2cmdline(self, args):
          return subprocess.list2cmdline(args)

_process_ops_classes.append(ProcessOpsWindowsRemoteSSH)



##===================================================================================================
## File Operations

_file_ops_classes = []

class FileOpsNope(object):
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "none"

    def __init__(self, process_ops, ssh = None, target_os = None):
        pass

    def save_file_content(self, filename, content, as_user = Users.CURRENT, user_password = None):
        pass

    def save_file_content_and_backup(self, filename, content, backup_extension, as_user = Users.CURRENT, user_password = None):
        pass

    def get_file_content(self, filename, as_user = Users.CURRENT, user_password = None, skip_lines=0):
        return ""

    def _copy_file(self, source, dest, as_user = Users.CURRENT, user_password = None): # not used externally
        pass

    def check_dir_writable(self, path, as_user=Users.CURRENT, user_password=None):
        return False

    def file_exists(self, path, as_user = Users.CURRENT, user_password = None):
        return False

    def get_file_owner(self, path, as_user = Users.CURRENT, user_password = None):
        return False
        
    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        pass

    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        pass

    def get_available_space(self, path, as_user = Users.CURRENT, user_password = None):
        return False

    # Return format is list of entries in dir (directories go first, each dir name is follwoed by /)
    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False): # base operation to build file_exists and remote file selector
        return []

    def get_owner(self, path): # base operation to build file_exists and remote file selector
        return []
_file_ops_classes.append(FileOpsNope)

class FileOpsLinuxBase(object):
    def __init__(self, process_ops, ssh=None, target_os = None):
        self.process_ops = process_ops
        self.ssh = ssh
        self.target_os = target_os
        
    # Exception Handling will vary on local and remote
    def raise_exception(self, message, custom_messages = {}):
        pass
        
    def file_exists(self, filename, as_user=Users.CURRENT, user_password=None):
        res = self.process_ops.exec_cmd('test -e ' + quote_path(filename),
                            as_user,
                            user_password,
                            output_handler = lambda line:None)
        return res == 0
    
    def get_available_space(self, path, as_user=Users.CURRENT, user_password=None):
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd("LC_ALL=C df -Ph %s" % quote_path(path),
                            as_user,
                            user_password,
                            output_handler = output.write)

        output = sanitize_sudo_output(output.getvalue()).strip()
        
        available = "Could not determine"
        if res == 0:
            tokens = output.split("\n")[-1].strip().split()
            available = "%s of %s available" % (tokens[3], tokens[1])
        
        return available
        
    def get_file_owner(self, path, as_user = Users.CURRENT, user_password = None):
        if self.target_os == wbaOS.linux:
          command = 'LC_ALL=C stat -c %U '
        else:
          command = 'LC_ALL=C /usr/bin/stat -f "%Su" '
      
        output = StringIO.StringIO()
        command = command + quote_path(path)
        
        res = self.process_ops.exec_cmd(command,
                            as_user,
                            user_password,
                            output_handler= output.write)
            
        output = sanitize_sudo_output(output.getvalue()).strip()
        if res != 0:
            self.raise_exception(output)
        
        return output      
        
    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        output = StringIO.StringIO()
        if with_owner:
            command = "/bin/mkdir %s && chown %s %s" % (quote_path(path), with_owner, quote_path(path))
        else:
            command = "/bin/mkdir %s" % (quote_path(path))
            
        res = self.process_ops.exec_cmd(command,
                                        as_user   = as_user,
                                        user_password = user_password,
                                        output_handler = output.write)

        if res != 0:
            output = sanitize_sudo_output(output.getvalue()).strip()
            self.raise_exception(output)      
                
    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        head, tail = splitpath(path)
        if not tail:
            head, tail = splitpath(head)
        if head and tail and not self.file_exists(head):
            try:
                self.create_directory_recursive(head, as_user, user_password, with_owner)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise

        self.create_directory(path, as_user, user_password, with_owner)

    def remove_directory(self, path, as_user = Users.CURRENT, user_password = None):
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd('/bin/rmdir ' + quote_path(path),
                                        as_user   = as_user,
                                        user_password = user_password,
                                        output_handler = output.write)

        if res != 0:
            output = sanitize_sudo_output(output.getvalue()).strip()
            self.raise_exception(output)

    def remove_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None):
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd('/bin/rm -R ' + quote_path(path),
                                        as_user   = as_user,
                                        user_password = user_password,
                                        output_handler = output.write)

        if res != 0:
            output = sanitize_sudo_output(output.getvalue()).strip()
            self.raise_exception(output)

    def delete_file(self, path, as_user = Users.CURRENT, user_password = None):
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd("/bin/rm " + quote_path(path),
                                        as_user   = as_user,
                                        user_password = user_password,
                                        output_handler = output.write)

        if res != 0:
            output = sanitize_sudo_output(output.getvalue()).strip()
            self.raise_exception(output)

    def get_file_content(self, filename, as_user = Users.CURRENT, user_password = None, skip_lines=0): # may raise IOError
        command = ''
        output = StringIO.StringIO()

        if skip_lines == 0:
            command = 'cat %s' % quote_path(filename)
        else:
            command = 'tail -n+%d %s' % (skip_lines+1, quote_path(filename))

        res = self.process_ops.exec_cmd(command,
                                        as_user   = as_user,
                                        user_password = user_password,
                                        output_handler = output.write)

                                        
        output = sanitize_sudo_output(output.getvalue()).strip()
        
        if res != 0:
            self.raise_exception(output)

        return output
        
    def _copy_file(self, source, dest, as_user = Users.CURRENT, user_password = None):
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd("LC_ALL=C /bin/cp " + quote_path(source) + " " + quote_path(dest),
                      as_user   = as_user,
                      user_password = user_password,
                      output_handler = output.write)

        if res != 0:
            output = sanitize_sudo_output(output.getvalue()).strip()
            self.raise_exception(output)
        
    def check_dir_writable(self, path, as_user=Users.CURRENT, user_password=None):
        ret_val = True
        
        output = StringIO.StringIO()
        
        path = quote_path(path)
        command = "test -e %s;_fe=$?;test -d %s;_fd=$?;test -w %s;echo $_fe$_fd$?" % (path, path, path)
        self.process_ops.exec_cmd(command,
                                  as_user,
                                  user_password,
                                  output_handler = output.write)

        # The validation will depend on the output and not the returned value
        output = sanitize_sudo_output(output.getvalue()).strip()
      
        log_debug(_this_file, 'check_dir_writable :%s\n' % output)
        
        if len(output) == 3:
            if output[0] == '1':
                raise OSError(errno.ENOENT, 'The indicated path does not exist')
            elif output[1] == '1':
                raise OSError(errno.ENOTDIR, 'The indicated path is not a directory')
            elif output[2] == '1':
                ret_val = False
        else:
          raise Exception('Unable to verify directory is writable : %s' % output)

        return ret_val        
        
    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False): 
        file_list = []
        if include_size:
            command = '/bin/ls -l -p %s | awk \'{ print $5,$9 }\' ; exit ${PIPESTATUS[0]}' % quote_path(path)
        else:
            command = '/bin/ls -1 -p %s' % quote_path(path)
            
        output = StringIO.StringIO()
        res = self.process_ops.exec_cmd(command,
                                        as_user,
                                        user_password,
                                        output_handler = output.write)
        output = sanitize_sudo_output(output.getvalue().strip())
        if res != 0:
            custom_messages = {
                                errno.ENOENT:"The indicated path does not exist",
                                errno.ENOTDIR:"The indicated path is not a directory",
                                errno.EACCES:"Permission denied accessing %s" % path
                              }
        
            self.raise_exception(output, custom_messages)
        else:
            try:
                if include_size:
                    file_list = [(f, int(s)) for s, f in [s.strip().split(" ", 1) for s in output.split("\n")]]
                else:
                    file_list = [s.strip() for s in output.split("\n")]
                    
            except Exception, e:
                log_error(_this_file, "%s: Could not parse output of remote ls %s command: '%s'\n"% (e, path, output))
    
        return file_list        
        
    def save_file_content(self, filename, content, as_user = Users.CURRENT, user_password = None):        
        pass
        
    def _set_file_content(self, path, content):
        pass
        
    def _create_temp_file(self, content):
        pass

    def save_file_content_and_backup(self, filename, content, backup_extension, as_user = Users.CURRENT, user_password = None):
        log_debug(_this_file, '%s: Saving file "%s" with backup (sudo="%s")\n' % (self.__class__.__name__, filename, str(as_user)) )
        # Checks if the target folder is writable
        target_dir = posixpath.split(filename)[0]
        
        if self.check_dir_writable(target_dir, as_user, user_password):
            # Creates a backup of the existing file... if any
            if backup_extension and self.file_exists(filename, as_user, user_password):
                log_debug(_this_file, '%s: Creating backup of "%s" to "%s"\n' %  (self.__class__.__name__, filename, filename+backup_extension))
                self._copy_file(source = filename, dest = filename + backup_extension,
                                as_user = as_user, user_password = user_password)
                                    
            if as_user != Users.CURRENT:
                temp_file = self._create_temp_file(content)
                log_debug(_this_file, '%s: Wrote file contents to tmp file "%s"\n' %  (self.__class__.__name__, temp_file) )
                
                         
                log_debug(_this_file, '%s: Copying over tmp file to final filename using sudo: %s -> %s\n' % (self.__class__.__name__, temp_file, filename) )
                self._copy_file(source = temp_file, dest = filename, 
                                as_user = Users.ADMIN, user_password = user_password)
                    
                log_debug(_this_file, '%s: Copying file done\n' % self.__class__.__name__)
                
                # If needed changes the ownership of the new file to the requested user
                if as_user != Users.ADMIN:
                
                    # TODO: Does this need any validation being executed by root??
                    self.process_ops.exec_cmd("chown %s %s" % (as_user, quote_path(filename)),
                                  as_user   = Users.ADMIN,
                                  user_password = user_password)
                                  
                self.delete_file(temp_file)
            else:
                log_debug(_this_file, '%s: Saving file...\n' % self.__class__.__name__)
                self._create_file(filename, content)
                    
        else:
            raise PermissionDeniedError("Cannot write to target folder: %s" % target_dir)
        
        
            
#===============================================================================
# The local file ops are context free, meaning that they
# do not need active shell session to work on
# local  all  plain
#   save_file_content  - python
#   get_file_content   - python
#   copy_file          - python
#   get_dir_access     - python (returns either rw or ro or none)
#   listdir            - python
# local  all  sudo derives from local-all-plain
#   save_file_content  - shell
#   get_file_content   - python (maybe sudo if file is 0600)
#   copy_file          - shell
#   get_dir_access     - python (returns either rw or ro or none)
#   listdir            - python/shell(for ro-dirs)
class FileOpsLocalUnix(FileOpsLinuxBase):
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "local" and target_os in (wbaOS.linux, wbaOS.darwin)

    process_ops = None
    def __init__(self, process_ops, ssh=None, target_os = None):
        FileOpsLinuxBase.__init__(self, process_ops, ssh, target_os)

    # Still need to differentiate whether it is an OSError or an IOError
    def raise_exception(self, message, custom_messages = {}):
        for code, name in errno.errorcode.iteritems():
            if os.strerror(code) in message:
                if code == errno.EACCES:
                    raise PermissionDeniedError(custom_messages.get(code, message))
                
                raise OSError(code, custom_messages.get(code, message))
    
        raise Exception(custom_messages.get(None, message))
        
    # content must be a string
    def save_file_content(self, filename, content, as_user = Users.CURRENT, user_password = None):
        self.save_file_content_and_backup(filename, content, None, as_user, user_password)

    def _create_file(self, path, content):
        try:
            f = open(path, 'w')
            f.write(content)
            f.close()
        except (IOError, OSError), err:
            if err.errno == errno.EACCES:
                raise PermissionDeniedError("Could not open file %s for writing" % path)
            raise err

    def _create_temp_file(self, content):
        tmp = tempfile.NamedTemporaryFile(delete = False)
        tmp_name = tmp.name

        try:
            log_debug(_this_file, '%s: Writing file contents to tmp file "%s"\n' %  (self.__class__.__name__, tmp_name) )
            tmp.write(content)
            tmp.flush()
        except Exception, exc:
            log_error(_this_file, '%s: Exception caught: %s\n' % (self.__class__.__name__, str(exc)) )
            if tmp:
                tmp.close()
            raise
            
        return tmp_name


    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_user = Users.CURRENT, user_password = None, skip_lines=0):
        if as_user == Users.CURRENT:
            try:
                f = open(filename, 'r')
            except (IOError, OSError), e:
                if e.errno == errno.EACCES:
                    raise PermissionDeniedError("Can't open file '%s'" % filename)
                raise e

            if skip_lines > 0:
                #unused last_skipped_line = ""
                skipped = 0
                lines = []
                for line in f:
                    if skipped < skip_lines:
                        #unused last_skipped_line = "%d - %s\n" % (skipped, line)
                        pass
                    else:
                        lines.append(line.rstrip())

                    skipped = skipped + 1
                 
                cont = "\n".join(lines)
            else:
                cont = f.read()

            f.close()
        else:
            cont = FileOpsLinuxBase.get_file_content(self, filename, as_user, user_password, skip_lines)

        return cont


    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if as_user == Users.CURRENT:
            if with_owner is not None:
                raise PermissionDeniedError("Cannot set owner of directory %s" % path)
                
            FileUtils.create_directory(path)
        else:
            FileOpsLinuxBase.create_directory(self, path, as_user, user_password, with_owner)

    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if as_user == Users.CURRENT:
            if with_owner is not None:
                raise PermissionDeniedError("Cannot set owner of directory %s" % path)
                
            FileUtils.create_directory_recursive(path)
        else:
            FileOpsLinuxBase.create_directory_recursive(self, path, as_user, user_password, with_owner)

    def delete_file(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            FileUtils.delete_file(path)                   
        else:
            FileOpsLinuxBase.delete_file(self, path, as_user, user_password)


    def _copy_file(self, source, dest, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            FileUtils.copy_file(source, dest)            
        else:
            FileOpsLinuxBase._copy_file(self, source, dest, as_user, user_password)

    # Return format is list of entries in dir (directories go first, each dir name is followed by /)
    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False): # base operation to build file_exists and remote file selector
        file_list = []
        if as_user == Users.CURRENT: 
            FileUtils.list_dir(path, include_size, lambda l, list = file_list: file_list.append(l))
            
            if include_size:
              file_list = [(f, int(s)) for s, f in [s.strip().split(" ", 1) for s in file_list]]
            else:
              file_list = [s.strip() for s in file_list]
        else:
            file_list = FileOpsLinuxBase.listdir(self, path, as_user, user_password, include_size)
                    
        return file_list

_file_ops_classes.append(FileOpsLocalUnix)


#===============================================================================
class FileOpsLocalWindows(object): # Used for remote as well, if not using sftp
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method in ("local", "wmi") and target_os == wbaOS.windows


    def __init__(self, process_ops, ssh=None, target_os = None):
        self.process_ops = process_ops
        self.ssh = ssh
        self.target_os = target_os
    
        tempdir, rc= self.process_ops.get_cmd_output("echo %temp%")
        if tempdir and tempdir.strip():
            self.tempdir = tempdir.strip()

    def exec_helper_command(self, command, result_mode, as_user, user_password):
        """
        This function is in charge of executing a command through the admin helper
        and processes the result depending on the result_mode parameter

        It was created to avoid having a result parsing on each function called
        through the admin helper and simplify code
        """

        ret_val = None
        out = []
        res = self.process_ops.exec_cmd(command,
                            as_user,
                            user_password,
                            output_handler = lambda line, l = out:l.append(line))

        if res == 0:
            if result_mode == FunctionType.Boolean:
                # Only booleans are expected,  if an error 
                # occurred it has been already raised on an exception
                if out[0] == 'True':
                    ret_val = True
                elif out[0] == 'False':
                    ret_val = False

            elif result_mode == FunctionType.Success:
                # nothing to do, is expected to succeed, if an error
                # happened, it has been already raised on an exception
                pass

            elif result_mode == FunctionType.String:
                ret_val = out[0]

            elif result_mode == FunctionType.Data:
                ret_val = out
                    
        else:
            raise Exception('Error executing helper command : %s' % command)

        return ret_val

        
    def get_file_owner(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            ret_val = FileUtils.get_file_owner(path)
        else:
            ret_val = self.exec_helper_command('GET_FILE_OWNER %s' % path, FunctionType.String, as_user, user_password)

        return ret_val


    def check_dir_writable(self, path, as_user=Users.CURRENT, user_password=None):
        if as_user == Users.CURRENT:
            ret_val = FileUtils.check_dir_writable(path)
        else:
            ret_val = self.exec_helper_command('CHECK_DIR_WRITABLE %s' % path, FunctionType.Boolean, as_user, user_password)
          
        return ret_val

    def file_exists(self, filename, as_user = Users.CURRENT, user_password=None):
        if as_user == Users.CURRENT:
            ret_val = FileUtils.check_path_exists(filename)
        else:
            ret_val = self.exec_helper_command('CHECK_PATH_EXISTS %s' % filename, FunctionType.Boolean, as_user, user_password)

        return ret_val

    def get_available_space(self, path, as_user=Users.CURRENT, user_password=None):
        if as_user == Users.CURRENT:
            ret_val = FileUtils.get_free_space(path)
        else:
            try:
                ret_val = self.exec_helper_command('GET_FREE_SPACE %s' % path, FunctionType.String, as_user, user_password)
            except Exception:
                ret_val = 'Could not determine'

        return ret_val

    # content must be a string
    def save_file_content(self, filename, content, as_user = Users.CURRENT, user_password = None):
        self.save_file_content_and_backup(filename, content, None, as_user, user_password)


    def save_file_content_and_backup(self, filename, content, backup_extension, as_user = Users.CURRENT, user_password = None):
        log_debug(_this_file, '%s: Saving file "%s" with backup (sudo="%s")\n' % (self.__class__.__name__, filename, str(as_user)) )

        # First saves the content to a temporary file
        try:
            tmp = tempfile.NamedTemporaryFile("w+b", delete = False)
            tmp_name = tmp.name
            log_debug(_this_file, '%s: Writing file contents to tmp file "%s" as %s\n' % (self.__class__.__name__, tmp_name, as_user) )
            tmp.write(content)
            tmp.close()

            backup_file = ""
            if backup_extension and ntpath.exists(filename):
                backup_file = filename + backup_extension

            if as_user != Users.CURRENT:
                if backup_file:
                    copy_command = 'COPY_FILE %s>%s>%s' % (tmp_name, filename, backup_file)
                else:
                    copy_command = 'COPY_FILE %s>%s' % (tmp_name, filename)

                self.exec_helper_command(copy_command, FunctionType.Success, as_user, user_password)
            else:
                FileUtils.copy_file(tmp_name, filename, backup_file)

        except Exception, exc:
            log_error(_this_file, '%s: Exception caught: %s\n' % (self.__class__.__name__, str(exc)) )
            raise

    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_user = Users.CURRENT, user_password = None, skip_lines=0):

        lines = []
        if as_user == Users.CURRENT: 
            FileUtils.get_file_lines(filename, skip_lines, lambda l, list = lines: list.append(l))
        else:
            lines = self.exec_helper_command('GETFILE_LINES %d %s' % (skip_lines, filename), FunctionType.Data, as_user, user_password)

        return ''.join(lines)


    def _copy_file(self, source, dest, as_user = Users.CURRENT, user_password = None): # not used externally, but in superclass
        if as_user == Users.CURRENT:
            error = FileUtils.copy_file(source, dest)
            if error:
                raise Exception(error)
        else:
            self.exec_helper_command('COPY_FILE %s>%s' % (source, dest), FunctionType.Success, as_user, user_password)


    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if with_owner is not None:
            raise PermissionDeniedError("Changing owner of directory not supported in Windows" % path)

        if as_user == Users.CURRENT:
            FileUtils.create_directory(path)
        else:
            self.exec_helper_command('CREATE_DIRECTORY %s' % path, FunctionType.Success, as_user, user_password)


    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if with_owner is not None:
            raise PermissionDeniedError("Changing owner of directory not supported in Windows" % path)

        if as_user == Users.CURRENT:
            FileUtils.create_directory_recursive(path)
        else:
            self.exec_helper_command('CREATE_DIRECTORY_RECURSIVE %s' % path, FunctionType.Success, as_user, user_password)

    def remove_directory(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            FileUtils.remove_directory(path)
        else:
            self.exec_helper_command('REMOVE_DIRECTORY %s' % path, FunctionType.Success, as_user, user_password)

    def remove_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            FileUtils.remove_directory_recursive(path)
        else:
            self.exec_helper_command('REMOVE_DIRECTORY_RECURSIVE %s' % path, FunctionType.Success, as_user, user_password)

    def delete_file(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            FileUtils.delete_file(path)
        else:
            self.exec_helper_command('DELETE_FILE %s' % path, FunctionType.Success, as_user, user_password)


    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False):
        file_list = []
        if as_user == Users.CURRENT: 
            FileUtils.list_dir(path, include_size, lambda l, list = file_list: file_list.append(l))
        else:
            file_list = self.exec_helper_command('LISTDIR %s %s' % ("1" if include_size else "0", path), FunctionType.Data, as_user, user_password)

        if include_size:
          file_list = [(f, int(s)) for s, f in [s.strip().split(" ", 1) for s in file_list]]
        else:
          file_list = [s.strip() for s in file_list]

        return file_list



_file_ops_classes.append(FileOpsLocalWindows)

#===============================================================================
# This remote file ops are shell dependent, they must be
# given active ssh connection, possibly, as argument
# remote unix sudo/non-sudo
#   save_file_content  - shell
#   get_file_content   - shell
#   copy_file          - shell
#   get_dir_access     - shell(returns either rw or ro or none)
#   listdir            - shell(for ro-dirs)
class FileOpsRemoteUnix(FileOpsLinuxBase):
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "ssh" and target_os in (wbaOS.linux, wbaOS.darwin)

    def __init__(self, process_ops, ssh, target_os = None):
        FileOpsLinuxBase.__init__(self, process_ops, ssh, target_os)

    # Still need to differentiate whether it is an OSError or an IOError
    def raise_exception(self, message, custom_messages = {}):
        if 'Permission denied' in message:
            raise PermissionDeniedError(custom_messages.get(errno.EACCES, message))
        elif 'No such file or directory' in message:
            raise OSError(errno.ENOENT, custom_messages.get(errno.ENOENT, message))
        elif 'Not a directory' in message:
            raise OSError(errno.ENOTDIR, custom_messages.get(errno.ENOTDIR, message))
        elif 'Directory not empty' in message:
            raise OSError(errno.ENOTEMPTY, custom_messages.get(errno.ENOTEMPTY, message))
        elif 'No SSH connection is active' in message:
            stack = inspect.stack()
            if len(stack) > 1:
                function = stack[1][3]
                message = "Unable to perform function %s. %s" % (function, message)
            raise Exception(message)
        else:        
            raise Exception(custom_messages.get(None, message))

       
    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if as_user == Users.CURRENT:
            if with_owner is not None:
                raise PermissionDeniedError("Cannot set owner of directory %s" % path)
                
            try:
                self.ssh.mkdir(path)
            except (IOError, OSError), err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not create directory %s" % path)
                raise err
        else:
            FileOpsLinuxBase.create_directory(self, path, as_user, user_password, with_owner)

    def delete_file(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            try:
                self.ssh.remove(path)
            except (IOError, OSError), err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not delete file %s" % path)
                raise err
        else:
            FileOpsLinuxBase.delete_file(self, path, as_user, user_password)
    
    #-----------------------------------------------------------------------------
    def save_file_content(self, filename, content, as_user = Users.CURRENT, user_password = None):
        self.save_file_content_and_backup(filename, content, None, as_user, user_password)

    #-----------------------------------------------------------------------------
    
    def _create_file(self, path, content):
        
        try:
            self.ssh.set_contents(path, content)
        except (IOError, OSError), err:
            if err.errno == errno.EACCES:
                raise PermissionDeniedError("Could not open file %s for writing" % path)
            raise err
    
    def _create_temp_file(self, content):
        tmpfilename = ''
        if self.ssh is not None:
            homedir, status = self.process_ops.get_cmd_output("echo ~")
            if type(homedir) is unicode:
                homedir = homedir.encode("utf8")
            if type(homedir) is str:
                homedir = homedir.strip(" \r\t\n")
            else:
                homedir = None
            log_debug2(_this_file, '%s: Got home dir: "%s"\n' % (self.__class__.__name__, homedir) )

            if not homedir:
                raise Exception("Unable to get path for remote home directory")

            tmpfilename = homedir + "/.wba.temp"
            
            self.ssh.set_contents(tmpfilename, content)
        else:
            raise Exception("No SSH session active, cannot save file remotely")
        
        return tmpfilename
        

_file_ops_classes.append(FileOpsRemoteUnix)


#===============================================================================
# remote win sudo/non-sudo
#   save_file_content  - sftp
#   get_file_content   - sftp
#   copy_file          - sftp
#   get_dir_access     - sftp(returns either rw or ro or none)
#   listdir            - sftp(for ro-dirs)
class FileOpsRemoteWindows(object):
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "ssh" and target_os == wbaOS.windows

    def __init__(self, process_ops, ssh, target_os):
        self.process_ops = process_ops
        self.ssh = ssh

    def file_exists(self, filename, as_user=Users.CURRENT, user_password=None):
        if self.ssh:
            try:
                return self.ssh.file_exists(filename)
            except IOError:
                raise
        else:
            print "Attempt to read remote file with no ssh session"
            log_error(_this_file, '%s: Attempt to read remote file with no ssh session\n' % self.__class__.__name__)
            import traceback
            traceback.print_stack()
            raise Exception("Cannot read remote file without an SSH session")
        return False

    def get_available_space(self, path, as_user=Users.CURRENT, user_password=None):
        out = []        

        res = self.process_ops.exec_cmd('dir %s' % quote_path(path),
                            as_user,
                            user_password,
                            output_handler = lambda line, l = out:l.append(line))

        available = "Could not determine"
        if res == 0 and len(out):
            measures = ['B', 'KB', 'MB', 'GB', 'TB']
            tokens = out[0].strip().split("\n")[-1].strip().split()
            
            total = float(tokens[2].replace(",",""))
            index = 0
            while index < len(measures) and total > 1024:
                total = total / 1024
                index = index + 1


            available = "%.2f %s available" % (total, measures[index])
        
        return available

    def create_directory(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        if with_owner is not None:
            raise PermissionDeniedError("Changing owner of directory not supported in Windows" % path)

        if as_user == Users.CURRENT:
            try:
                self.ssh.mkdir(path)
            except OSError, err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not create directory %s" % path)
                raise err
        else:
            command = wrap_for_sudo('mkdir ' + quote_path_win(path), self.process_ops.sudo_prefix, as_user)
            out, ret = self.ssh.exec_cmd(command, as_user, user_password)
            if ret != 0:
                raise RuntimeError(out)

    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None, with_owner=None):
        head, tail = splitpath(path)
        if not tail:
            head, tail = splitpath(head)
        if head and tail and not self.file_exists(head):
            try:
                self.create_directory_recursive(head, as_user, user_password, with_owner)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise

        self.create_directory(path, as_user, user_password, with_owner)

    def remove_directory(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            try:
                self.ssh.rmdir(path)
            except OSError, err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not remove directory %s" % path)
                raise err
        else:
            command = wrap_for_sudo('rmdir ' + quote_path_win(path), self.process_ops.sudo_prefix, as_user)

            out, ret = self.ssh.exec_cmd(command, as_user, user_password)
            if ret != 0:
                raise RuntimeError(out)

    def remove_directory_recursive(self, path, as_user = Users.CURRENT, user_password = None):
        command = wrap_for_sudo('rmdir %s /s /q' % quote_path_win(path), self.process_ops.sudo_prefix, as_user)

        out, ret = self.ssh.exec_cmd(command, as_user, user_password)
        if ret != 0:
            raise RuntimeError(out)

    def delete_file(self, path, as_user = Users.CURRENT, user_password = None):
        if as_user == Users.CURRENT:
            try:
                self.ssh.remove(path)
            except OSError, err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not delete file %s" % path)
                raise err
        else:
            command = wrap_for_sudo('del ' + quote_path_win(path), self.process_ops.sudo_prefix, as_user)
            out, ret = self.ssh.exec_cmd(command, as_user, user_password)
            if ret != 0:
                raise RuntimeError(out)

    def save_file_content_and_backup(self, path, content, backup_extension, as_user = Users.CURRENT, user_password = None):
        # Check if dir, where config file will be stored is writable
        dirname, filename = ntpath.split(path)

        if as_user == Users.CURRENT:
            if not self.check_dir_writable(dirname.strip(" \r\t\n")):
                raise PermissionDeniedError("Cannot write to directory %s" % dirname)

        if self.ssh is not None:
            ## Get temp dir for using as tmpdir
            tmpdir, status = self.process_ops.get_cmd_output("echo %temp%")
            if type(tmpdir) is unicode:
                tmpdir = tmpdir.encode("utf8")
            if type(tmpdir) is str:
                tmpdir = tmpdir.strip(" \r\t\n")
                if tmpdir[1] == ":":
                    tmpdir = tmpdir[2:]
                else:
                    log_debug(_this_file, '%s: Temp directory path "%s" is not in expected form. The expected form is something like "C:\\Windows\\Temp"\n' % (self.__class__.__name__, tmpdir) )
                    tmpdir = None
                log_debug2(_this_file, '%s: Got temp dir: "%s"\n' % (self.__class__.__name__, tmpdir) )
            else:
                tmpdir = None

            if not tmpdir:
                tmpdir = dirname

            tmpfilename = tmpdir + r"\workbench-temp-file.ini"

            log_debug(_this_file, '%s: Remotely writing contents to temporary file "%s"\n' % (self.__class__.__name__, tmpfilename) )
            log_debug3(_this_file, '%s: %s\n' % (self.__class__.__name__, content) )
            self.ssh.set_contents(tmpfilename, content)

            if backup_extension:
                log_debug(_this_file, '%s: Backing up "%s"\n' % (self.__class__.__name__, path) )
                backup_cmd = "copy /y " + quote_path_win(path) + " " + quote_path_win(path+backup_extension)
                msg, code = self.process_ops.get_cmd_output(backup_cmd)
                if code != 0:
                    print backup_cmd, "->", msg
                    log_error(_this_file, '%s: Error backing up file: %s\n' % (self.__class__.__name__, backup_cmd+'->'+msg) )
                    raise RuntimeError("Error backing up file: %s" % msg)

            copy_to_dest = "copy /y " + quote_path_win(tmpfilename) + " " + quote_path_win(path)
            delete_tmp = "del " + quote_path_win(tmpfilename)
            log_debug(_this_file, '%s: Copying file to final destination: "%s"\n' % (self.__class__.__name__, copy_to_dest) )
            msg, code = self.process_ops.get_cmd_output(copy_to_dest)
            if code != 0:
                print copy_to_dest, "->", msg
                log_error(_this_file, '%s: Error copying temporary file over destination file: %s\n%s to %s\n' % (self.__class__.__name__, msg, tmpfilename, path) )
                raise RuntimeError("Error copying temporary file over destination file: %s\n%s to %s" % (msg, tmpfilename, path))
            log_debug(_this_file, '%s: Deleting tmp file: "%s"\n' % (self.__class__.__name__, delete_tmp) )
            msg, code = self.process_ops.get_cmd_output(delete_tmp)
            if code != 0:
                print "Could not delete temporary file %s: %s" % (tmpfilename, msg)
                log_info(_this_file, '%s: Could not delete temporary file "%s": %s\n' % (self.__class__.__name__, tmpfilename, msg) )
        else:
            raise Exception("No SSH session active, cannot save file remotely")

    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_user = Users.CURRENT, user_password = None, skip_lines=0):
        if self.ssh:
            # Supposedly in Windows, sshd account has admin privileges, so Users.ADMIN can be ignored
            try:
                return self.ssh.get_contents(filename)
            except IOError, exc:
                if exc.errno == errno.EACCES:
                    raise PermissionDeniedError("Permission denied attempting to read file %s" % filename)
        else:
            print "Attempt to read remote file with no ssh session"
            import traceback
            traceback.print_stack()
            raise Exception("Cannot read remote file without an SSH session")

    def check_dir_writable(self, path, as_user=Users.CURRENT, user_password=None):
        msg, code = self.process_ops.get_cmd_output('echo 1 > ' + quote_path(path + "/wba_tmp_file.bak"))
        ret = (code == 0)
        if ret:
            msg, code = self.process_ops.get_cmd_output('del ' + quote_path(path + "/wba_tmp_file.bak"))
        return ret

    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False): # base operation to build file_exists and remote file selector
        # TODO: user elevation
        sftp = self.ssh.getftp()
        (dirs, files) = sftp.ls(path, include_size=include_size)
        ret = []
        for d in dirs:
            ret.append((d[0] + "/", d[1]) if include_size else d + "/")
        return ret + list(files)
        
_file_ops_classes.append(FileOpsRemoteWindows)


#===============================================================================
#
#===============================================================================
class ServerManagementHelper(object):
    def __init__(self, profile, ssh):
        self.tmp_files = [] # TODO: make sure the files will be deleted on exit

        self.profile = profile

        klass = None
        match_tuple = (profile.host_os, profile.target_os, profile.connect_method)
        for k in _process_ops_classes:
            if k.match(match_tuple):
                klass = k
                break
        if klass:
            sudo_prefix=profile.sudo_prefix
            
            if not sudo_prefix:
                sudo_prefix = default_sudo_prefix

            self.shell = klass(sudo_prefix=sudo_prefix, ssh=ssh)
            self.shell.post_init()
        else:
            raise Exception("Unsupported administration target type: %s"%str(match_tuple))

        klass = None
        for k in _file_ops_classes:
            if k.match(profile.target_os, profile.connect_method):
                klass = k
                break

        if klass:
            self.file = klass(self.shell, ssh=ssh, target_os = profile.target_os)
        else:
            raise Exception("Unsupported administration target type: %s:%s" % (str(profile.target_os), str(profile.connect_method)))


    @property
    def cmd_output_encoding(self):
        if self.shell:
            return self.shell.cmd_output_encoding
        return ""

    #-----------------------------------------------------------------------------
    def check_dir_writable(self, path, as_user=Users.CURRENT, user_password=None):
        return self.file.check_dir_writable(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def file_exists(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.file_exists(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def get_available_space(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.get_available_space(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def get_file_owner(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.get_file_owner(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def create_directory(self, path, as_user = Users.CURRENT, user_password=None, with_owner=None):
        return self.file.create_directory(path, as_user, user_password, with_owner)

    #-----------------------------------------------------------------------------
    def create_directory_recursive(self, path, as_user = Users.CURRENT, user_password=None, with_owner=None):
        return self.file.create_directory_recursive(path, as_user, user_password, with_owner)

    #-----------------------------------------------------------------------------
    def remove_directory(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.remove_directory(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def remove_directory_recursive(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.remove_directory_recursive(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    def delete_file(self, path, as_user = Users.CURRENT, user_password=None):
        return self.file.delete_file(path, as_user, user_password)

    #-----------------------------------------------------------------------------
    # Make sure that file is readable only by user!
    def make_local_tmpfile(self):
        # Here we create that file name blah-blah-blah
        # if total_success:
        #   self.tmp_files.append(filename)
        raise NotImplementedError

    #-----------------------------------------------------------------------------
    def get_file_content(self, path, as_user = Users.CURRENT, user_password = None, skip_lines=0):
        return self.file.get_file_content(path, as_user=as_user, user_password=user_password, skip_lines=skip_lines)

    #-----------------------------------------------------------------------------
    def set_file_content(self, path, contents, as_user = Users.CURRENT, user_password = None):
        return self.file.save_file_content(path, contents, as_user=as_user, user_password=user_password)

    #-----------------------------------------------------------------------------
    def listdir(self, path, as_user = Users.CURRENT, user_password = None, include_size=False):
        return self.file.listdir(path, as_user, user_password, include_size=include_size)

    #-----------------------------------------------------------------------------
    def set_file_content_and_backup(self, path, contents, backup_extension, as_user = Users.CURRENT, user_password = None):
        if type(contents) is unicode:
            contents = contents.encode("utf8")
        return self.file.save_file_content_and_backup(path, contents, backup_extension, as_user=as_user, user_password=user_password)

    #-----------------------------------------------------------------------------
    # Returns Status Code
    # Text Output is given to output_handler, if there is any
    def execute_command(self, command, as_user = Users.CURRENT, user_password=None, output_handler=None):
        return self.shell.exec_cmd(command, as_user, user_password, output_handler)

    def spawn_process(self, command, as_user=Users.CURRENT, user_password=None, output_handler=None):
        # This hack is needed as linux/mac behave differently when running commands with nohup
        # through ssh.
        if self.profile.target_os == 'linux' and not self.profile.is_local:
            command = '_linux_spawn_' + command

        return self.shell.spawn_process(command, as_user, user_password, output_handler)


    def list2cmdline(self, args):
        return self.shell.list2cmdline(args)


#===============================================================================

class LocalInputFile(object):
    def __init__(self, path):
        self.path = path
        self._f = open(path)

    def tell(self):
        return self._f.tell()

    @property
    def size(self):
        return os.stat(self.path).st_size

    def get_range(self, start, end):
        self._f.seek(start)
        return self._f.read(end-start)

    def start_read_from(self, offset):
        self._f.seek(offset)

    def read(self, count):
        return self._f.read(count)

    def readline(self):
        return self._f.readline()


class SFTPInputFile(object):
    def __init__(self, ctrl_be, path):
        self.ctrl_be = ctrl_be
        self.ssh = WbAdminSSH()
        self.path = path
        while True:
            try:  # Repeat get password while password is misspelled. Re-raise other exceptions
                self.ssh.wrapped_connect(self.ctrl_be.server_profile, self.ctrl_be.password_handler)
            except ConnectionError, error:
                if not str(error).startswith('Could not establish SSH connection: Authentication failed'):
                    raise
            else:
                break
        if not self.ssh.is_connected():
            raise RuntimeError('Could not connect to remote server')

        self.sftp = self.ssh.client.open_sftp()
        try:
            self._f = self.sftp.open(path)
        except IOError:
            raise RuntimeError('Could not read file %s in remote server. Please verify path and permissions' % path)

    def tell(self):
        return self._f.tell()

    @property
    def size(self):
        return self.sftp.stat(self.path).st_size

    def get_range(self, start, end):
        self._f.seek(start)
        return self._f.read(end-start)

    def start_read_from(self, offset):
        self._f.seek(offset)

    def read(self, count):
        return self._f.read(count)

    def readline(self):
        return self._f.readline()


import multiprocessing
class SudoTailInputFile(object):
    def __init__(self, server_helper, path, password):
        self.path = path
        self.server_helper = server_helper # ServerManagementHelper
        self.data = None
        self._password = password
        self.skip_first_newline = True
        self._pos = 0
        self._proc = None
        self._queue = None
        # multiprocessing + paramiko doesn't work, so fallback to threading for remote access
        self._is_local = self.server_helper.profile.is_local

    def __del__(self):
        if self._proc:
            self._proc.join()

    def tell(self):
        return self._pos

    @property
    def size(self):
        files = self.server_helper.listdir(self.path, as_user = Users.ADMIN, user_password=self._password, include_size=True)
        if not files:
            raise RuntimeError("Could not get size of file %s" % self.path)
        return files[0][1]

    def get_range(self, start, end):
        f = StringIO.StringIO()
        ret = self.server_helper.execute_command("/bin/dd if=%s ibs=1 skip=%i count=%i 2> /dev/null" % (quote_path(self.path), start, end-start), as_user = Users.ADMIN, user_password=self._password, output_handler=f.write)
        if ret != 0:
            raise RuntimeError("Could not get data from file %s" % self.path)
        return f.getvalue()

    def read_task(self, offset, file):
        self.server_helper.execute_command("/bin/dd if=%s ibs=1 skip=%i 2> /dev/null" % (quote_path(self.path), offset), as_user = Users.ADMIN, user_password=self._password, output_handler=file.write)
        # this will signal the reader end that there's no more data
        file.close()

    def start_read_task_from(self, offset):
        self._pos = offset
        self._queue = multiprocessing.Queue()
        self.data = QueueFileMP(self._queue)
        self._proc = multiprocessing.Process(target=self.read_task, args=(offset, self.data))
        import sys
        # restore original stdout file descriptors before forking
        stdo, stde, stdi = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr, sys.stdin = sys.real_stdout, sys.real_stderr, sys.real_stdin
        self._proc.start()
        sys.stdout, sys.stderr, sys.stdin = stdo, stde, stdi
        if self.skip_first_newline:
            # for some reason (in Mac OS X) the output is prefixed with a newline, which breaks the XML parsing.. so check for that and skip it if its the case
            if self.data.peek(1) == '\n':
                self.data.read(1)

    def start_read_from(self, offset):
        if self._is_local:
            return self.start_read_task_from(offset)
        self._pos = offset
        f = StringIO.StringIO()
        self.server_helper.execute_command("/bin/dd if=%s ibs=1 skip=%i 2> /dev/null" % (quote_path(self.path), offset), as_user = Users.ADMIN, user_password=self._password, output_handler=f.write)
        self.data = f
        self.data.seek(0)
        if self.skip_first_newline:
            # for some reason (in Mac OS X) the output is prefixed with a newline, which breaks the XML parsing.. so check for that and skip it if its the case
            if self.data.read(1) != '\n':
                self.data.seek(0)

    def read(self, count=None):
        assert self.data is not None
        d = self.data.read(count)
        self._pos += len(d)
        return d

    def readline(self):
        assert self.data is not None
        d = self.data.readline()
        self._pos += len(d)
        return d


# Previous class but for windows
class AdminTailInputFile(object):
    """
    This class is the windows like implementation for the tail as admin command
    It is aided with a command in the admin helper which has the next syntax

    GETFILE <offset> <size> <filename>
       <offset> : position of the file where the read starts
       <size>   : number of bytes to be read, 0 indicates the rest of the file from the <offset> position
    """
    def __init__(self, server_helper, path, password):
        self.path = path
        self.server_helper = server_helper # ServerManagementHelper
        self.data = None
        self._password = password
        self._pos = 0
        self._proc = None
        self._queue = None

    def __del__(self):
        if self._proc:
            self._proc.join()

    def tell(self):
        return self._pos

    @property
    def size(self):
        files = self.server_helper.listdir(self.path, as_user = Users.ADMIN, user_password=self._password, include_size=True)
        if not files:
            raise RuntimeError("Could not get size of file %s" % self.path)
        return files[0][1]

    def get_range(self, start, end):
        f = StringIO.StringIO()
        ret = self.server_helper.execute_command("GETFILE %i %i file=%s" % (start, end-start, quote_path(self.path)), as_user = Users.ADMIN, user_password=self._password, output_handler=f.write)
        if ret != 0:
            raise RuntimeError("Could not get data from file %s" % self.path)
        return f.getvalue()

    def read_task(self, offset, file):
        self.server_helper.execute_command("GETFILE %i 0 file=%s" % (offset, quote_path(self.path)), as_user = Users.ADMIN, user_password=self._password, output_handler=file.write)
        # this will signal the reader end that there's no more data
        file.close()

    def start_read_task_from(self, offset):
        self._pos = offset
        self._queue = multiprocessing.Queue()
        self.data = QueueFileMP(self._queue)
        self._proc = multiprocessing.Process(target=self.read_task, args=(offset, self.data))
        import sys
        # restore original stdout file descriptors before forking
        stdo, stde, stdi = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr, sys.stdin = sys.real_stdout, sys.real_stderr, sys.real_stdin
        self._proc.start()
        sys.stdout, sys.stderr, sys.stdin = stdo, stde, stdi

    def start_read_from(self, offset):
        self._pos = offset
        f = StringIO.StringIO()
        self.server_helper.execute_command("GETFILE %i 0 %s" % (offset, quote_path(self.path)), as_user = Users.ADMIN, user_password=self._password, output_handler=f.write)
        self.data = f
        self.data.seek(0)

    def read(self, count=None):
        assert self.data is not None
        d = self.data.read(count)
        self._pos += len(d)
        return d

    def readline(self):
        assert self.data is not None
        d = self.data.readline()
        self._pos += len(d)
        return d
