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

from mforms import newTreeNodeView, newButton, newBox, newSelector, newCheckBox, newLabel, Utilities
import mforms
import grt

from functools import partial

from wb_common import dprint_ex
from wb_admin_utils import not_running_warning_label, weakcb, make_panel_header

class WbAdminConnections(mforms.Box):
    ui_created = False
    serial = 0

    @classmethod
    def wba_register(cls, admin_context):
        admin_context.register_page(cls, "wba_management", "Client Connections", False)

    @classmethod
    def identifier(cls):
        return "admin_connections"

    def __init__(self, ctrl_be, instance_info, main_view):
        mforms.Box.__init__(self, False)
        self.set_managed()
        self.set_release_on_add()
        self.set_padding(12)
        self.set_spacing(12)
        self.instance_info = instance_info
        self.ctrl_be = ctrl_be
        self.page_active = False
        self.main_view = main_view

    
    def create_ui(self):
        dprint_ex(4, "Enter")
        self.suspend_layout()

        self.heading = make_panel_header("title_connections.png", self.instance_info.name, "Client Connections")
        self.add(self.heading, False, False)

        self.warning = not_running_warning_label()
        self.add(self.warning, False, True)

        self.connection_list = newTreeNodeView(mforms.TreeDefault|mforms.TreeFlatList|mforms.TreeAltRowColors)
        self.connection_list.add_column(mforms.LongIntegerColumnType, "Id", 50, False)
        self.connection_list.add_column(mforms.StringColumnType, "User", 80, False)
        self.connection_list.add_column(mforms.StringColumnType, "Host", 120, False)
        self.connection_list.add_column(mforms.StringColumnType, "DB", 100, False)
        self.connection_list.add_column(mforms.StringColumnType, "Command", 80, False)
        self.connection_list.add_column(mforms.LongIntegerColumnType, "Time", 60, False)
        self.connection_list.add_column(mforms.StringColumnType, "State", 80, False)
        self.info_column = self.connection_list.add_column(mforms.StringColumnType, "Info", 300, False)
        self.connection_list.end_columns()
        self.connection_list.set_allow_sorting(True)
        
        self.connection_list.add_changed_callback(weakcb(self, "connection_selected"))
        
        #self.set_padding(8)
        self.add(self.connection_list, True, True)
        
        self.button_box = box = newBox(True)
        
        box.set_spacing(12)
        
        refresh_button = newButton()
        refresh_button.set_text("Refresh")
        box.add_end(refresh_button, False, True)
        refresh_button.add_clicked_callback(weakcb(self, "refresh"))

        self.kill_button = newButton()
        self.kill_button.set_text("Kill Connection")
        box.add_end(self.kill_button, False, True)
        self.kill_button.add_clicked_callback(weakcb(self, "kill_connection"))
        
        self.killq_button = newButton()
        self.killq_button.set_text("Kill Query")
        box.add_end(self.killq_button, False, True)
        self.killq_button.add_clicked_callback(weakcb(self, "kill_query"))
        
        refresh_label = newLabel("Refresh Rate:")
        box.add(refresh_label, False, True)

        self._menu = mforms.newContextMenu()
        self._menu.add_item_with_title("Copy Info", self.copy_selected, "copy_selected")
        self._menu.add_item_with_title("Show in Editor", self.edit_selected, "edit_selected")
        self.connection_list.set_context_menu(self._menu)

        
        self.refresh_values = [0.5, 1, 2, 3, 4, 5, 10, 15, 30]
        self.refresh_values_size = len(self.refresh_values)
        
        self.refresh_selector = newSelector()
        self.refresh_selector.set_size(100,-1)
        
        for s in self.refresh_values:
            self.refresh_selector.add_item(str(s) + " seconds")
        
        self.refresh_selector.add_item("Don't Refresh")
        
        refresh_rate_index = grt.root.wb.options.options.get('Administrator:refresh_connections_rate_index', 9)
        self.refresh_selector.set_selected(refresh_rate_index)
        self.update_refresh_rate()
        self.refresh_selector.add_changed_callback(weakcb(self, "update_refresh_rate"))
        box.add(self.refresh_selector, False, True)

        self.hide_sleep_connections = newCheckBox()
        self.hide_sleep_connections.set_text('Hide sleeping connections')
        self.hide_sleep_connections.add_clicked_callback(self.refresh)
        box.add(self.hide_sleep_connections, False, True)
        
        self.add(box, False, True)
        
        self.resume_layout()
        
        self.connection_selected()
        dprint_ex(4, "Leave")
    
    
    def connection_selected(self):
        dprint_ex(4, "Enter")
        if not self.connection_list.get_selected_node():
            self.kill_button.set_enabled(False)
            self.killq_button.set_enabled(False)
        else:
            self.kill_button.set_enabled(True)
            self.killq_button.set_enabled(True)
        dprint_ex(4, "Leave")
    
    def page_activated(self):
        if not self.ui_created:
            self.create_ui()
            self.ui_created = True
        
        self.page_active = True
        if self.ctrl_be.is_sql_connected():
            self.warning.show(False)
            self.heading.show(True)
            self.connection_list.show(True)
            self.button_box.show(True)
        else:
            self.warning.show(True)
            self.heading.show(False)
            self.connection_list.show(False)
            self.button_box.show(False)
        
        self.refresh()
    
    def page_deactivated(self):
        self.page_active = False
    
    def get_process_list(self):
        fields = ["Id", "User", "Host", "db", "Command", "Time", "State", "Info"]
        result = self.ctrl_be.exec_query("SHOW FULL PROCESSLIST")
        if result is not None:
            result_rows = []
            while result.nextRow():
                row = []
                for field in fields:
                    value = result.stringByName(field)
                    row.append(value)
                result_rows.append(row)
            return result_rows
        
        return None
    
    
    def update_refresh_rate(self):
        index = int(self.refresh_selector.get_selected_index())
        grt.root.wb.options.options['Administrator:refresh_connections_rate_index'] = index
        self.serial += 1
        if (index < self.refresh_values_size):
            Utilities.add_timeout(self.refresh_values[index], partial(self.refresh, my_serial = self.serial))
    
    def copy_selected(self):
        sel = self.connection_list.get_selected_node()
        if not sel:
            return
        
        info = sel.get_tag()
        mforms.Utilities.set_clipboard_text(info)


    def edit_selected(self):
        sel = self.connection_list.get_selected_node()
        if not sel:
            return

        text = []
        text.append("-- Thread Id: %s\n" % sel.get_long(0))
        text.append("-- User: %s\n" % sel.get_string(1))
        text.append("-- Host: %s\n" % sel.get_string(2))
        text.append("-- DB: %s\n" % sel.get_string(3))
        text.append("-- Command: %s\n" % sel.get_string(4))
        text.append("-- Time: %s\n" %  sel.get_long(5))
        text.append("-- State: %s\n" % sel.get_string(6))

        info = sel.get_tag()
        text.append(info)
        editor = self.main_view.editor.addQueryEditor()
        editor.replaceContents("".join(text))


    def refresh(self, query_result = None, my_serial = 0):
        if not self.ctrl_be.is_sql_connected():
            dprint_ex(2, "Leave. SQL connection is offline")
            return False
        
        if not self.page_active:
            dprint_ex(2, "Leave. Page is inactive")
            return False
        
        node = self.connection_list.get_selected_node()
        if node:
            old_selected = node.get_long(0)
        else:
            old_selected = None
        old_selected_node = None
        
        if query_result is None:
            query_result = self.get_process_list()
        
        if query_result is not None:
            self.connection_list.freeze_refresh()
            self.connection_list.clear()
            no_sleep_connections = self.hide_sleep_connections.get_active()
            try:
                for row in query_result:
                    if no_sleep_connections and str(row[4]).startswith('Sleep'):
                        continue
                    r = self.connection_list.add_node()
                    for c, field in enumerate(row):
                        if c == 0:
                            try:
                                field = long(field)
                            except Exception:
                                field = 0
                            r.set_long(c, field)
                            if field == old_selected:
                                old_selected_node = r
                        elif c == 5:
                            try:
                                field = long(field)
                            except Exception:
                                field = 0
                            r.set_long(c, field)
                        elif c == 7:
                            # truncate Info column to 255 chars for display, since they can be REALLY long
                            # which causes GDI trouble in Windows... so just store the full info in the tag
                            if field is not None:
                                r.set_string(c, field[:255])
                            else:
                                r.set_string(c, "NULL")
                            r.set_tag(field or "")
                        else:
                            field = str(field)
                            r.set_string(c, field)
            
            finally:
                self.connection_list.thaw_refresh()
            
            if old_selected_node:
                self.connection_list.select_node(old_selected_node)
            
            self.connection_selected()
        
        return (my_serial == self.serial)
    
    
    
    def kill_connection(self):
        if not self.ctrl_be.is_sql_connected():
            return
        
        sel = self.connection_list.get_selected_node()
        if not sel:
            return
        
        connid = sel.get_long(0)
        try:
            self.ctrl_be.exec_sql("KILL CONNECTION %s"%connid)
        except Exception, e:
            raise Exception("Error executing KILL CONNECTION: %s" % e)
        
        self.refresh()
    
    
    def kill_query(self):
        if not self.ctrl_be.is_sql_connected():
            return
        
        sel = self.connection_list.get_selected_node()
        if not sel:
            return
        
        connid = sel.get_long(0)
        try:
            self.ctrl_be.exec_sql("KILL QUERY %s"%connid)
        except Exception, e:
            raise Exception("Error executing KILL QUERY: %s" % e)
        
        self.refresh()
