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


from grt import log_info, log_error
from workbench.db_utils import QueryError
import mforms

import wb_admin_monitor

def stradd(table, y, label, value):
    t = mforms.newLabel(label)
    table.add(t, 0, 1, y, y+1, mforms.HFillFlag)

    t = mforms.newLabel(value)
    t.set_style(mforms.BoldStyle)
    t.set_color("#555555")
    table.add(t, 1, 2, y, y+1, mforms.HFillFlag)
    return t


class ConnectionInfo(mforms.Box):
    def __init__(self):
        mforms.Box.__init__(self, True)
        self.set_release_on_add()
        self.set_managed()

        self.set_spacing(35)

        self.icon = mforms.newImageBox()
        self.icon.set_image(mforms.App.get().get_resource_path("mysql-logo-00.png"))

        self.add(self.icon, False, True)

        vbox = mforms.newBox(False)
        self.vbox = vbox
        self.add(vbox, True, True)
        vbox.set_spacing(2)
        vbox.add(mforms.newLabel("Connection Name"), False, True)

        self.connection_name = mforms.newLabel("?")
        self.connection_name.set_style(mforms.VeryBigStyle)
        vbox.add(self.connection_name, False, True)

        self.info_table = None


    def update(self, ctrl_be):
        self.suspend_layout()
        self.connection_name.set_text(ctrl_be.server_profile.name)

        info = ctrl_be.server_variables

        if self.info_table:
            self.vbox.remove(self.info_table)

        self.info_table = mforms.newTable()
        self.info_table.set_column_count(2)
        self.info_table.set_row_count(5)
        self.info_table.set_column_spacing(18)
        self.info_table.set_row_spacing(5)
        self.vbox.add(self.info_table, True, True)

        stradd(self.info_table, 0, "\nHost:", "\n"+info.get("hostname", "n/a"))
        stradd(self.info_table, 1, "Socket:", info.get("socket", "n/a"))
        stradd(self.info_table, 2, "Port:", info.get("port", "n/a"))
        stradd(self.info_table, 3, "Version:", "%s\n%s" % (info.get("version", "n/a"), info.get("version_comment", "")))
        stradd(self.info_table, 4, "Compiled For:", "%s (%s)" % (info.get("version_compile_os", "n/a"), info.get("version_compile_machine", "n/a")))

        server_version = ctrl_be.get_server_version()
        if server_version and info:
            x, y = server_version[:2]
            icon = mforms.App.get().get_resource_path("mysql-logo-%i%i.png" % (x, y))
            if icon:
                self.icon.set_image(icon)
        self.resume_layout()



#===============================================================================
#
#===============================================================================
class WbAdminServerStatus(mforms.Box):
    status      = None
    connections = None

    @classmethod
    def wba_register(cls, admin_context):
        admin_context.register_page(cls, "wba_management", "Server Status", False)

    @classmethod
    def identifier(cls):
        return "admin_server_status"


    #---------------------------------------------------------------------------
    def __init__(self, ctrl_be, server_profile, main_view):
        mforms.Box.__init__(self, True)
        self.set_managed()
        self.set_release_on_add()

        self.ui_created = False

        self.set_spacing(24)

        self.ctrl_be = ctrl_be
        self.server_profile = server_profile
        self.main_view = main_view

        lbox = mforms.newBox(False)
        self.add(lbox, True, True)

        self.connection_info = ConnectionInfo()
        self.connection_info.set_padding(24)
        lbox.add(self.connection_info, False, True)

        self.scrollbox = mforms.newScrollPanel(mforms.ScrollPanelDrawBackground)
        self.scrollbox.set_padding(24)
        self.content = mforms.newBox(False)
        self.content.set_padding(20)
        self.content.set_spacing(4)
        self.scrollbox.add(self.content)
        lbox.add(self.scrollbox, True, True)

        image = mforms.newImageBox()
        if self.server_profile.host_os == "linux":
            image.set_image(mforms.App.get().get_resource_path("mysql-status-separator-linux.png"))
        else:
          image.set_image(mforms.App.get().get_resource_path("mysql-status-separator.png"))
        image.set_image_align(mforms.MiddleCenter)
        self.add(image, False, True)

        self.on_icon = mforms.App.get().get_resource_path("mysql-status-on.png")
        self.off_icon = mforms.App.get().get_resource_path("mysql-status-off.png")

        self.status = wb_admin_monitor.WbAdminMonitor(server_profile, self.ctrl_be)
        self.status.set_size(360, -1)
        self.status.set_padding(0, 24, 24, 24)
        self.add(self.status, False, False)

        self.controls = {}

        self.currently_started = None
        self.ctrl_be.add_me_for_event("server_started", self)
        self.ctrl_be.add_me_for_event("server_stopped", self)

        self.connection_info.update(self.ctrl_be)

    #---------------------------------------------------------------------------
    def server_started_event(self):
        if self.currently_started != True:
            self.refresh("started")
            self.currently_started = True

            self.connection_info.update(self.ctrl_be)

    #---------------------------------------------------------------------------
    def server_stopped_event(self):
        if self.currently_started != False:
            self.refresh("stopped")
            self.currently_started = False

    #---------------------------------------------------------------------------
    def refresh(self, status):
        self.status.refresh_status(status)

    #---------------------------------------------------------------------------
    def page_activated(self):
        self.suspend_layout()
        try:
            if not self.ui_created:
                self.create_ui()
                self.ui_created = True
        finally:
            self.resume_layout()

        mforms.Utilities.add_timeout(0.5, self.update)
        #self.update()


    def update(self):
        self.status.refresh_status(self.main_view.last_server_status)

        info = self.ctrl_be.server_variables
        plugins = dict(self.ctrl_be.server_active_plugins) # plugin -> type

        repl_error = None
        res = None
        try:
            res = self.ctrl_be.exec_query("SHOW SLAVE STATUS")
        except QueryError, e:
            if e.error == 1227:
                repl_error = "Insufficient privileges to view slave status"
            else:
                repl_error = "Error querying status: %s" % str(e)
        repl = {}
        if res and res.nextRow():
            for field in ["Slave_IO_State", "Master_Host"]:
                repl[field] = res.stringByName(field)

        disk_space = "unable to retrieve"
        if self.ctrl_be.server_control and info.get("datadir"):
            disk_space = self.ctrl_be.server_helper.get_available_space(info.get("datadir"))

        # Update the controls in the UI
        self.suspend_layout()
        self.controls["Disk Space in Data Dir:"].set_text(disk_space)

        table = self.controls["Replication Slave"]

        if repl:
            table.remove(self.controls[""])
            self.setup_info_table(table,
                                  [("Slave IO State:", repl.get("Slave_IO_State")),
                                   ("Master Host:", repl.get("Master_Host")),
                                   ("GTID Mode:", info.get("gtid_mode"))])
        else:
            self.controls[""].set_text(repl_error or "this server is not a slave in a replication setup")
        table.relayout()
        self.resume_layout()


    def create_ui(self):
        info = self.ctrl_be.server_variables
        plugins = dict(self.ctrl_be.server_active_plugins) # plugin -> type

        repl = {}
        disk_space = "checking..."

        def tristate(value, true_value = None):
            if true_value is not None and value == true_value:
                return True
            if value == "OFF" or value == "NO":
                return False
            elif value and true_value is None:
                return True
            return None

        semi_sync_master = tristate(info.get("rpl_semi_sync_master_enabled"))
        semi_sync_slave = tristate(info.get("rpl_semi_sync_slave_enabled"))
        if not repl:
            if semi_sync_master:
                semi_sync_master = False
            if semi_sync_slave:
                semi_sync_slave = False

        self.add_info_section_2("Available Server Features",
                              [("Performance Schema:", tristate(info.get("performance_schema"))),
                               ("Thread Pool:", tristate(info.get("thread_handling"), "loaded-dynamically")),
                               ("Memcached Plugin:", tristate(info.get("daemon_memcached_option"))),
                               ("Semisync Replication Plugin:", (semi_sync_master or semi_sync_slave, "(%s)"% ", ".join([x for x in [semi_sync_master and "master", semi_sync_slave and "slave"] if x]))),
                               ("SSL Availability:", info.get("have_openssl") == "YES" or info.get("have_ssl") == "YES"),
                               ("Windows Authentication:", plugins.has_key("authentication_windows")) if self.server_profile.target_is_windows else ("PAM Authentication:", plugins.has_key("authentication_pam")),
                               ("Password Validation:", (tristate(info.get("validate_password_policy")), "(Policy: %s)" % info.get("validate_password_policy"))),
                               ("Audit Log:", (tristate(info.get("audit_log_policy")), "(Log Policy: %s)" % info.get("audit_log_policy")))])

        log_output = info.get("log_output", "FILE")

        self.add_info_section("Server Directories",
                              [("Base Directory:", info.get("basedir")),
                               ("Data Directory:", info.get("datadir")),
                               ("Disk Space in Data Dir:", disk_space),
                               ("InnoDB Data Directory:", info.get("innodb_data_home_dir")) if info.get("innodb_data_home_dir") else None,
                               ("Plugins Directory:", info.get("plugin_dir")),
                               ("Tmp Directory:", info.get("tmpdir")),
                               ("Error Log:", (info.get("log_error") and info.get("log_error")!="OFF", info.get("log_error"))),
                               ("General Log:", (info.get("general_log")!="OFF" and log_output != "NONE", info.get("general_log_file") if "FILE" in log_output else "[Stored in database]")),
                               ("Slow Query Log:", (info.get("slow_query_log")!="OFF" and log_output != "NONE", info.get("slow_query_log_file") if "FILE" in log_output else "[Stored in database]"))])

        self.add_info_section("Replication Slave",
                              [("", "checking...")])

        self.add_info_section("Authentication",
                              [("SHA256 password private key:", info.get("sha256_password_private_key_path")),
                               ("SHA256 password public key:", info.get("sha256_password_public_key_path"))])

        self.add_info_section("SSL",
                              [("SSL CA:", info.get("ssl_ca") or "n/a"),
                               ("SSL CA path:", info.get("ssl_capath") or "n/a"),
                               ("SSL Cert:", info.get("ssl_cert") or "n/a"),
                               ("SSL Cipher:", info.get("ssl_cipher") or "n/a"),
                               ("SSL CRL:", info.get("ssl_crl") or "n/a"),
                               ("SSL CRL path:", info.get("ssl_crlpath") or "n/a"),
                               ("SSL Key:", info.get("ssl_key") or "n/a")])



    def mkswitch(self, state, text = None):
        box = mforms.newBox(True)
        box.set_spacing(8)
        image = mforms.newImageBox()
        box.add(image, False, True)
        if state:
            image.set_image(self.on_icon)
            box.add(mforms.newLabel("On"), False, True)
        elif state is None:
            image.set_image(self.off_icon)
            box.add(mforms.newLabel("n/a"), False, True)
        else:
            image.set_image(self.off_icon)
            box.add(mforms.newLabel("Off"), False, True)
        if text:
            l = mforms.newLabel(text)
            l.set_style(mforms.BoldStyle)
            l.set_color("#555555")
            box.add(l, False, True)
        return box


    def add_info_section_2(self, title, info):
        label = mforms.newLabel(title)
        label.set_style(mforms.BigBoldStyle)
        label.set_color("#5f5f5f")
        self.content.add(label, False, True)
        sep = mforms.newBox(False)
        sep.set_back_color("#b2b2b2")
        sep.set_size(-1, 1)
        self.content.add(sep, False, True)

        hbox = mforms.newBox(True)

        info_table = self.make_info_table(info[:len(info)/2])
        hbox.add(info_table, True, True)
        info_table = self.make_info_table(info[len(info)/2:])
        hbox.add(info_table, True, True)

        self.content.add(hbox, False, True)


    def add_info_section(self, title, info):
        label = mforms.newLabel(title)
        label.set_style(mforms.BigBoldStyle)
        label.set_color("#5f5f5f")
        self.content.add(label, False, True)
        sep = mforms.newBox(False)
        sep.set_back_color("#b2b2b2")
        sep.set_size(-1, 1)
        self.content.add(sep, False, True)

        info_table = self.make_info_table([x for x in info if x])
        self.content.add(info_table, False, True)
        self.controls[title] = info_table


    def make_info_table(self, info):
        info_table = mforms.newTable()
        info_table.set_column_spacing(8)
        info_table.set_row_spacing(6)
        info_table.set_column_count(2)
        return self.setup_info_table(info_table, info)


    def setup_info_table(self, info_table, info):
        info_table.set_row_count(len(info)+1)
        for i, item in enumerate(info):
            (label, value) = item

            if self.controls.has_key(label):
                info_table.remove(self.controls[label])
            else:
                info_table.add(mforms.newLabel(label), 0, 1, i, i+1, mforms.HFillFlag)

            if type(value) is bool or value is None:
                b = self.mkswitch(value)
                info_table.add(b, 1, 2, i, i+1, mforms.HFillFlag|mforms.HExpandFlag)
                self.controls[label] = b
            elif type(value) is tuple:
                b = self.mkswitch(value[0], value[1] if value[0] else None)
                info_table.add(b, 1, 2, i, i+1, mforms.HFillFlag|mforms.HExpandFlag)
                self.controls[label] = b
            else:
                l2 = mforms.newLabel(value or "")
                l2.set_style(mforms.BoldStyle)
                l2.set_color("#1c1c1c")
                info_table.add(l2, 1, 2, i, i+1, mforms.HFillFlag|mforms.HExpandFlag)
                self.controls[label] = l2
        info_table.add(mforms.newLabel(""), 0, 1, len(info), len(info)+1, mforms.HFillFlag) # blank space
        return info_table


    #---------------------------------------------------------------------------
    def page_deactivated(self):
        pass
    
    #---------------------------------------------------------------------------
    def shutdown(self):
        self.status.stop()

