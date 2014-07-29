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

from __future__ import with_statement

import threading
import time
import os
import sys

from grt import log_info, log_error
_this_file = os.path.basename(__file__)

from mforms import App, Utilities, newTabView
import mforms

from workbench.notifications import nc

from wb_common import dprint_ex
import wb_admin_utils
from wb_admin_configuration_startup import WbAdminConfigurationStartup
from wb_admin_config_file_ui import WbAdminConfigFileUI
from wb_admin_server_status import WbAdminServerStatus
from wb_admin_connections import WbAdminConnections
from wb_admin_variables import WbAdminVariables
from wb_admin_security import WbAdminSecurity
from wb_admin_logs import WbAdminLogs
from wb_admin_export import WbAdminExport, WbAdminImport
from wb_admin_utils import weakcb
from wb_server_management import wbaOS


def scan_admin_modules():
    # initialize the main WBA modules
    modules = [WbAdminConfigurationStartup,
               WbAdminLogs,
               WbAdminConfigFileUI,

               WbAdminServerStatus,
               WbAdminConnections,
               WbAdminSecurity,
               WbAdminVariables,
               WbAdminExport,
               WbAdminImport]

    # look for extension modules
    #---------------------------------------------------------------------------
    log_info("WBA", "Looking for extension modules for WBA...\n")
    init_count = 0
    # search in the same dir where the WBA code itself is located
    for location in [os.path.dirname(__file__)]:
        try:
            folders = [f for f in os.listdir(location) if f.startswith("wba_") and os.path.isdir(os.path.join(location, f))]
        except:
            continue

        sys.path.append(location)

        for candidate in folders:
            if os.path.exists(os.path.join(location, candidate, "__init__.py")):
                mod = __import__(candidate)
                if hasattr(mod, "wba_register"):
                    modules.append(mod)
                    init_count+= 1
                else:
                    # unload the module
                    del sys.modules[mod.__name__]
                    del mod

        sys.path.pop()

    log_info("WBA", "%i extension modules found\n" % init_count)

    return modules

#===============================================================================
#
#===============================================================================
class AdministratorTab(mforms.AppView):
    last_server_status = None
    last_notified_server_status = None

    def __init__(self, ctrl_be, server_profile, main_view, editor):
        mforms.AppView.__init__(self, False, "administrator", False)
        self.editor                     = editor
        self.owner                      = main_view
        self.tabs                       = []
        self.name2page                  = {}
        self.config_ui                  = None
        self.closing                    = False
        self.tabview                    = newTabView(True)
        self.ctrl_be                    = ctrl_be
        self.old_active_tab             = None
        self.server_profile             = server_profile

        self.refresh_tasks_sleep_time   = 2

        # if we're in the Mac, we need to set the background color of the main view of the tab to white,
        # so that MTabSwitcher will take the cue and set the tab color to white too
        if self.server_profile.host_os == wbaOS.darwin:
            self.set_back_color("#ffffff")
      
        # Setup self
        self.set_managed()
        self.set_release_on_add()

        self.on_close(wb_admin_utils.weakcb(self, "handle_on_close"))

        self.ctrl_be.add_me_for_event("server_started", self)
        self.ctrl_be.add_me_for_event("server_stopped", self)

        self.add(self.tabview, True, True)

        Utilities.add_timeout(0.5, weakcb(self, "timeout"))
        self.timeout_thread = threading.Thread(target = self.refresh_tasks_thread)
        self.timeout_thread.setDaemon(True)
        self.timeout_thread.start()
        self.tabview.add_tab_changed_callback(self.tab_changed)

        self.timeout() # will call self.connect_mysql() and check if mysql is running

        self.ctrl_be.continue_events() # Process events which are queue during init
        dprint_ex(1, "WBA init complete")

    #---------------------------------------------------------------------------
    def handle_on_close(self):
        App.get().set_status_text("Closing Administator.")
        self.shutdown()
        if not self.closing:
            return False
        self.ctrl_be.shutdown()
        self.release()
        self.owner.handle_close()
        return True

    #---------------------------------------------------------------------------
    def set_content_label(self, text):
        self.set_title(text)

    #---------------------------------------------------------------------------
    def add_page(self, page):
        self.tabs.append(page)
        # not needed in Mac since it's already done earlier and in Linux, we shouldn't set the background color,
        # because you never know what gtk theme the user may be using
        if self.server_profile.host_os == wbaOS.windows:
            page.set_back_color("#ffffff")
        self.tabview.add_page(page, "")

    #---------------------------------------------------------------------------
    def remove_page(self, page):
        self.tabs.remove(page)
        self.tabview.remove_page(page)

    #---------------------------------------------------------------------------
    def select_page(self, page):
        self.tabview.set_active_tab(self.tabs.index(page))
        self.owner.become_active_tab()

    #---------------------------------------------------------------------------
    def page_with_id(self, entry_id):
        return self.owner.page_with_id(entry_id)

    #---------------------------------------------------------------------------
    def switch_to(self, entry_id):
        #self.tasks_side.select_entry(entry_id)
        self.tab_changed()

    #---------------------------------------------------------------------------
    def tab_changed(self):
        if self.old_active_tab and hasattr(self.old_active_tab, "page_deactivated"):
            self.old_active_tab.page_deactivated()

        i = self.tabview.get_active_tab()
        panel = self.tabs[i]
        if panel is not None and hasattr(panel, "page_activated"):
            try:
                panel.page_activated()
            except Exception, e:
                import traceback
                log_error(_this_file, "Unhandled exception in Admin for %s: %s\n" % (panel, traceback.format_exc()))
                mforms.Utilities.show_error("Error", "An unhandled exception occurred (%s). Please refer to the log files for details." % e, "OK", "", "")
        self.old_active_tab = panel

    #---------------------------------------------------------------------------
    def shutdown(self):
        dprint_ex(2, " closing")
        self.closing = True
        for tab in self.tabs:
            if hasattr(tab, "shutdown"):
                res = tab.shutdown()
                if res is False:  # It has to explicitely return False to cancel shutdown
                    self.closing = False

    #---------------------------------------------------------------------------
    def shutdown_event(self):
        self.shutdown()

    #---------------------------------------------------------------------------
    def notify_server_status_change(self, state):
        if self.last_notified_server_status and self.last_notified_server_status != state:
            info = { "state" : state, "connection" : self.editor.connection }
            # this will notify the rest of the App that the server state has changed, giving them a chance
            # to reconnect or formally disconnect
            nc.send("GRNServerStateChanged", self.editor, info)
        self.last_notified_server_status = state

    #---------------------------------------------------------------------------
    def server_started_event(self):
        dprint_ex(1, "Handling start event")
        if len(self.tabs) > 0 and hasattr(self.tabs[0], 'print_output'):
            self.ctrl_be.uitask(self.tabs[0].print_output, "Server is running")
        self.notify_server_status_change("running")
        self.refresh_tasks_sleep_time = 2
        dprint_ex(1, "Done handling start event")

    #---------------------------------------------------------------------------
    def server_stopped_event(self):
        dprint_ex(1, "Handling stop event")
        if len(self.tabs) > 0 and hasattr(self.tabs[0], "print_output"):
            self.ctrl_be.uitask(self.tabs[0].print_output, "Server is stopped")
        self.notify_server_status_change("stopped")
        self.refresh_tasks_sleep_time = 3
        dprint_ex(1, "Done handling stop event")

    #---------------------------------------------------------------------------
    def refresh_tasks_thread(self):
        dprint_ex(2, "Entering refresh tasks thread")

        while not self.closing:
            status = "unknown"
            try:
                status = self.ctrl_be.is_server_running(verbose=0)
            except Exception, exc:
                import traceback
                traceback.print_exc()
                print "exception getting server status: %s" % exc

            control_event = None
            if self.last_server_status != status:
                if status == "running":
                    control_event = "server_started"
                elif status == "stopped":
                    control_event = "server_stopped"

            if control_event:
                self.ctrl_be.event_from_main(control_event)

            dprint_ex(3, "server running", status, ", self.closing =", self.closing)
            self.last_server_status = status

            time.sleep(self.refresh_tasks_sleep_time)

        dprint_ex(2, "Leaving refresh tasks thread")

    #---------------------------------------------------------------------------
    def timeout(self):
        if not self.closing:
            self.ctrl_be.process_ui_task_queue()
        return not self.closing
