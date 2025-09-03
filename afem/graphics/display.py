# This file is part of AFEM which provides an engineering toolkit for airframe
# finite element modeling during conceptual design.
#
# Copyright (C) 2016-2018  Laughlin Research, LLC (info@laughlinresearch.com)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
import os

from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Display.wxDisplay import wxViewer3d
from OCC.Display.SimpleGui import init_display

from afem.base.entities import ViewableItem
from afem.structure.group import Group


__all__ = ["Viewer"]

# Icon location
_icon = os.path.dirname(__file__) + '/resources/main.png'


class Viewer(wxViewer3d):
    """
    Simple tool for viewing entities.
    """

    def __init__(self):
        super(Viewer, self).__init__()
        self.SetLabel('AFEM')

    def display_item(self, item):
        """
        Display a type derived from ``ViewableItem``.

        :param afem.base.entities.ViewableItem item: The item.

        :return: The AIS_Shape created for the item.
        :rtype: OCC.Core.AIS.AIS_Shape
        """
        return self.display_shape(item.displayed_shape, item.color,
                                  item.transparency)

    def display_group(self, group, include_subgroup=True):
        """
        Display all parts of a group.

        :param afem.structure.group.Group group: The group.
        :param bool include_subgroup: Option to recursively include parts
            from any subgroups.

        :return: None.
        """
        for part in group.get_parts(include_subgroup):
            self.display_item(part)

    def add(self, *items):
        """
        Add items to be displayed.

        :param items: The items.
        :type items: afem.base.entities.ViewableItem or
            OCC.Core.TopoDS.TopoDS_Shape or
            afem.structure.group.Group or

        :return: None.
        """
        for item in items:
            if isinstance(item, ViewableItem):
                self.display_item(item)
            elif isinstance(item, Group):
                self.display_group(item)
            elif isinstance(item, TopoDS_Shape):
                self.display_shape(item)
