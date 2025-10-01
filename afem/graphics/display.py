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
from OCC.Display.SimpleGui import check_callable
from typing import Callable, Optional, Tuple, List
import wx

from afem.base.entities import ViewableItem
from afem.structure.group import Group


__all__ = ["Viewer"]

# Icon location
_icon = os.path.dirname(__file__) + '/resources/main.png'


class AppFrame(wx.Frame):
    def __init__(self, parent, size):
        wx.Frame.__init__(
            self,
            parent,
            -1,
            f"AFEM",
            style=wx.DEFAULT_FRAME_STYLE,
            size=size,
        )
        self.canva = wxViewer3d(self)
        self.menuBar = wx.MenuBar()
        self._menus = {}
        self._menu_methods = {}

    def add_menu(self, menu_name: str) -> None:
        _menu = wx.Menu()
        self.menuBar.Append(_menu, f"&{menu_name}")
        self.SetMenuBar(self.menuBar)
        self._menus[menu_name] = _menu

    def add_function_to_menu(self, menu_name: str, _callable: Callable) -> None:
        # point on curve
        _id = wx.NewId()
        check_callable(_callable)
        if menu_name not in self._menus:
            raise ValueError(f"the menu item {menu_name} does not exist")
        self._menus[menu_name].Append(
            _id, _callable.__name__.replace("_", " ").lower()
        )
        self.Bind(wx.EVT_MENU, _callable, id=_id)


# app = wx.App(False)
# win = AppFrame(None)
# win.Show(True)
# wx.SafeYield()
# win.canva.InitDriver()
# app.SetTopWindow(win)
# display = win.canva._display


class Viewer:
    """
    Simple tool for viewing entities.
    """

    def __init__(
            self,
            size: Optional[Tuple[int, int]] = (1024, 768),
            display_triedron: Optional[bool] = True,
            background_gradient_color1: Optional[List[int]] = [206, 215, 222],
            background_gradient_color2: Optional[List[int]] = [128, 128, 128],
            label: Optional[str] = 'AFEM',
            show: Optional[bool] = False,
    ):
        app = wx.App(False)
        self._app = app
        self.win = AppFrame(None, size)
        self.win.Show(show)
        wx.SafeYield()
        self.win.canva.InitDriver()
        self._app.SetTopWindow(self.win)
        self.display = self.win.canva._display
        self.win.SetLabel(label)
        self.add_key(ord('C'), self.hide)
        if display_triedron:
            self.display.display_triedron()

        if background_gradient_color1 and background_gradient_color2:
            # background gradient
            self.display.set_bg_gradient_color(
                background_gradient_color1, background_gradient_color2
            )

    def start(self):
        self.win.Show()
        self._app.MainLoop()

    def hide(self):
        self.win.Hide()
        self._app.ExitMainLoop()

    def add_menu(self, *args, **kwargs) -> None:
        self.win.add_menu(*args, **kwargs)

    def add_function_to_menu(self, *args, **kwargs) -> None:
        self.win.add_function_to_menu(*args, **kwargs)

    def add_key(self, key: int, fcn: Callable):
        self.win.canva._key_map[key] = fcn

    def display_item(self, item, material=None, texture=None, update=False):
        """
        Display a type derived from ``ViewableItem``.

        :param afem.base.entities.ViewableItem item: The item.

        :return: The AIS_Shape created for the item.
        :rtype: OCC.Core.AIS.AIS_Shape
        """
        return self.display.DisplayShape(
            item.displayed_shape,
            material=material,
            texture=texture,
            color=item.color,
            transparency=item.transparency,
            update=update,
        )

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
                self.display.DisplayShape(item)
