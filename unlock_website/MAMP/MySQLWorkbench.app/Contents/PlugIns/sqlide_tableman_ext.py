# Copyright (c) 2013, Oracle and/or its affiliates. All rights reserved.
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


import mforms
import grt

import os
from grt import log_error
_this_file = os.path.basename(__file__)


def show_table_inspector(editor, selection):
    for schema, table in selection:
        sman = TableInspector(editor)
        sman.show_tables(schema, table)
        dpoint = mforms.fromgrt(editor.dockingPoint)
        dpoint.dock_view(sman, "", 0)
        dpoint.select_view(sman)
        sman.set_title("%s.%s" % (schema, table))


def handleLiveTreeContextMenu(name, sender, args):
    menu = mforms.fromgrt(args['menu'])
    selection = args['selection']

    # Add extra menu items to the SQL editor live schema tree context menu
    tables_selected = []

    for s in selection:
        if s.type == 'db.Table':
            tables_selected.append((s.schemaName, s.name))
        else:
            return
    if selection:
        item = mforms.newMenuItem("Table Inspector")
        item.add_clicked_callback(lambda: show_table_inspector(sender, tables_selected))
        menu.insert_item(0, item)


class TableInfoPanel(mforms.Box):
    def __init__(self):
        mforms.Box.__init__(self, False)
        self.set_managed()
        self.set_release_on_add()

        table = mforms.newTable()
        table.set_row_count(8)
        table.set_column_count(2)
        table.set_row_spacing(8)
        table.set_column_count(4)

        table.add(mforms.newLabel(""), 0, 1, 0, 1, mforms.HFillFlag)

        self.add(table, True, True)


class CreateIndexForm(mforms.Form):
    def __init__(self, owner, editor, schema, table, columns):
        mforms.Form.__init__(self, mforms.Form.main_form(), mforms.FormNormal)

        self._owner = owner
        self._editor = editor
        self._schema = schema
        self._table = table
        self._columns = columns

        self.set_title("Create Index for Table %s.%s" % (schema, table))

        content = mforms.newBox(False)
        self.set_content(content)
        content.set_padding(20)
        content.set_spacing(12)

        table = mforms.newTable()
        table.set_row_count(7)
        table.set_column_count(2)
        table.set_row_spacing(8)
        table.set_column_spacing(8)
        content.add(table, False, True)

        table.add(mforms.newLabel("Index Name:", True), 0, 1, 0, 1, mforms.HFillFlag)
        hbox = mforms.newBox(True)
        hbox.set_spacing(12)
        self.name = mforms.newTextEntry()
        hbox.add(self.name, True, True)
        self.kind = mforms.newSelector()
        self.kind.add_items(["Non-Unique", "Unique", "FullText", "Spatial"])
        hbox.add(self.kind, False, True)
        table.add(hbox, 1, 2, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)

        table.add(mforms.newLabel("Type:", True), 0, 1, 1, 2, mforms.HFillFlag)
        self.type = mforms.newSelector()
        self.type.add_items(["BTREE", "HASH"])
        table.add(self.type, 1, 2, 1, 2, mforms.HFillFlag)

        l = mforms.newLabel("Columns:")
        l.set_text_align(mforms.TopRight)
        table.add(l, 0, 1, 2, 3, mforms.HFillFlag|mforms.VFillFlag)
        self.columns = mforms.newTreeNodeView(mforms.TreeFlatList)
        self.columns.add_column(mforms.StringColumnType, "Column", 200, False)
        self.columns.add_column(mforms.StringColumnType, "Length", 60, True)
        #        self.columns.add_column(mforms.CheckColumnType, "Order", 50, False) # ignored by server
        self.columns.end_columns()
        self.columns.set_size(-1, 80)
        tbl = mforms.newTable()
        tbl.set_row_count(3)
        tbl.set_column_count(2)
        tbl.set_row_spacing(2)
        tbl.set_column_spacing(4)
        tbl.add(self.columns, 0, 1, 0, 3, mforms.HFillFlag|mforms.VFillFlag|mforms.HExpandFlag)
        self.move_up = mforms.newButton()
        self.move_up.set_text("\xe2\x96\xb2")
        self.move_up.add_clicked_callback(self.move_row_up)
        self.move_up.enable_internal_padding(False)
        self.move_down = mforms.newButton()
        self.move_down.set_text("\xe2\x96\xbc")
        self.move_down.add_clicked_callback(self.move_row_down)
        self.move_down.enable_internal_padding(False)
        tbl.add(self.move_up, 1, 2, 0, 1, mforms.HFillFlag)
        tbl.add(self.move_down, 1, 2, 1, 2, mforms.HFillFlag)
        tbl.add(mforms.newLabel(""), 1, 2, 2, 3, mforms.HFillFlag|mforms.VExpandFlag)
        table.add(tbl, 1, 2, 2, 3, mforms.HFillFlag)

        l = mforms.newLabel("Comments:")
        l.set_text_align(mforms.TopRight)
        table.add(l, 0, 1, 3, 4, mforms.HFillFlag|mforms.VFillFlag)
        self.comments = mforms.newTextBox(0)
        self.comments.set_size(-1, 60)
        if self._editor.serverVersion.majorNumber > 5 or (self._editor.serverVersion.majorNumber == 5 and self._editor.serverVersion.minorNumber >= 5):
            pass
        else:
            self.comments.set_enabled(False)
        table.add(self.comments, 1, 2, 3, 4, mforms.HFillFlag|mforms.VFillFlag)

        online_ddl_ok = self._editor.serverVersion.majorNumber > 5 or (self._editor.serverVersion.majorNumber == 5 and self._editor.serverVersion.minorNumber >= 6)

        if online_ddl_ok:
            l = mforms.newLabel("\nCreate/Online Options")
        else:
            l = mforms.newLabel("\nCreate/Online Options (requires MySQL 5.6+)")
            l.set_enabled(False)
        l.set_style(mforms.BoldStyle)
        table.add(l, 1, 2, 4, 5, mforms.HFillFlag)
        table.add(mforms.newLabel("Algorithm:", True), 0, 1, 5, 6, mforms.HFillFlag)
        self.algorithm = mforms.newSelector()
        self.algorithm.add_items(["Default", "Copy", "InPlace"])
        self.algorithm.set_enabled(online_ddl_ok)
        table.add(self.algorithm, 1, 2, 5, 6, mforms.HFillFlag)

        table.add(mforms.newLabel("Locking:", True), 0, 1, 6, 7, mforms.HFillFlag)
        self.lock = mforms.newSelector()
        self.lock.add_items(["Default (allow as much concurrency as possible)", "Exclusive (totally block access to table)", "Shared (allow queries but not DML)", "None (allow queries and DML)"])
        self.lock.set_enabled(online_ddl_ok)
        table.add(self.lock, 1, 2, 6, 7, mforms.HFillFlag)

        bbox = mforms.newBox(True)
        bbox.set_spacing(12)
        self.ok = mforms.newButton()
        self.ok.set_text("Create")

        self.cancel = mforms.newButton()
        self.cancel.set_text("Cancel")

        mforms.Utilities.add_end_ok_cancel_buttons(bbox, self.ok, self.cancel)
        content.add_end(bbox, False, True)

        self.set_size(550, -1)
        self.center()

    def move_row_up(self):
        node = self.columns.get_selected_node()
        if node:
            row = self.columns.row_for_node(node)
            if row > 0:
                name, length = node.get_string(0), node.get_string(1)
                new_node = self.columns.root_node().insert_child(row-1)
                new_node.set_string(0, name)
                new_node.set_string(1, length)
                node.remove_from_parent()
                self.columns.select_node(new_node)

    def move_row_down(self):
        node = self.columns.get_selected_node()
        if node:
            row = self.columns.row_for_node(node)
            if row < self.columns.count()-1:
                name, length = node.get_string(0), node.get_string(1)
                node.remove_from_parent()
                new_node = self.columns.root_node().insert_child(row+1)
                new_node.set_string(0, name)
                new_node.set_string(1, length)
                self.columns.select_node(new_node)

    def run(self):
        name = "idx_%s_%s" % (self._table, "_".join(self._columns))
        self.name.set_value(name)

        for c in self._columns:
            node = self.columns.add_node()
            node.set_string(0, c)

        if self.run_modal(self.ok, self.cancel):
            columns = []
            for i in range(self.columns.count()):
                node = self.columns.node_at_row(i)
                c = node.get_string(0)
                l = node.get_string(1)
                if l:
                    columns.append("%s(%s)" % (c, l))
                else:
                    columns.append(c)
            kind = self.kind.get_string_value().upper()
            if self.kind.get_selected_index() == 0:
                kind = ""
            else:
                kind = " "+kind
            sql = "CREATE%s INDEX `%s` USING %s ON `%s`.`%s` (%s)" % (kind, self.name.get_string_value(), self.type.get_string_value().upper(), self._schema, self._table, ", ".join(columns))
            if self._editor.serverVersion.majorNumber > 5 or (self._editor.serverVersion.majorNumber == 5 and self._editor.serverVersion.minorNumber >= 5):
                sql += " COMMENT '%s'" % self.comments.get_string_value().replace("'", "''") # 5.5
            if self._editor.serverVersion.majorNumber > 5 or (self._editor.serverVersion.majorNumber == 5 and self._editor.serverVersion.minorNumber >= 6):
                sql += " ALGORITHM %s" % self.algorithm.get_string_value().upper() # 5.6
                sql += " LOCK %s" % self.lock.get_string_value().upper().split()[0]
            try:
                self._editor.executeManagementCommand(sql, 1)
                return True
            except grt.DBError, e:
                mforms.Utilities.show_error("Create Index",
                                            "Error creating index.\n%s" % e.args[0],
                                            "OK", "", "")
        return True


class TableIndexInfoPanel(mforms.Box):
    def __init__(self, editor):
        mforms.Box.__init__(self, False)
        self.set_managed()
        self.set_release_on_add()

        self.set_padding(12)
        self.set_spacing(12)

        self.editor = editor

        # Upper Row
        table = mforms.newTable()
        table.set_row_count(2)
        table.set_column_count(2)
        table.set_row_spacing(4)
        table.set_column_spacing(8)
        self.add(table, False, True)

        def make_title(t):
            l = mforms.newLabel(t)
            l.set_style(mforms.BoldStyle)
            return l

        table.add(make_title("Indexes in Table"), 0, 1, 0, 1, mforms.HFillFlag)
        self.index_list = mforms.newTreeNodeView(mforms.TreeFlatList)
        self.index_list.add_column(mforms.IconStringColumnType, "Key", 140, False)
        self.index_list.add_column(mforms.StringColumnType, "Type", 80, False)
        self.index_list.add_column(mforms.StringColumnType, "Unique", 40, False)
        self.index_list.add_column(mforms.StringColumnType, "Columns", 200, False)
        self.index_list.end_columns()
        self.index_list.add_changed_callback(self.index_selected)
        self.index_list.set_size(400, -1)
        table.add(self.index_list, 0, 1, 1, 2, mforms.HFillFlag|mforms.VFillFlag)

        table.add(make_title("Index Details"), 1, 2, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)
        self.info = mforms.newTable()
        table.add(self.info, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag|mforms.VFillFlag)

        self.info.set_padding(8)
        self.info.set_row_count(9)
        self.info.set_column_count(2)
        self.info.set_row_spacing(4)
        self.info.set_column_spacing(4)

        self.info.add(mforms.newLabel("Key Name:"),        0, 1, 0, 1, mforms.HFillFlag)
        self.key_name = mforms.newLabel("")
        self.key_name.set_style(mforms.BoldStyle)
        self.info.add(self.key_name,                       1, 2, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Unique:"),           0, 1, 1, 2, mforms.HFillFlag)
        self.unique_values = mforms.newLabel("")
        self.unique_values.set_style(mforms.BoldStyle)
        self.info.add(self.unique_values,                  1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Index Type:"),      0, 1, 2, 3, mforms.HFillFlag)
        self.index_type = mforms.newLabel("")
        self.index_type.set_style(mforms.BoldStyle)
        self.info.add(self.index_type,                     1, 2, 2, 3, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Packed:"),          0, 1, 3, 4, mforms.HFillFlag)
        self.packed = mforms.newLabel("")
        self.packed.set_style(mforms.BoldStyle)
        self.info.add(self.packed,                         1, 2, 3, 4, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Allows NULL:"),     0, 1, 4, 5, mforms.HFillFlag)
        self.allows_null = mforms.newLabel("")
        self.allows_null.set_style(mforms.BoldStyle)
        self.info.add(self.allows_null,                    1, 2, 4, 5, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Comment:"),         0, 1, 5, 6, mforms.HFillFlag)
        self.comment = mforms.newLabel("")
        self.comment.set_style(mforms.BoldStyle)
        self.info.add(self.comment,                        1, 2, 5, 6, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("User Comment:"),    0, 1, 6, 7, mforms.HFillFlag)
        self.user_comment = mforms.newLabel("")
        self.user_comment.set_style(mforms.BoldStyle)
        self.info.add(self.user_comment,                   1, 2, 6, 7, mforms.HFillFlag|mforms.HExpandFlag)
        self.info.add(mforms.newLabel("Cardinality:"),     0, 1, 7, 8, mforms.HFillFlag)
        self.cardinality = mforms.newLabel("")
        self.cardinality.set_style(mforms.BoldStyle)
        self.info.add(self.cardinality,                    1, 2, 7, 8, mforms.HFillFlag|mforms.HExpandFlag)
        self.index_columns = mforms.newTreeNodeView(mforms.TreeFlatList)
        self.index_columns.add_column(mforms.StringColumnType, "Column", 150, False)
        self.index_columns.add_column(mforms.StringColumnType, "Sub part", 50, False)
        self.index_columns.add_column(mforms.StringColumnType, "Collation", 100, False)
        self.index_columns.end_columns()
        self.index_columns.set_size(-1, 70)
        self.info.add(self.index_columns,                  0, 2, 8, 9, mforms.HFillFlag|mforms.HExpandFlag|mforms.VFillFlag)

        # Lower Row
        table = mforms.newTable()
        table.set_row_count(2)
        table.set_column_count(2)
        table.set_row_spacing(4)
        table.set_column_spacing(8)
        self.add(table, True, True)

        table.add(make_title("Table Columns"), 0, 1, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)

        self.drop_index = mforms.newButton()
        self.drop_index.set_text("Drop Index")
        self.drop_index.set_enabled(False)
        self.drop_index.add_clicked_callback(self.do_drop_index)
        table.add(self.drop_index, 1, 2, 0, 1, mforms.HFillFlag)

        self.column_list = mforms.newTreeNodeView(mforms.TreeFlatList)
        self.column_list.add_column(mforms.IconStringColumnType, "Column", 150, False)
        self.column_list.add_column(mforms.StringColumnType, "Type", 150, False)
        self.column_list.add_column(mforms.StringColumnType, "Nullable", 50, False)
        self.column_list.add_column(mforms.StringColumnType, "Indexes", 300, False)
        self.column_list.end_columns()
        self.column_list.set_selection_mode(mforms.TreeSelectMultiple)
        table.add(self.column_list, 0, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag|mforms.VFillFlag|mforms.VExpandFlag)

        hbox = mforms.newBox(True)
        self.create_index = mforms.newButton()
        self.create_index.set_text("Create Index for Selected Columns...")
        self.create_index.add_clicked_callback(self.do_create_index)
        hbox.add_end(self.create_index, False, True)
        self.add(hbox, False, True)


    def do_drop_index(self):
        node = self.index_list.get_selected_node()
        if node:
            index = node.get_string(0)
            if mforms.Utilities.show_message("Drop Index", "Drop index `%s` from table `%s`.`%s`?" % (index, self._schema, self._table), "Drop", "Cancel", "") == mforms.ResultOk:
                try:
                    self.editor.executeManagementCommand("DROP INDEX `%s` ON `%s`.`%s`" % (index, self._schema, self._table), 1)
                    self.refresh()
                except grt.DBError, e:
                    mforms.Utilities.show_error("Drop Index", "Error dropping index.\n%s" % e.args[0], "OK", "", "")


    def do_create_index(self):
        cols = []
        for node in self.column_list.get_selection():
            cols.append(node.get_string(0))
        if cols:
            form = CreateIndexForm(self, self.editor, self._schema, self._table, cols)
            if form.run():
                self.refresh()


    def index_selected(self):
        node = self.index_list.get_selected_node()
        if node:
            idx = self.index_info[self.index_list.row_for_node(node)]

            info, columns = idx
            self.key_name.set_text(info[2])
            self.unique_values.set_text("NON UNIQUE" if info[1] == "1" else "UNIQUE")
            if info[2] == "PRIMARY" and self._engine and self._engine.lower() == "innodb":
                self.index_type.set_text("%s (clustered)" % info[6])
            else:
                self.index_type.set_text(info[6])
            self.cardinality.set_text(info[3])
            self.packed.set_text(info[4])
            self.allows_null.set_text(info[5])
            self.comment.set_text(info[7])
            self.user_comment.set_text(info[8])

            self.index_columns.clear()
            for seq, name, coll, subpart in columns:
                node = self.index_columns.add_node()
                node.set_string(0, name)
                node.set_string(1, subpart)
                node.set_string(2, "Ascending" if coll == "A" else "Not sorted")

            self.drop_index.set_enabled(True)
        else:
            self.drop_index.set_enabled(False)
            self.index_columns.clear()
            self.key_name.set_text("")
            self.unique_values.set_text("")
            self.index_type.set_text("")
            self.cardinality.set_text("")
            self.packed.set_text("")
            self.allows_null.set_text("")
            self.comment.set_text("")
            self.user_comment.set_text("")

    def refresh(self):
        self.show_table(self._schema, self._table)


    def show_table(self, schema, table):
        self._schema = schema
        self._table = table
        self._engine = None
        self.index_list.clear()
        self.index_info = []
        self.column_list.clear()
        column_icon = mforms.App.get().get_resource_path("db.Column.16x16.png")
        index_icon = mforms.App.get().get_resource_path("db.Index.16x16.png")
        if table:
            try:
                rset = self.editor.executeManagementQuery("SHOW INDEX FROM `%s`.`%s`" % (schema, table), 0)
            except grt.DBError, e:
                log_error("Cannot execute SHOW INDEX FROM `%s`.`%s`: %s" % (schema, table, e))
                rset = None

            index_rs_columns = range(13)
            column_rs_columns = [3, 4, 5, 7]
            for i in column_rs_columns:
                index_rs_columns.remove(i)
            column_to_index = {}
            if rset:
                ok = rset.goToFirstRow()
                curname = None
                columns = []
                while ok:
                    name = rset.stringFieldValue(2)
                    if name != curname:
                        if columns:
                            node = self.index_list.add_node()
                            node.set_icon_path(0, index_icon)
                            node.set_string(0, curname)
                            node.set_string(1, itype)
                            node.set_string(2, "YES" if non_unique != "1" else "NO")
                            node.set_string(3, ", ".join([c[1] for c in columns]))

                        columns = []
                        self.index_info.append(([rset.stringFieldValue(i) for i in index_rs_columns], columns))
                        curname = name

                    itype = rset.stringFieldValue(10)
                    non_unique = rset.stringFieldValue(1)
                    cname = rset.stringFieldValue(4)
                    if cname not in column_to_index:
                        column_to_index[cname] = [name]
                    else:
                        column_to_index[cname].append(name)
                    columns.append([rset.stringFieldValue(i) for i in column_rs_columns])
                    ok = rset.nextRow()
                if columns:
                    node = self.index_list.add_node()
                    node.set_icon_path(0, index_icon)
                    node.set_string(0, curname)
                    node.set_string(1, itype)
                    node.set_string(2, "YES" if non_unique != "1" else "NO")
                    node.set_string(3, ", ".join([c[1] for c in columns]))
            try:
                rset = self.editor.executeManagementQuery("SHOW COLUMNS FROM `%s`.`%s`" % (schema, table), 0)
            except grt.DBError, e:
                log_error("Cannot execute SHOW COLUMNS FROM `%s`.`%s`: %s" % (schema, table, e))
                rset = None

            if rset:
                ok = rset.goToFirstRow()
                while ok:
                    node = self.column_list.add_node()
                    node.set_icon_path(0, column_icon)
                    node.set_string(0, rset.stringFieldValue(0))
                    node.set_string(1, rset.stringFieldValue(1))
                    node.set_string(2, rset.stringFieldValue(2))
                    node.set_string(3, ", ".join(column_to_index.get(rset.stringFieldValue(0), [])))
                    ok = rset.nextRow()
        else:
            self.index_list.clear()
            self.column_list.clear()
            self.index_selected()



class TableInspector(mforms.AppView):
    def __init__(self, editor):
        mforms.AppView.__init__(self, False, "TableInspector", False)
        self.set_managed()
        self.set_release_on_add()

        self.tab = mforms.newTabView()
        self.add(self.tab, True, True)

        self.info = TableInfoPanel()
        self.tab.add_page(self.info, "Information")

        self.index_page = TableIndexInfoPanel(editor)
        self.tab.add_page(self.index_page, "Indexes")

        #        self.info = TableInfoPanel()
        #        self.add_page(self.info, "Partitioning")
        #
        #        self.info = TableInfoPanel()
        #        self.add_page(self.info, "Dependencies")


    def show_tables(self, schema, table):
        self.index_page.show_table(schema, table)


