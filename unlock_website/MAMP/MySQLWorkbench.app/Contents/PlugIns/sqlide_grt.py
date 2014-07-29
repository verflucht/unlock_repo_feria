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

# import the wb module
from wb import DefineModule, wbinputs
# import the grt module
import grt
# import the mforms module for GUI stuff
import mforms

import re
import os

from workbench.notifications import NotificationCenter

from sql_reformatter import formatter_for_statement_ast, ASTHelper
from text_output import TextOutputTab
from sqlide_catalogman_ext import show_schema_manager

from sqlide_resultset_ext import handleResultsetContextMenu
import sqlide_catalogman_ext
#import sqlide_tableman_ext
import sqlide_schematree_ext

# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "SQLIDEUtils", author= "Oracle Corp.", version="1.1")


@ModuleInfo.export(grt.INT)
def initialize0():
    nc = NotificationCenter()
    nc.add_observer(handleResultsetContextMenu, name = "GRNSQLResultsetMenuWillShow")

    sqlide_schematree_ext.init()

    # register a handler for when the SQLIDE live schema tree context menu is about to be shown
    nc.add_observer(sqlide_schematree_ext.handleLiveTreeContextMenu, name = "GRNLiveDBObjectMenuWillShow") # must be 1st
    nc.add_observer(sqlide_catalogman_ext.handleLiveTreeContextMenu, name = "GRNLiveDBObjectMenuWillShow")
    #nc.add_observer(sqlide_tableman_ext.handleLiveTreeContextMenu, name = "GRNLiveDBObjectMenuWillShow")



@ModuleInfo.export(grt.INT, grt.classes.db_query_EditableResultset)
def importRecordsetDataFromFile(resultset):
    file_chooser = mforms.newFileChooser(None, mforms.OpenFile)
    file_chooser.set_title('Import Recordset From CSV File')
    file_chooser.set_directory(os.path.expanduser('~'))
    file_chooser.set_extensions('CSV Files (*.csv)|*.csv', 'import')
    if file_chooser.run_modal():
        with open(file_chooser.get_path(), 'rb') as import_file:
            ext = os.path.splitext(import_file.name)[1].lower()
            import_module = None
            if ext == '.csv':
                import csv as import_module
            elif ext == '.sql':
                pass  # Here will go our not yet written .sql reader
            else:
                import csv as import_module
            if import_module:
                reader = import_module.reader(import_file)
                column_count = len(resultset.columns)
                type_classes = { 'string':str,
                                 'int':int,
                                 'real':float,
                                 'blob':str,
                                 'date':str,
                                 'time':str,
                                 'datetime':str,
                                 'geo':str,
                               }
                converters = tuple(type_classes[column.columnType] for column in resultset.columns)
                for row in reader:
                    if len(row) < column_count:  # Fill with default values
                        row.extend(converter() for converter in converters[len(row):])
                    try:
                        converted_values = [ converter(value) for converter, value in zip(converters, row) ]
                    except ValueError:
                        continue  # TODO: log a warning here
                    resultset.addNewRow()
                    for column, value in enumerate(converted_values):
                        if isinstance(value, str):
                            resultset.setStringFieldValue(column, value)
                        elif isinstance(value, int):
                            resultset.setIntFieldValue(column, value)
                        elif isinstance(value, float):
                            resultset.setFloatFieldValue(column, value)
                        else:
                            resultset.setFieldNull(column)
    return 0


@ModuleInfo.plugin("wb.sqlide.executeToTextOutput", caption= "Execute Query Into Text Output", input= [wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def executeQueryAsText(qbuffer):
    view = TextOutputTab("")

    dock = mforms.fromgrt(qbuffer.resultDockingPoint)
    dock.dock_view(view, "", 0)
    dock.select_view(view)
    dock.set_view_title(view, "Query Output")

    editor = qbuffer.owner
    sql = qbuffer.selectedText or qbuffer.script
    resultsets = editor.executeScript(sql)
    for result in resultsets:
        output = ["Execute:"]
        output.append("> %s\n" % result.sql)
        line = []
        column_lengths = []
        ncolumns = len(result.columns)
        for column in result.columns:
            line.append(column.name + " "*5)
            column_lengths.append(len(column.name)+5)

        separator = []
        for c in column_lengths:
            separator.append("-"*c)
        separator = " + ".join(separator)
        output.append("+ "+separator+" +")

        line = " | ".join(line)
        output.append("| "+line+" |")

        output.append("+ "+separator+" +\n")

        ok = result.goToFirstRow()
        if ok:
            view.textbox.append_text('\n'.join(output))

        import time
        
        last_flush = 0
        rows = []
        while ok:
            line = []
            for i in range(ncolumns):
              value = result.stringFieldValue(i)
              if value is None:
                value = "NULL"
              line.append(value.ljust(column_lengths[i]))
            line= " | ".join(line)
            rows.append("| "+line+" |")
            
            # flush text every 1/2s
            if time.time() - last_flush >= 0.5:
                last_flush = time.time()
                view.textbox.append_text("\n".join(rows)+"\n")
                rows = []
            ok = result.nextRow()

        if rows:
            view.textbox.append_text("\n".join(rows)+"\n")

        view.textbox.append_text("+ "+separator+" +\n")
        view.textbox.append_text("%i rows\n\n" % (result.currentRow + 1))

    return 0


@ModuleInfo.plugin('wb.sqlide.verticalOutput', caption='Vertical Output', input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def verticalOutput(editor):
    statement = editor.currentStatement
    if statement:
        rsets = editor.owner.executeScript(statement)
        rset = rsets and rsets[0]
        if rset:
            column_name_length = max(len(col.name) for col in rset.columns)
            output = [ '> %s\n' % rset.sql ]
            ok = rset.goToFirstRow()
            while ok:
                output.append('******************** %s. row *********************' % (rset.currentRow + 1))
                for column in rset.columns:
                    col_name, col_value = column.name.rjust(column_name_length), rset.stringFieldValueByName(column.name)
                    output.append('%s: %s' % (col_name, col_value if col_value is not None else 'NULL'))
                ok = rset.nextRow()
            output.append('%d rows in set' % (rset.currentRow + 1))

            view = TextOutputTab('\n'.join(output) + '\n')
            
            dock = mforms.fromgrt(editor.resultDockingPoint)
            dock.dock_view(view, '', 0)
            dock.select_view(view)
            dock.set_view_title(view, 'Vertical Output')
          
            rset.reset_references()
            
    return 0


def doReformatSQLStatement(text, return_none_if_unsupported):
    from grt.modules import MysqlSqlFacade
    ast_list = MysqlSqlFacade.parseAstFromSqlScript(text)
    if len(ast_list) != 1:
        raise Exception("Error parsing statement")
    if type(ast_list[0]) is str:
        raise Exception("Error parsing statement: %s" % ast_list[0])

    helper = ASTHelper(text)

    curpos = 0
    new_text = ""
    ast = ast_list[0]
    
    def trim_ast_fix_bq(text, node):
        s = node[0]
        v = node[1]
        c = node[2]
        # put back backquotes to identifiers, if there's any
        if s in ("ident", "ident_or_text"):
            begin = node[3] + node[4]
            end = node[3] + node[5]
            if begin > 0 and text[begin-1] == '`' and text[end] == '`':
                v = "`%s`" % v.replace("`", "``")
        l = []
        for i in c:
            l.append(trim_ast_fix_bq(text, i))
        return (s, v, l)

    formatter = formatter_for_statement_ast(ast)
    if formatter:
        p = formatter(trim_ast_fix_bq(text, ast))
        return p.run()
    else:
        if return_none_if_unsupported:
            return None
        return text

  
@ModuleInfo.export(grt.STRING, grt.STRING)
def reformatSQLStatement(text):
    return doReformatSQLStatement(text, False)


@ModuleInfo.plugin("wb.sqlide.enbeautificate", caption = "Reformat SQL Query", input=[wbinputs.currentQueryBuffer()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
def enbeautificate(editor):
    from grt.modules import MysqlSqlFacade

    text = editor.selectedText
    selectionOnly = True
    if not text:
        selectionOnly = False
        text = editor.script

    ok_count = 0
    bad_count = 0
    
    prev_end = 0
    new_text = []
    ranges = MysqlSqlFacade.getSqlStatementRanges(text)
    for begin, end in ranges:
        end = begin + end
        if begin > prev_end:
            new_text.append(text[prev_end:begin])
        statement = text[begin:end]
        
        # 
        stripped = statement.lstrip(" \t\r\n")
        leading = statement[:len(statement) - len(stripped)]
        statement = stripped
        stripped = statement.rstrip(" \t\r\n")
        if stripped != statement:
            trailing = statement[-(len(statement) - len(stripped)):]
        else:
            trailing = ""
        statement = stripped

        # if there's a comment at the start, then skip the comment until its end
        while True:
            if statement.startswith("-- "):
                comment, _, rest = statement.partition("\n")
                leading += comment+"\n"
                statement = rest
            elif statement.startswith("/*"):
                pos = statement.find("*/")
                if pos >= 0:
                    leading += statement[:pos+2]
                    statement = statement[pos+2:]
                else:
                    break
            else:
                break
        stripped = statement.lstrip(" \t\r\n")
        leading += statement[:len(statement) - len(stripped)]
        statement = stripped
        stripped = statement.rstrip(" \t\r\n")
        if stripped != statement:
            trailing += statement[-(len(statement) - len(stripped)):]
        statement = stripped                

        try:
            result = doReformatSQLStatement(statement, True)
        except:
            result = None
        if result:
            ok_count += 1
            if leading:
                new_text.append(leading.strip(" "))
            new_text.append(result)
            if trailing:
                new_text.append(trailing.strip(" "))
        else:
            bad_count += 1
            new_text.append(text[begin:end])
        prev_end = end
    new_text.append(text[prev_end:])

    new_text = "".join(new_text)

    if selectionOnly:
        editor.replaceSelection(new_text)
    else:
        editor.replaceContents(new_text)

    if bad_count > 0:
        mforms.App.get().set_status_text("Formatted %i statements, %i unsupported statement types skipped."%(ok_count, bad_count))
    else:
        mforms.App.get().set_status_text("Formatted %i statements."%ok_count)

    return 0



def apply_to_keywords(editor, callable):
    from grt.modules import MysqlSqlFacade
    non_keywords = ["ident", "TEXT_STRING", "text_string", "TEXT_STRING_filesystem", "TEXT_STRING_literal", "TEXT_STRING_sys",
                    "part_name"]

    text = editor.selectedText
    selectionOnly = True
    if not text:
        selectionOnly = False
        text = editor.script
    
    new_text = ""
    ast_list = MysqlSqlFacade.parseAstFromSqlScript(text)
    bb = 0
    for ast in ast_list:
        if type(ast) is str:
            # error
            print ast
            mforms.App.get().set_status_text("Cannot format invalid SQL: %s"%ast)
            return 1
        else:
            if 0: # debug
                from sql_reformatter import dump_tree
                import sys
                dump_tree(sys.stdout, ast)

            def get_keyword_offsets(offsets, script, node):
                s, v, c, base, b, e = node
                if v:
                    b += base
                    e += base
                    if s not in non_keywords:
                        offsets.append((b, e))
                for i in c:
                    get_keyword_offsets(offsets, script, i)

            offsets = []
            get_keyword_offsets(offsets, text, ast)
            for b, e in offsets:
                new_text += text[bb:b] + callable(text[b:e])
                bb = e
    new_text += text[bb:]

    if selectionOnly:
        editor.replaceSelection(new_text)
    else:
        editor.replaceContents(new_text)

    mforms.App.get().set_status_text("SQL code reformatted.")
    return 0


@ModuleInfo.plugin("wb.sqlide.upcaseKeywords", caption = "Make keywords in query uppercase", input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def upcaseKeywords(editor):
    return apply_to_keywords(editor, lambda s: s.upper())


@ModuleInfo.plugin("wb.sqlide.lowercaseKeywords", caption = "Make keywords in query lowercase", input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def lowercaseKeywords(editor):
    return apply_to_keywords(editor, lambda s: s.lower())


def get_lines_in_range(text, range_start, range_end):
    def intersects_range(start1, end1, start2, end2):
        if start1 <= start2 <= end1 or start1 <= end2 <= end1 or\
          start2 <= start1 <= end2 or start2 <= end1 <= end2:
            return True
        return False

    def split(text):
        lines = []
        while text:
            p = text.find("\n")
            if p >= 0:
                lines.append(text[0:p+1])
                text = text[p+1:]
            else:
                lines.append(text)
                break
        return lines

    all_lines = split(text)
    offs = 0
    lines = []
    first_line_start = None
    last_line_end = None
    for line in all_lines:
        line_start = offs
        line_end = offs+len(line)
        if intersects_range(range_start, range_end, line_start, line_end-1):
            if first_line_start is None:
                first_line_start = line_start
            last_line_end = line_end
            lines.append(line)
        offs = line_end
    return (first_line_start, last_line_end, lines)


@ModuleInfo.plugin("wb.sqlide.indent", caption = "Indent Selected Lines", input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def indent(editor):
    # indent and unindent handle selection a bit differently:
    # - if there is no selection, only the line where the cursor is should be indented
    # - if there is a selection, all selected lines should be indented, even if selected partially
        
    indentation = " "*4
    start = editor.selectionStart
    end = editor.selectionEnd
    full_text = editor.script
    if end > start:
        first_line_start, last_line_end, lines = get_lines_in_range(full_text, start, end)
        new_text = indentation + indentation.join(lines)
        last_line_end = end
        while last_line_end < len(full_text) and full_text[last_line_end-1] != "\n":
            last_line_end += 1
        if last_line_end != end:
            new_text = new_text[:-(last_line_end-end)]
        delta = len(lines) * len(indentation)
        editor.selectionStart = first_line_start
        editor.replaceSelection(new_text)
        # update cursor position
        editor.selectionEnd = end + delta
        editor.selectionStart = start + len(indentation)
    else:
        line_start = pos = editor.insertionPoint
        while line_start > 0 and full_text[line_start-1] != "\n":
            line_start -= 1
        editor.replaceContents(full_text[:line_start] + indentation + full_text[line_start:]) 
        editor.insertionPoint = pos + len(indentation)

    return 0



@ModuleInfo.plugin("wb.sqlide.unindent", caption = "Unindent Selected Lines", input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def unindent(editor):
    indentation = " "*4
    start = editor.selectionStart
    end = editor.selectionEnd
    full_text = editor.script

    if end > start:
        first_line_start, last_line_end, lines = get_lines_in_range(full_text, start, end)
        flag = False
        for i in range(len(lines)):
            if lines[i].startswith(indentation):
                lines[i] = lines[i][len(indentation):]
                flag = True
        if not flag:
            return
        if lines:
            last_line_start = last_line_end - len(lines[-1])
        else:
            last_line_start = last_line_end
        new_text = "".join(lines)
        last_line_end = end
        while last_line_end < len(full_text) and full_text[last_line_end-1] != "\n":
            last_line_end += 1
        if last_line_end != end:
            new_text = new_text[:-(last_line_end-end)]
        delta = len(lines) * len(indentation)
        # select to the beginning of the line, so that we can indent the whole block
        editor.selectionStart = first_line_start
        editor.replaceSelection(new_text)
        # update cursor position
        if start - len(indentation) > first_line_start:
            start = start - len(indentation)
        else:
            start = first_line_start
        if end - delta > last_line_start:
            end = end - delta
        else:
            end = last_line_start
        editor.selectionEnd = end 
        editor.selectionStart = start
    else:
        line_start = pos = editor.insertionPoint
        while line_start > 0 and full_text[line_start-1] != "\n":
            line_start -= 1
        if full_text[line_start:].startswith(indentation):
            editor.replaceContents(full_text[:line_start] + full_text[line_start+len(indentation):]) 
        if pos - len(indentation) >= line_start:
            editor.insertionPoint = pos - len(indentation)

    return 0


@ModuleInfo.plugin("wb.sqlide.comment", caption = "Un/Comment Selection", input=[wbinputs.currentQueryEditor()])
@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryEditor)
def commentText(editor):
    commentType = "%s " % grt.root.wb.options.options["DbSqlEditor:SQLCommentTypeForHotkey"]
    commentTypeLength = len(grt.root.wb.options.options["DbSqlEditor:SQLCommentTypeForHotkey"]) + 1
    text = editor.selectedText
    if text:
        lines = text.split("\n")
        if lines[0].startswith(commentType):
            new_text = "\n".join((line[commentTypeLength:] if line.startswith(commentType) else line) for line in lines)
        else:
            new_text = "\n".join(commentType + line for line in lines)
        editor.replaceSelection(new_text)
    else:
        pos = editor.insertionPoint
        full_text = editor.script
        done = False
        # if cursor is before or after a comment sequence, then delete that
        if full_text[pos:pos+commentTypeLength] == commentType:
            editor.replaceContents(full_text[:pos] + full_text[pos+commentTypeLength:])
            done = True
        else:
            for i in range(4):
                if full_text[pos+i:pos+i+commentTypeLength] == commentType:
                    editor.replaceContents(full_text[:pos+i] + full_text[pos+i+commentTypeLength:])
                    done = True
                    break
                if pos-i >= 0 and full_text[pos-i:pos-i+commentTypeLength] == commentType:
                    editor.replaceContents(full_text[:pos-i] + full_text[pos-i+commentTypeLength:])
                    done = True
                    pos -= i
                    break
       
        if not done:
            editor.replaceSelection(commentType)

        editor.insertionPoint = pos
    return 0


@ModuleInfo.export(grt.INT, grt.classes.db_query_Editor, grt.LIST)
def showSchemaInspector(editor, selection):
    show_schema_manager(editor, selection, False)
    return 0


#@ModuleInfo.plugin("wb.sqlide.refactor.renameSchema", caption = "Rename References to Schema Name", input=[wbinputs.currentQueryBuffer()]) # pluginMenu="SQL/Utilities"
#@ModuleInfo.export(grt.INT, grt.classes.db_query_QueryBuffer)
  #def refactorRenameSchema(editor):
#    pass

