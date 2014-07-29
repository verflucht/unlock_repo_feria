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

import weakref

from mforms import Utilities, newLabel
import mforms

from workbench.db_utils import MySQLConnection, MySQLError

#-------------------------------------------------------------------------------
def get_db_connection(server_instance_settings):
    if server_instance_settings.connection:
        db_connection = MySQLConnection(server_instance_settings.connection)
        ignore_error = False
        error_location = None
        the_error = None
        try:
            db_connection.connect()
        except MySQLError, exc:
         # errors that probably just mean the server is down can be ignored (ex 2013)
         # errors from incorrect connect parameters should raise an exception
         # ex 1045: bad password
            if exc.code in (1045,):
                raise exc
            elif exc.code in (2013,):
                ignore_error = True
            error_location = exc.location
            the_error = str(exc)

            if not ignore_error:
                if Utilities.show_warning("Could not connect to MySQL Server at %s" % error_location,
                        "%s\nYou can continue but some functionality may be unavailable." % the_error,
                        "Continue Anyway", "Cancel", "") != mforms.ResultOk:
                    raise MySQLError("", 0, "")
        return db_connection
    else:
        Utilities.show_warning("WB Admin", "Server instance has no database connection specified.\nSome functionality will not be available.", "OK", "", "")


    return None




def weakcb(object, cbname):
    """Create a callback that holds a weak reference to the object. When passing a callback
    for mforms, use this to create a ref to it and prevent circular references that are never freed.
    """
    def call(ref, cbname):
        callback = getattr(ref(), cbname, None)
        if callback is None:
            print "Object has no callback %s"%cbname
        else:
            return callback()

    return lambda ref=weakref.ref(object): call(ref, cbname)


not_running_warning_label_text = "There is no connection to the MySQL Server.\nThis functionality requires an established connection to a running MySQL server to work."
def not_running_warning_label():
    warning = newLabel("\n\n\n\n"+not_running_warning_label_text)
    warning.set_style(mforms.BigStyle)
    warning.set_text_align(mforms.MiddleCenter)
    warning.show(False)
    return warning

def no_remote_admin_warning_label(server_instance_settings):
    if server_instance_settings.uses_ssh:
        warning = newLabel("There is no SSH connection to the server.\nTo use this functionality, the server where MySQL is located must have a SSH server running\nand you must provide its login information in the server profile.")
    else:
        if server_instance_settings.uses_wmi:
            warning = newLabel("There is no WMI connection to the server.\nTo use this functionality, the server where MySQL is located must be configured to use WMI\nand you must provide its login information in the server profile.")
        else:
            warning = newLabel("Remote Administration is disabled.\nTo use this functionality, the server where MySQL is located must either have an SSH server running\nor alternatively, if it is a Windows machine, must have WMI enabled.\nAdditionally you must enable remote administration in the server profile, providing login details for it.")
    warning.set_style(mforms.BigStyle)
    warning.set_text_align(mforms.MiddleCenter)
    return warning


def make_panel_header(icon, title, subtitle, button=None):
    table = mforms.newTable()
    table.set_row_count(2)
    table.set_column_count(3)
    table.set_row_spacing(0)
    table.set_column_spacing(15)
    image = mforms.newImageBox()
    image.set_image(mforms.App.get().get_resource_path(icon))
    image.set_image_align(mforms.TopCenter)
    table.add(image, 0, 1, 0, 2, mforms.HFillFlag)
    label = mforms.newLabel(title)
    label.set_style(mforms.SmallStyle)
    table.add(label, 1, 2, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)
    label = mforms.newLabel(subtitle)
    label.set_style(mforms.VeryBigStyle)
    table.add(label, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)
    if button:
        table.add(button, 2, 3, 0, 2, mforms.HFillFlag)
    return table

