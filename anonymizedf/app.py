import wx
import wx.adv
import wx.grid
import wx.dataview

from pathlib import Path
from .editor import EditorFrame

APP_VERSION = "v0.0.1β"


class App(wx.App):
    def __init__(self, filenames=None):
        super().__init__(False)

        self.app_frame = AppFrame(None, "AnonymizEDF", filenames)


class AppFrame(wx.Frame):
    def __init__(self, parent, title, filenames=None):
        super().__init__(parent, title=title)
        icon_path = str(Path(__file__).parent.joinpath("resources", "frame_icon.ico"))
        self.SetIcon(wx.Icon(icon_path))
        self.CreateStatusBar()

        self._configure_menu()
        self._configure_drop_target()

        if filenames:
            for fn in filenames:
                self.open_editor(fn)
        else:
            self.Centre()
            self.Show()

    def _configure_menu(self):
        menu = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()

        about_item = file_menu.Append(
            wx.ID_ABOUT, "&About", "Information about this program"
        )
        self.Bind(wx.EVT_MENU, self.on_menu_about, about_item)
        quit_item = file_menu.Append(wx.ID_EXIT, "&Quit", "Terminate the program")
        self.Bind(wx.EVT_MENU, self.on_menu_quit, quit_item)
        open_item = file_menu.Append(wx.ID_OPEN, "&Open…", "Open an EDF file")
        self.Bind(wx.EVT_MENU, self.on_file_open, open_item)

        menu.Append(file_menu, "&File")

        self.SetMenuBar(menu)

    def _configure_drop_target(self):
        drop_panel = wx.Panel(self, style=wx.BORDER_THEME)

        label = wx.StaticText(drop_panel, wx.ID_ANY, label="Drop an EDF file here")
        open_btn = wx.Button(drop_panel, wx.ID_ANY, label="Open…")
        open_btn.Bind(wx.EVT_BUTTON, self.on_file_open)
        sizer_h = wx.BoxSizer(wx.HORIZONTAL)
        sizer_v = wx.BoxSizer(wx.VERTICAL)
        sizer_v.Add(label, 1, wx.CENTER)
        sizer_v.Add(open_btn, 1, wx.CENTER)
        sizer_h.Add(sizer_v, 1, wx.CENTER)
        drop_panel.SetSizer(sizer_h)

        target = FileDropTarget(self.on_files_drop)
        drop_panel.SetDropTarget(target)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(drop_panel, 1, wx.EXPAND | wx.ALL, border=20)

        self.SetSizer(box)
        self.Layout()

    def on_menu_about(self, event):
        dialog = wx.MessageDialog(
            self,
            f"An Anonymizer for EDF files\n(Version {APP_VERSION})",
            "AnonymizEDF",
            wx.CLOSE,
        )
        dialog.ShowModal()
        dialog.Destroy()

    def on_menu_quit(self, event):
        self.Close(True)

    def on_files_drop(self, filenames):
        for filename in filenames:
            self.open_editor(filename)

    def on_file_open(self, event):
        dialog = wx.FileDialog(
            self, wildcard="EDF files (*.edf)|*.edf", style=wx.FD_OPEN
        )
        if dialog.ShowModal() == wx.ID_OK:
            filename = dialog.GetPath()
            self.open_editor(filename)

        dialog.Destroy()

    def open_editor(self, filename):
        editor = EditorFrame(self, Path(filename))
        editor.Show()
        self.Hide()

    def on_child_closed(self):
        children = [c for c in self.GetChildren() if isinstance(c, wx.Frame)]
        if len(children) <= 1:
            self.Show()


class FileDropTarget(wx.FileDropTarget):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def OnDropFiles(self, x, y, filenames):
        self.callback(filenames)
        return True
