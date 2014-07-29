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
import os

from grt import log_debug3

_this_file = os.path.basename(__file__)

class ChangeTracker(object):
    """
    ChangeTracker is a class in charge of keeping track of the 
    changes done to the attributes in a subclass.

    As 'change' we understand any change done from a starting point
    which by default is after __init__ is called (not necessarily).

    i.e. when an attribue is created by the first time that is considered
    it's starting point, from there, if the value is changed it is already
    considered a change.

    The starting point can be also re-defined by calling reset_changes.
    """
    def __init__(self):
        self.__changed = {}
        self.__ignoring = 0

    def __setattr__(self, name, value):
        # Verifies the value being set is a valid attribute
        # Also ensures the value is changing from the current value
        if name in self.__dict__ and \
           name != '_ChangeTracker__changed' and \
           name != '_ChangeTracker__ignoring' and \
           not self.__ignoring and \
           self.__dict__[name] != value:

            log_message = "Changed %s from %s to %s at %s\n" % (name, self.__dict__[name], value, self)

            # If the value was already changed and the new value
            # reverts the change then it removes the attribute from
            # the changed map
            if name in self.__dict__["_ChangeTracker__changed"]:
                if self.__dict__["_ChangeTracker__changed"][name] == value:
                    del self.__dict__["_ChangeTracker__changed"][name]
                    log_message = "Reverted change on %s to %s at %s\n" % (name, value, self)

            # If this is the first change to the attribute, registers the
            # Original value on the changed map
            else:
                self.__dict__["_ChangeTracker__changed"][name] = self.__dict__[name]
            
            # Logs the change
            log_debug3(_this_file, log_message)

        # Updates the value
        self.__dict__[name] = value

    def has_changed(self, name = None):
        """
        Verifies if there are changes on the class attributes.
        If name is given it will verify for changes on that specific attribute.
        If not, will verify for changes on any attribute.
        """
        if name:
            return name in self.__changed
        else:
            return len(self.__changed) > 0

    def get_changes(self, name = None):
        """
        Retrieves the changes on the class attributes as tuples.
        If name is given it will return a tuple containing the (initial, current) values
        If not, it will return a list of tuples as (attribute, initial, current)

        If there are no changes it will return None.
        """
        if name and name in self.__changed:
            return (self.__changed[name], self.__dict__[name])
        elif name is None and len(self.__changed):
            return [(att, self.__changed[att], self.__dict__[att]) for att in self.__changed]
        else:
            return None

    def set_ignoring(self, value):
        """ 
        Used to turn ON/OFF the change detection mechanism.
        """ 
        increase = 1 if value else -1
        self.__ignoring = self.__ignoring + increase

    def reset_changes(self):
        """
        Clears any registered change to create a new starting point.
        """
        self.__changed={}
        
class ignore_changes(object):
    """
    IgnoreChanges Decorator
    It's purpose is to add the decorator on those methods
    for which the change detection will be turned off.

    It will only have effect on those classes childs of ChangeTracker.
    """
    def __init__(self, func):
        self.func = func
        self.instance = None

    def __call__(self, *args):
        if isinstance(self.instance, ChangeTracker):
            self.instance.set_ignoring(True)
            ret_val = self.func(*args)
            self.instance.set_ignoring(False)
            return ret_val

    def __get__(self, obj, objtype):
        self.instance = obj
        import functools
        return functools.partial(self.__call__, obj)
        