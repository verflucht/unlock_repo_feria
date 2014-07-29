# Copyright (c) 2009, 2013, Oracle and/or its affiliates. All rights reserved.
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

from wb import DefineModule, wbinputs
import grt
import os
import sys

from mforms import Utilities, newButton, newLabel, newBox
import mforms

import wb_admin_main
import wb_admin_utils
import wba_ssh_ui
import wb_admin_ssh
import wb_admin_control
from wb_server_control import PasswordHandler
from wb_server_control import ServerProfile
from workbench.db_utils import MySQLConnection, MySQLError, escape_sql_string
from wb_common import OperationCancelledError, InvalidPasswordError, NoDriverInConnection, Users
from wb_server_management import local_get_cmd_output

from workbench.notifications import NotificationCenter


from grt import log_info, log_error, log_warning, log_debug
_this_file = os.path.basename(__file__)


# How the Administrator Module Works
# ----------------------------------
#
# = Initial Setup
#
# When the Workbench starts up, the initialize() function from this module is called.
# That will do the following:
# - register an observer for the GRNSQLEditorOpened notification.
# - register all built-in pages of the administrator
# - register all extension pages of the administrator
#
# = When GRNSQLEditorOpened is received
#
# An instance of AdministratorContext is created, which will hook the various admin
# page sections to the SQL Editor sidebar and save a reference to itself in the SQL Editor
# object's customData dictionary.
# No other initialization is done at this time (ie, no DB connections or GUI is setup).
#
# = When an admin item is selected in the sidebar
#
# - Setup the main admin GUI view and dock it to the SQL Editor.
# - If the entry requires a ssh connection, it will try to open that connection and the
#   admin specific DB connection, unless it's already connected.
#   If not, it will open the DB connection only.
# - Then it will setup the GUI for the requested admin page and dock it/switch to it.
#


# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "WbAdmin", author= "Oracle Corp.", version="2.0")

class DBError(Exception):
    pass

#-------------------------------------------------------------------------------
wba_page_modules = []

#===============================================================================
#
#===============================================================================
class AdministratorContext:
    """
    An instance of the WBA, associated to a SQL Editor.
    Thi is created when a GRNSQLEditorOpened notification is received.

    Initially, only the different sections of the WBA are added to the sidebar
    and the GUI itself is not initialized until the user enters each section.
    """
    def __init__(self, editor):
        self.editor = editor

        self.connection = self.editor.connection

        self.server_profile = None
        self.admin_pages = {}
        self.page_instances = {}
        self.admin_tab = None
        self.error_box = None
        self.ctrl_be = None

        self.admin_access_status = None # None means OK

        self.sidebar = mforms.fromgrt(editor.sidebar)

        self.sidebar.add_on_section_command_callback(self._sidebar_entry_clicked)

        self.sidebar_sections = [("wba_management", "MANAGEMENT", []), ("wba_instance", "INSTANCE", [])]

        self.shown_in_sidebar = False

        for mod in wba_page_modules:
            mod.wba_register(self)

        # create server profile now, since we need it to be able to tell whether instance items should be enabled in sidebar
        self._check_instance_profile()

        self.show_in_sidebar()

    @property
    def instance_profile(self):
        for instance in grt.root.wb.rdbmsMgmt.storedInstances:
            if instance.connection == self.connection:
                return instance
        return None

    @property
    def instance_management_enabled(self):
        return self.instance_profile != None


    def handle_close(self):
        grt.root.wb.options.options['Administrator:sidebar_collapsed_sections'] = self.sidebar.get_collapse_states()
        del self.editor.customData["adminContext"]

        self.admin_tab = None
        self.ctrl_be = None
        self.admin_access_status = None
        self.page_instances = {}
        self.sidebar.clear_selection()


    def handle_reconnect(self):
        # Called when SQL Editor sends a reconnected notification
        if self.ctrl_be:
            self.ctrl_be.event_from_main("server_started")

    def _check_instance_profile(self):
        self.server_profile = ServerProfile(self.connection, self.instance_profile, False)
        # if no instance info exists, try to auto-detect them
        if self.instance_profile is None:
          if self.server_profile.is_local:
            if autoDetectLocalInstance(self.connection):
              grt.log_info("Admin", "Auto-created instance profile for connection %s\n" % self.connection.name)
              # Retry
              self.server_profile = ServerProfile(self.connection, self.instance_profile, False)
          else:
            if autoDetectRemoteInstance(self.connection):
              grt.log_info("Admin", "Auto-created dummy instance profile for remote connection %s\n" % self.connection.name)
              # Retry
              self.server_profile = ServerProfile(self.connection, self.instance_profile, False)


    def _check_server_version(self):
        version = self.ctrl_be.get_server_version()
        if type(version) is tuple:
            valid_versions = ((4,0), (4,1), (5,0), (5,1), (5,2), (5,4), (5,5), (5,6), (5, 7))
            if version[:2] not in valid_versions:
                log_warning(_this_file, "%s: Server version %s is NOT supported\n" % (self.__class__.__name__, str(version)) )
                Utilities.show_error("Unsupported Server Version", "The version of the server you're trying to connect to is %i.%i, which is not supported by Workbench."%version[:2],
                                     "Close", "Ignore", "")
                return False
            else:
                log_info(_this_file, "%s: Server version %s is supported\n" % (self.__class__.__name__, str(version)) )
                return True
        return None


    def _acquire_admin_access(self):
        if not self._validate_remote_admin_settings():
            self.admin_access_status = "Remote management settings are invalid"
            return
        while True:
            try:
                mforms.App.get().set_status_text("Acquiring management access to target host...")
                self.ctrl_be.acquire_admin_access()
                mforms.App.get().set_status_text("Management support for target host enabled successfully.")
                return True
            except wb_admin_ssh.ConnectionError, exc:
                self.admin_access_status = "Remote management capabilities are currently unavailable.\nSSH connection could not be established\n\n%s" % str(exc)
                Utilities.show_error("Error opening SSH connection to server (%s@%s)" % (self.instance_profile.loginInfo["ssh.userName"], self.instance_profile.loginInfo["ssh.hostName"]), str(exc), "OK", "", "")
                return None
            except OperationCancelledError, exc:
                self.admin_access_status = "Remote management capabilities are currently unavailable.\nSSH connection was cancelled"
                mforms.App.get().set_status_text("Cancelled SSH connection (%s)"%exc)
                return None
            except InvalidPasswordError, exc:
                self.admin_access_status = "Remote management capabilities are currently unavailable.\nCould not acquire management access to the server\n\n%s" % exc
                if Utilities.show_error("Could not acquire management access for administration", "%s" % exc, "Retry", "Cancel", "") == mforms.ResultOk:
                    continue
                mforms.App.get().set_status_text("Could not Open WB Admin")
                return None
            except Exception, exc:
                import traceback
                traceback.print_exc()
                self.admin_access_status = "Remote management capabilities are currently unavailable.\nCould not acquire management access to the server\n\n%s" % exc
                mforms.App.get().set_status_text("Could not Open WB Admin")
                if Utilities.show_error("Could not acquire management access for administration", "%s: %s" % (type(exc).__name__, exc), "Settings...", "Cancel", "") == mforms.ResultOk:
                    grt.modules.Workbench.showInstanceManagerFor(self.connection)
                return None

    def acquire_admin_access(self, ignore_failure=False):
        if not self._acquire_admin_access():
            if ignore_failure:
                return True
            if not self.error_box:
                self.error_box = mforms.newBox(True)
                self.error_box.set_padding(50)
                error_label = mforms.newLabel(self.admin_access_status)
                error_label.set_style(mforms.BigBoldStyle)
                self.error_box.add(error_label, False, True)
                self.admin_tab.add_page(self.error_box)
            else:
                self.admin_tab.select_page(self.error_box)
            return False
        else:
            if self.error_box:
                self.admin_tab.remove_page(self.error_box)
                self.error_box = None
            return True

    def _validate_remote_admin_settings(self):
        server_instance = self.instance_profile
        if not server_instance:
            return False

        def validate_setting(settings, option, norm_cb, msg):
            if settings.has_key(option):
                if norm_cb is not None:
                    norm_cb(settings, option)
            else:
                if msg is not None:
                    Utilities.show_warning("WB Administrator", msg, "OK", "", "")
                norm_cb(settings, option)

        def norm_to_switch(settings, option):
            value = 0
            if settings.has_key(option):
                value = settings[option]
                if value > 0:
                    value = 1
                else:
                    value = 0

            settings[option] = value

        def make_str_existing(settings, option):
            if not settings.has_key(option):
                settings[option] = ""

        validate_setting(server_instance.serverInfo, "sys.usesudo", norm_to_switch, None)#"Server profile has no indication of sudo usage")
        validate_setting(server_instance.serverInfo, "sys.usesudostatus", norm_to_switch, None)

        return True

    def _dock_admin_tab(self):
        app = mforms.App.get()
        try:
            self.ctrl_be = wb_admin_control.WbAdminControl(self.server_profile, connect_sql=True)
            self.ctrl_be.init()

            self.admin_tab = wb_admin_main.AdministratorTab(self.ctrl_be, self.server_profile, self, self.editor)
        except MySQLError, exc:
            if exc.message:
                Utilities.show_error("Error Connecting to MySQL Server (%s)" % exc.location, str(exc), "OK", "", "")
            app.set_status_text("Could not Open WB Admin")
            return None
        except OperationCancelledError, exc:
            app.set_status_text("Cancelled (%s)"%exc)
            return None
        except NoDriverInConnection, exc:
            Utilities.show_error('Missing connection driver', str(exc), 'OK', '', '')
            app.set_status_text("Could not Open WB Admin")
            return None
        except Exception, exc:
            import traceback
            traceback.print_exc()
            Utilities.show_error("Error Starting Workbench Administrator", "%s: %s" % (type(exc).__name__, exc), "OK", "", "")
            app.set_status_text("Could not Open WB Admin")
            return None

        if self._check_server_version() is False:
            app.set_status_text("Unsupported server version for Administration")
            return None


        dp = mforms.fromgrt(self.editor.dockingPoint)
        dp.dock_view(self.admin_tab, "", 0)
        dp.select_view(self.admin_tab)
        self.admin_tab.set_title("Administrator")


    def become_active_tab(self):
        dp = mforms.fromgrt(self.editor.dockingPoint)
        dp.select_view(self.admin_tab)


    def _sidebar_entry_clicked(self, entry_id):
        if entry_id == "configure":
            grt.modules.Workbench.showInstanceManagerFor(self.editor.connection)
        else:
            self.open_into_section(entry_id)


    def open_into_section(self, entry_id, select_item=False):
        page_class, needs_remote_access = self.admin_pages.get(entry_id, (None, None))
        if page_class is None: # unknown entry from sidebar, not our business
            return

        # if this is the 1st time opening the WBA, init the main tab and dock it
        if self.admin_tab is None:
            self._dock_admin_tab()

        page = self.page_instances.get(entry_id)
        if not page:
            if (needs_remote_access or entry_id == "admin_server_status") and not self.ctrl_be.admin_access_available:
                if not self.acquire_admin_access(entry_id == "admin_server_status"):
                    return

            page = page_class(self.ctrl_be, self.server_profile, self.admin_tab)
            self.page_instances[entry_id] = page
            self.admin_tab.add_page(page)

        for sname, stitle, sitems in self.sidebar_sections:
            for ident, title, icon_path in sitems:
                if ident == entry_id:
                    self.admin_tab.set_content_label("Administration - %s" % title)
                    break

        self.admin_tab.select_page(page)


    def add_section(self, name, title):
        if not any(x[0] == name for x in self.sidebar_sections):
            self.sidebar_sections.append((name, title, []))


    def register_page(self, page_class, section_id, title, needs_remote_access = False):
        if not section_id:
            section_id = "wba_management" # the default

        self.admin_pages[page_class.identifier()] = (page_class, needs_remote_access)
        icon_path = page_class.identifier()+".png"
        for sname, stitle, sitems in self.sidebar_sections:
            if sname == section_id:
                sitems.append((page_class.identifier(), title, icon_path))
                break

    def show_in_sidebar(self):
        if not self.shown_in_sidebar:
            self.shown_in_sidebar = True
            for sname, stitle, sitems in self.sidebar_sections:
                self.sidebar.add_section(sname, stitle, mforms.TaskSectionShowConfigButton if sname == "wba_instance" else mforms.TaskSectionPlain)
                for ident, ititle, icon_path in sitems:
                    self.sidebar.add_section_entry(sname, ident, ititle, icon_path, mforms.TaskEntryLink)
                    requires_remote_access = self.admin_pages.get(ident, (None, True))[1]
                    enabled = True
                    if requires_remote_access and (not self.server_profile or (self.server_profile and not self.server_profile.is_local and not self.server_profile.remote_admin_enabled)):
                        enabled = False
                    self.sidebar.set_section_entry_enabled(ident, enabled)

            self.sidebar.set_collapse_states(grt.root.wb.options.options.get('Administrator:sidebar_collapsed_sections', ''))

    def page_with_id(self, entry_id):
        return self.page_instances.get(entry_id)


#-------------------------------------------------------------------------------

def attachToSQLEditor(name, sender, args):
    # this is called when a new SQL Editor tab is created
    # attach our WBA related things to it
    context = AdministratorContext(sender)
    sender.customData["adminContext"] = grt.togrt(context)
    if not sender.isConnected:
        mforms.Utilities.add_timeout(0.1, lambda:context.open_into_section("admin_server_status", True))

#-------------------------------------------------------------------------------
def handleReconnect(name, sender, args):
    context = grt.fromgrt(sender.customData["adminContext"])
    if context and args['connected']:
        context.handle_reconnect()

#-------------------------------------------------------------------------------
@ModuleInfo.export(grt.INT)
def initialize():
    # this is called when WB finishes initializing itself

    # register ourselves for when SQL Editor tabs are opened
    nc = NotificationCenter()
    nc.add_observer(attachToSQLEditor, name = "GRNSQLEditorOpened")
    nc.add_observer(handleReconnect, name = "GRNSQLEditorReconnected")

    return 1

# scan for WBA modules at module load time
wba_page_modules = wb_admin_main.scan_admin_modules()

#-------------------------------------------------------------------------------

@ModuleInfo.export(grt.classes.db_mgmt_ServerInstance, grt.classes.db_mgmt_Connection)
def autoDetectLocalInstance(connection):
    """Create a Instance profile for the local server from the connection."""
    instance = grt.classes.db_mgmt_ServerInstance()
    instance.connection = connection
    instance.name = connection.name
    instance.serverInfo["setupPending"] = True

    version = connection.parameterValues.get("serverVersion", None)
    if version:
        version = ".".join(version.split(".")[:2])

    def get_profiles_for(system):
        path = mforms.App.get().get_resource_path("mysql.profiles")
        if not path:
            path = mforms.App.get().get_resource_path("")
            if not path:
                log_error(_this_file, "Could not find mysql.profiles dir\n")
                return []
            path += "/mysql.profiles"
        files = os.listdir(path)
        profiles = []
        for f in files:
            data = grt.unserialize(os.path.join(path, f))
            if data.has_key("sys.system") and data["sys.system"] == system:
                profiles.append(data)
        return profiles

    def pick_suitable_linux_profile(profiles):
        return profiles[0]

    if sys.platform.lower().startswith("win"):
        profiles = get_profiles_for("Windows")
        if profiles:
            if version:
                profiles = [prof for prof in profiles if prof.get("serverVersion", None) == version]
            if profiles:
                instance.serverInfo.update(profiles[0])
        instance.serverInfo["windowsAdmin"] = 1 # this forces WMI admin for localhost Windows
    elif sys.platform.lower() == "darwin":
        profiles = get_profiles_for("MacOS X")
        if profiles:
            instance.serverInfo.update(profiles[0])
            possible_paths = [instance.serverInfo.get("sys.config.path"), "/etc/my.cnf", "/etc/mysql/my.cnf"]
            for p in possible_paths:
                if os.path.exists(p):
                    instance.serverInfo["sys.config.path"] = p
                    break
    elif "linux" in sys.platform.lower():
        profiles = get_profiles_for("Linux")
        if profiles:
            profile = pick_suitable_linux_profile(profiles)
            instance.serverInfo.update(profile)
            possible_paths = [instance.serverInfo.get("sys.config.path"), "/etc/my.cnf", "/etc/mysql/my.cnf"]
            for p in possible_paths:
                if os.path.exists(p):
                    instance.serverInfo["sys.config.path"] = p
                    break

    instance.loginInfo["ssh.hostName"] = ""
    instance.loginInfo["ssh.localPort"] = "3306"
    instance.loginInfo["ssh.userName"] = "mysql"
    instance.loginInfo["ssh.useKey"] = 0

    if sys.platform.lower().startswith("win"):
        homedir = mforms.Utilities.get_special_folder(mforms.ApplicationData)
    else:
        homedir = "~"
    instance.loginInfo["ssh.key"] = homedir + "/.ssh/ssh_private_key"

    instance.owner = grt.root.wb.rdbmsMgmt
    grt.root.wb.rdbmsMgmt.storedInstances.append(instance)
    grt.modules.Workbench.saveInstances()
    return instance


@ModuleInfo.export(grt.classes.db_mgmt_ServerInstance, grt.classes.db_mgmt_Connection)
def autoDetectRemoteInstance(connection):
    """Create an Instance profile for the remove server from the connection.
    Remote admin will be left disabled, to be filled by the user."""

    instance = grt.classes.db_mgmt_ServerInstance()
    instance.connection = connection
    instance.name = connection.name
    instance.serverInfo["setupPending"] = True
    
    instance.owner = grt.root.wb.rdbmsMgmt
    grt.root.wb.rdbmsMgmt.storedInstances.append(instance)
    grt.modules.Workbench.saveInstances()

    return instance

#-------------------------------------------------------------------------------

@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_Connection)
def checkConnectionForRemoteAdmin(conn):
    the_instance = None
    for instance in grt.root.wb.rdbmsMgmt.storedInstances:
        if instance.connection == conn:
            the_instance = instance
            break
    profile = ServerProfile(conn, the_instance)
    return profile.is_local or profile.remote_admin_enabled

@ModuleInfo.export(grt.STRING, grt.DICT)
def listWindowsServices(server_instance):
    return wb_admin_utils.list_windows_services(server_instance)

@ModuleInfo.export(grt.STRING, grt.classes.db_mgmt_Connection, grt.classes.db_mgmt_ServerInstance)
def openRemoteFileSelector(connection, serverInstance):
    profile = ServerProfile(connection, serverInstance)
    return wba_ssh_ui.remote_file_selector(profile, PasswordHandler(profile))


class PasswordExpiredDialog(mforms.Form):
    def __init__(self, conn):
        mforms.Form.__init__(self, None)
        self._conn = conn
        self.set_title("Password Expired")

        vbox = mforms.newBox(False)
        vbox.set_padding(20)
        vbox.set_spacing(18)

        user = conn.parameterValues["userName"]
        l = newLabel("Password for MySQL account '%s'@%s expired.\nPlease pick a new password:" % (user, conn.hostIdentifier.replace("Mysql@", "")))
        l.set_style(mforms.BoldStyle)
        vbox.add(l, False, True)

        box = mforms.newTable()
        box.set_padding(1)
        box.set_row_count(3)
        box.set_column_count(2)
        box.set_column_spacing(7)
        box.set_row_spacing(8)

        hbox = mforms.newBox(True)
        hbox.set_spacing(12)
        icon = mforms.newImageBox()
        icon.set_image(mforms.App.get().get_resource_path("wb_lock.png"))
        hbox.add(icon, False, True)
        hbox.add(box, True, True)
        vbox.add(hbox, False, True)

        self.old_password = mforms.newTextEntry(mforms.PasswordEntry)
        box.add(newLabel("Old Password:", True), 0, 1, 0, 1, mforms.HFillFlag)
        box.add(self.old_password, 1, 2, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)

        self.password = mforms.newTextEntry(mforms.PasswordEntry)
        box.add(newLabel("New Password:", True), 0, 1, 1, 2, mforms.HFillFlag)
        box.add(self.password, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)

        self.confirm = mforms.newTextEntry(mforms.PasswordEntry)
        box.add(newLabel("Confirm:", True), 0, 1, 2, 3, mforms.HFillFlag)
        box.add(self.confirm, 1, 2, 2, 3, mforms.HFillFlag|mforms.HExpandFlag)

        bbox = newBox(True)
        bbox.set_spacing(8)
        self.ok = newButton()
        self.ok.set_text("OK")

        self.cancel = newButton()
        self.cancel.set_text("Cancel")
        mforms.Utilities.add_end_ok_cancel_buttons(bbox, self.ok, self.cancel)

        vbox.add_end(bbox, False, True)

        self.set_content(vbox)

        self.set_size(500, 260)
        self.center()


    def run(self):
        if self.run_modal(self.ok, self.cancel):
            if self.password.get_string_value() != self.confirm.get_string_value():
                mforms.Utilities.show_error("Reset Password", "The password and its confirmation do not match. Please try again.", "OK", "", "")
                return self.run()

            con = self._conn
            old_multi_statements = con.parameterValues.get("CLIENT_MULTI_STATEMENTS")
            old_script = con.parameterValues.get("preInit")
            con.parameterValues["CLIENT_MULTI_STATEMENTS"] = 1
            con.parameterValues["preInit"] = "SET PASSWORD = PASSWORD('%s')" % escape_sql_string(self.password.get_string_value())

            retry = False
            result = 1

            c = MySQLConnection(con, password = self.old_password.get_string_value())
            # connect to server so that preInitScript will do the password reset work
            try:
                c.connect()
            except MySQLError, e:
                if mforms.Utilities.show_error("Reset Password", str(e), "Retry", "Cancel", "") == mforms.ResultOk:
                    retry = True
                result = 0
          
            if old_script is not None:
                con.parameterValues["preInit"] = old_script
            else:
                del con.parameterValues["preInit"]
            if old_multi_statements is not None:
                con.parameterValues["CLIENT_MULTI_STATEMENTS"] = old_multi_statements
            else:
                del con.parameterValues["CLIENT_MULTI_STATEMENTS"]

            if retry:
                return self.run()

            return result
        return 0



@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_Connection)
def handleExpiredPassword(conn):
    dlg = PasswordExpiredDialog(conn)
    return dlg.run()

#-------------------------------------------------------------------------------
@ModuleInfo.export(grt.INT, grt.STRING)
def testAdministrator(what):
    import wb_admin_test
    wb_admin_test.run()
    import sys
    sys.exit(0) # TODO return code here
    return 1


def check_if_config_file_has_section(config_file, section):
    for line in config_file:
        if line.strip() == "[%s]"%section:
            return True
    return False


test_ssh_connection = None
test_ssh_connection_is_windows = None

@ModuleInfo.export(grt.STRING, grt.STRING, grt.classes.db_mgmt_Connection, grt.classes.db_mgmt_ServerInstance)
def testInstanceSettingByName(what, connection, server_instance):
    global test_ssh_connection

    log_debug(_this_file, "Test %s in %s\n" % (what, connection.name))

    profile = ServerProfile(connection, server_instance)

    if what == "connect_to_host":
        if test_ssh_connection:
            test_ssh_connection = None

        log_info(_this_file, "Instance test: Connecting to %s\n" % profile.ssh_hostname)

        try:
            test_ssh_connection = wb_admin_control.WbAdminControl(profile, connect_sql=False)
            test_ssh_connection.init()
            grt.send_info("connected.")
        except Exception, exc:
            import traceback
            traceback.print_exc()
            return "ERROR "+str(exc)
        except:
            print "Unknown error"
            return "ERROR"

        try:
            test_ssh_connection.acquire_admin_access()
        except Exception, exc:
            import traceback
            traceback.print_exc()
            return "ERROR "+str(exc)

        os_info = test_ssh_connection.detect_operating_system_version()
        if os_info:
            os_type, os_name, os_variant, os_version = os_info
            log_info(_this_file, "Instance test: detected remote OS: %s (%s), %s, %s\n" % (os_info))

            # check if the admin access error was because of wrong OS set
            if os_type != profile.target_os:
                return "ERROR Wrong Remote OS configured for connection. Set to %s, but was detected as %s" % (profile.target_os, os_type)
        else:
            log_warning(_this_file, "Instance test: could not determine OS version information\n")

            return "ERROR Could not determine remote OS details"

        return "OK"

    elif what == "disconnect":
        if test_ssh_connection:
            test_ssh_connection = None
        return "OK"

    elif what == "check_privileges":
        return "ERROR"

    elif what in ("find_config_file", "check_config_path", "check_config_section"):
        config_file = profile.config_file_path
        print "Check if %s exists in remote host" % config_file
        try:
            if not test_ssh_connection.ssh.file_exists(config_file):
                return "ERROR File %s doesn't exist" % config_file
            else:
                print "File was found in expected location"
        except IOError:
            return 'ERROR Could not verify the existence of the file %s' % config_file

        if what == "check_config_path":
            return "OK"

        section = profile.config_file_section
        cfg_file_content = ""
        print "Check if %s section exists in %s" % (section, config_file)
        try:
            #local_file = test_ssh_connection.fetch_file(config_file)
            cfg_file_content = test_ssh_connection.server_helper.get_file_content(path=config_file)
        except Exception, exc:
            import traceback
            traceback.print_exc()
            return "ERROR "+str(exc)

        if ("[" + section + "]") in cfg_file_content:
            return "OK"
        return "ERROR Couldn't find section %s in the remote config file %s" % (section, config_file)

    elif what in ("find_config_file/local", "check_config_path/local", "check_config_section/local"):
        config_file = profile.config_file_path
        config_file = wb_admin_control.WbAdminControl(profile, connect_sql=False).expand_path_variables(config_file)
        print "Check if %s can be accessed" % config_file
        if os.path.exists(config_file):
            print "File was found at the expected location"
        else:
            return "ERROR File %s doesn't exist" % config_file

        if what == "check_config_path/local":
            return "OK"

        section = profile.config_file_section
        print "Check if section for instance %s exists in %s" % (section, config_file)
        if check_if_config_file_has_section(open(config_file, "r"), section):
            print "[%s] section found in configuration file" % section
            return "OK"
        return "ERROR Couldn't find section [%s] in the config file %s" % (section, config_file)

    elif what == "find_error_files":
        return "ERROR"

    elif what == "check_admin_commands":
        path = profile.start_server_cmd
        cmd_start= None
        if path.startswith("/"):
            cmd_start = path.split()[0]
            if not test_ssh_connection.ssh.file_exists(cmd_start):
                return "ERROR %s is invalid" % path

        path = profile.stop_server_cmd
        if path.startswith("/"):
            cmd = path.split()[0]
            if cmd != cmd_start and not test_ssh_connection.ssh.file_exists(cmd):
                return "ERROR %s is invalid" % path

        command = profile.check_server_status_cmd
        print "Checking command '%s'" % command
        #rc = test_ssh_connection.is_running()
        rc = test_ssh_connection.server_control.get_status()
        print "Server detected as %s" % (rc and "running" or "stopped"),

        return "OK"

    elif what == "check_admin_commands/local":
        path = profile.start_server_cmd
        cmd_start= None
        if path.startswith("/"):
            cmd_start = path.split()[0]
            if not os.path.exists(cmd_start):
                return "ERROR %s is invalid" % path

        path = profile.stop_server_cmd
        if path.startswith("/"):
            cmd = path.split()[0]
            if cmd != cmd_start and not os.path.exists(cmd):
                return "ERROR %s is invalid" % path

        command = profile.check_server_status_cmd
        print "Checking command '%s'" % command
        result, rc = local_get_cmd_output(command, Users.CURRENT, None)
        print "Server detected as %s" % (result and "running" or "stopped")

        return "OK "+(result and "running" or "stopped")

    return "ERROR bad command"


@ModuleInfo.export(grt.DICT, grt.classes.db_mgmt_ServerInstance)
def detectInstanceSettings(server_instance):
    #form = Form()

    #form.run(None, None)

    return {}



@ModuleInfo.export(grt.STRING, grt.classes.db_mgmt_ServerInstance)
def testInstanceSettings(server_instance):
    error = testInstanceSettingByName("connect_to_host", server_instance.connection, server_instance)
    testInstanceSettingByName("disconnect", server_instance.connection, server_instance)
    return error


##------------------------------------------------------------------------------------------------------------------------

@ModuleInfo.plugin("wb.admin.open_into", type="standalone", input=[wbinputs.currentSQLEditor(), wbinputs.string()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_Editor, grt.STRING)
def openAdminSection(editor, section):
    context = grt.fromgrt(editor.customData["adminContext"])
    if context:
        context.open_into_section(section, True)


# Hack to make this plugin only appear if SE modules are available
try:
    import wba_meb # noqa
    @ModuleInfo.plugin("wb.admin.open_into_se", type="standalone", input=[wbinputs.currentSQLEditor(), wbinputs.string()])
    @ModuleInfo.export(grt.INT, grt.classes.db_query_Editor, grt.STRING)
    def openAdminSectionSE(editor, section):
        context = grt.fromgrt(editor.customData["adminContext"])
        if context:
            context.open_into_section(section, True)
except ImportError:
    pass


@ModuleInfo.plugin("wb.admin.settings", type="standalone", input=[wbinputs.currentSQLEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_Editor)
def openConnectionSettings(editor):
    grt.modules.Workbench.showInstanceManagerFor(editor.connection)


@ModuleInfo.plugin("wb.admin.reset_password_cache", type="standalone", input=[wbinputs.currentSQLEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_Editor)
def resetPasswordCache(editor):
    context = grt.fromgrt(editor.customData["adminContext"])
    if context:
        handler = PasswordHandler(context.server_profile)
        if context.ctrl_be and context.ctrl_be.password_handler:
            context.ctrl_be.password_handler.pwd_store = {}

        for service_type in ["ssh", "sshkey", "file", "service.startstop", "remoteshell"]:
            details = handler.get_password_parameters(service_type)
            if details and details != "UAC":
                title, service, account = details
                mforms.Utilities.forget_password(service, account)

    mforms.Utilities.show_message("Reset Saved Passwords", "Saved passwords for this connection were deleted.", "OK", "", "")



