import wx
import wx.lib.scrolledpanel as scrolled

import datetime
from pathlib import Path
from functools import partial

from .model import EDFModel, InvalidFileError


class EditorFrame(wx.Frame):
    """The editor window.

    Controls the editing and anonymization of the EDF header fields
    and EDF annotations (if present).
    """

    _default_anonymized_fields = [
        "patientcode",
        "patientname",
        "patient_additional",
        "admincode",
        "technician",
    ]

    def __init__(self, parent, path: Path):
        super().__init__(parent, title=f"{path.name} — AnonymizEDF")
        icon_path = str(Path(__file__).parent.joinpath("resources", "frame_icon.ico"))
        self.SetIcon(wx.Icon(icon_path))
        self.parent = parent
        self.input_path = path
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self._read_edf()
        self._setup()
        self.Layout()
        self.Fit()
        self.header_panel.SetupScrolling()

    def _read_edf(self):
        try:
            self.model = EDFModel(self.input_path)
        except InvalidFileError:
            dialog = wx.MessageDialog(
                self,
                f"The selected file is not EDF(+) compliant.",
                "Could not open the EDF file",
                style=wx.ICON_ERROR | wx.OK,
            )
            dialog.ShowModal()
            self.Close()

    def _setup(self):
        panel = wx.Panel(self)

        self.header_panel = EditorHeaderPanel(
            panel, self.model, self._default_anonymized_fields
        )
        self.annots_panel = EditorAnnotationsPanel(panel, self.model)

        inner_box = wx.BoxSizer(wx.HORIZONTAL)
        inner_box.Add(self.header_panel, 1, wx.EXPAND, 0)
        inner_box.Add(self.annots_panel, 1, wx.EXPAND, 0)
        panel.SetSizerAndFit(inner_box)

        # Actions
        action_panel = wx.Panel(self)
        action_sizer = wx.BoxSizer()
        action_inner = wx.Panel(action_panel)
        inner_sizer = wx.BoxSizer()

        # reset_btn = wx.Button(action_panel, label="Reset all")
        cancel_btn = wx.Button(action_inner, label="Cancel")
        save_btn = wx.Button(action_inner, label="Save Anonymized")

        # reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)

        # action_sizer.Add(reset_btn, 0, wx.ALL, 5)
        inner_sizer.AddStretchSpacer()
        inner_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        inner_sizer.Add(save_btn, 0, wx.ALL, 5)
        action_inner.SetSizer(inner_sizer)

        action_sizer.Add(action_inner, 1, wx.EXPAND | wx.ALL, 10)
        action_panel.SetSizer(action_sizer)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(panel, 1, wx.EXPAND | wx.ALL, 0)
        box.Add(wx.StaticLine(self), 0, wx.EXPAND)
        box.Add(action_panel, 0, wx.EXPAND | wx.ALL, 0)

        self.SetSizer(box)

    def on_close(self, event):
        self.parent.on_child_closed()
        self.Destroy()

    def on_save(self, event):
        filename = self.open_file_save_dialog()

        if filename is None:
            return

        # Controller logic
        self.model.update_header(self.header_panel.get_field_values())
        self.model.update_annotations(self.annots_panel.get_annotation_values())
        self.model.write(filename)

    def open_file_save_dialog(self):
        default_filename = self.input_path.with_stem(
            self.input_path.stem + "_anonymized"
        ).name
        dialog = wx.FileDialog(
            self,
            defaultDir=str(self.input_path.parent.absolute()),
            defaultFile=default_filename,
            wildcard="EDF files (*.edf)|*.edf",
            style=wx.FD_SAVE,
        )

        if dialog.ShowModal() == wx.ID_OK:
            filename = dialog.GetPath()
        else:
            filename = None

        dialog.Destroy()
        return filename

    def on_cancel(self, event):
        self.on_close(event)

    def on_reset(self, event):
        raise NotImplementedError()


class EditorHeaderPanel(scrolled.ScrolledPanel):
    def __init__(self, parent, edf_model, anonymized_fields):
        super().__init__(parent)
        self.model = edf_model
        self.anonymized_fields = anonymized_fields
        self._setup()

    def _setup(self):
        sbox = wx.StaticBox(self, label="Header Information")
        sizer = wx.BoxSizer(wx.VERTICAL)

        inner_sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer = wx.FlexGridSizer(3, 0, 5)

        grid_sizer.Add((0, 0))
        grid_sizer.Add((0, 0))
        grid_sizer.Add(wx.StaticText(sbox, label="Anonymize?"), 0, wx.ALL, 0)

        grid_sizer.Add((0, 0))
        grid_sizer.Add((0, 0))
        grid_sizer.Add(wx.StaticLine(sbox), 0, wx.EXPAND | wx.BOTTOM, 10)

        self.field_elements = dict()
        for field in self.model.header_fields:
            should_anonymize = field["name"] in self.anonymized_fields

            # Label
            label_text = wx.StaticText(sbox, label=field["label"])
            grid_sizer.Add(
                label_text,
                1,
                wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            )

            # Editable field content
            match field["type"]:
                case "gender":
                    input_ctrl = GenderCtrl(sbox, value=field["value"])
                case "date":
                    if isinstance(field["value"], datetime.date):
                        date_val = wx.DateTime()
                        date_val.ParseISOCombined(field["value"].isoformat())
                    else:
                        date_val = wx.InvalidDateTime

                    input_ctrl = wx.adv.DatePickerCtrl(
                        sbox,
                        dt=date_val,
                        style=wx.adv.DP_DEFAULT | wx.adv.DP_ALLOWNONE,
                    )
                case "datetime":
                    if isinstance(field["value"], datetime.datetime):
                        date_val = wx.DateTime()
                        date_val.ParseISOCombined(field["value"].isoformat())
                    else:
                        date_val = wx.InvalidDateTime
                    input_ctrl = DateTimePickerPanel(sbox, date_val)
                case _:
                    input_ctrl = wx.TextCtrl(
                        sbox, value=field["value"], style=wx.TE_RICH
                    )

            grid_sizer.Add(input_ctrl, 1, wx.EXPAND | wx.BOTTOM, 5)

            # Checkbox “Anonymize”
            checkbox = wx.CheckBox(sbox, name=field["name"])
            checkbox.SetValue(should_anonymize)
            grid_sizer.Add(
                checkbox, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL
            )
            checkbox.Bind(wx.EVT_CHECKBOX, partial(self.update_field, field["name"]))

            self.field_elements[field["name"]] = {
                "label": label_text,
                "input": input_ctrl,
                "checkbox": checkbox,
                "type": field["type"],
            }

            self.update_field(field["name"])

        grid_sizer.AddGrowableCol(1)
        inner_sizer.AddSpacer(10)
        inner_sizer.Add(grid_sizer, 0, wx.ALL | wx.EXPAND, 10)
        sbox.SetSizerAndFit(inner_sizer)

        sizer.Add(sbox, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)
        self.Layout()

    def update_field(self, field_name, event=None):
        field = self.field_elements[field_name]
        should_anonymize = field["checkbox"].IsChecked()
        field["input"].Enable(not should_anonymize)

    def get_field_values(self):
        vals = dict()

        for field_name, field in self.field_elements.items():
            match field["type"]:
                case "date":
                    v_ = field["input"].GetValue()
                    field_val = datetime.date.fromisoformat(v_.FormatISODate())
                case "datetime":
                    v_ = field["input"].GetValue()
                    field_val = datetime.datetime.fromisoformat(v_.FormatISOCombined())
                case _:
                    field_val = field["input"].GetValue()

            vals[field_name] = {
                "value": field_val,
                "anonymize": field["checkbox"].IsChecked(),
            }

        return vals


class GenderCtrl(wx.Choice):
    GENDER_NA = "N/A"
    _choices = ["Male", "Female", GENDER_NA]

    def __init__(self, *args, value=None, **kwargs):
        super().__init__(*args, choices=self._choices, **kwargs)
        self.SetSelection(self.FindString(value))

    def GetValue(self):
        sel = self.GetStringSelection()
        if sel == self.GENDER_NA:
            return None
        return sel


class DateTimePickerPanel(wx.Panel):
    def __init__(self, parent, dt=wx.DefaultDateTime):
        super().__init__(parent)
        self.parent = parent

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.date_picker = wx.adv.DatePickerCtrl(
            self, dt=dt, style=wx.adv.DP_DEFAULT | wx.adv.DP_ALLOWNONE
        )
        self.time_picker = wx.adv.TimePickerCtrl(
            self, dt=dt, style=wx.adv.DP_DEFAULT | wx.adv.DP_ALLOWNONE
        )
        sizer.Add(self.date_picker, 1, wx.EXPAND | wx.RIGHT, 5)
        sizer.Add(self.time_picker, 1, wx.EXPAND | wx.LEFT, 5)
        self.SetSizer(sizer)

    def Enable(self, enable=True):
        self.date_picker.Enable(enable)
        return self.time_picker.Enable(enable)

    def GetValue(self):
        date_val = self.date_picker.GetValue()
        datetime_val = self.time_picker.GetValue()
        datetime_val.SetDay(date_val.GetDay())
        datetime_val.SetMonth(date_val.GetMonth())
        datetime_val.SetYear(date_val.GetYear())
        return datetime_val


class EditorAnnotationsPanel(scrolled.ScrolledPanel):
    def __init__(self, parent, model: EDFModel):
        super().__init__(parent)
        self.model = model
        self._setup()
        self.SetupScrolling()

    def _setup(self):
        self.annots_elements = []

        sbox = wx.StaticBox(self, label="Annotations")
        sizer = wx.BoxSizer(wx.VERTICAL)

        inner_sizer = wx.BoxSizer(wx.VERTICAL)
        inner_sizer.AddSpacer(10)

        if not self.model.annotations:
            placeholder = wx.StaticText(sbox, label="No annotations present.")
            inner_sizer.Add(placeholder, 1, wx.ALL, 10)
            sbox.SetSizerAndFit(inner_sizer)
            sizer.Add(sbox, 0, wx.EXPAND | wx.ALL, 10)
            self.SetSizer(sizer)
            self.Layout()
            return

        grid_sizer = wx.FlexGridSizer(3, 0, 0)

        grid_sizer.Add(wx.StaticText(sbox, label="Onset"), 0, wx.RIGHT, 5)
        grid_sizer.Add(
            wx.StaticText(sbox, label="Annotation"),
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            5,
        )
        grid_sizer.Add(wx.StaticText(sbox, label="Remove?"), 0, wx.LEFT | wx.RIGHT, 5)
        grid_sizer.Add(wx.StaticLine(sbox), 0, wx.EXPAND | wx.BOTTOM, 10)
        grid_sizer.Add(wx.StaticLine(sbox), 0, wx.EXPAND | wx.BOTTOM, 10)
        grid_sizer.Add(wx.StaticLine(sbox), 0, wx.EXPAND | wx.BOTTOM, 10)
        tc = wx.TextCtrl(sbox, value="Test")
        default_size = tc.GetSize()
        tc.Destroy()
        for n, (onset, _, annotation) in enumerate(self.model.annotations):
            onset_val = datetime.timedelta(seconds=onset)
            grid_sizer.Add(
                wx.StaticText(sbox, label=str(onset_val)),
                0,
                wx.ALIGN_RIGHT | wx.RIGHT,
                5,
            )
            input_text = wx.TextCtrl(
                sbox,
                value=annotation,
                style=wx.TE_MULTILINE,
                size=(-1, len(annotation.splitlines()) * default_size.height),
            )
            grid_sizer.Add(input_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

            checkbox = wx.CheckBox(sbox)
            grid_sizer.Add(
                checkbox, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL
            )
            grid_sizer.Add(wx.StaticLine(sbox), 1, wx.EXPAND | wx.BOTTOM, 10)
            grid_sizer.Add(wx.StaticLine(sbox), 1, wx.EXPAND | wx.BOTTOM, 10)
            grid_sizer.Add(wx.StaticLine(sbox), 1, wx.EXPAND | wx.BOTTOM, 10)

            self.annots_elements.append(
                {
                    "input": input_text,
                    "checkbox": checkbox,
                }
            )

        grid_sizer.AddGrowableCol(1)

        inner_sizer.Add(grid_sizer, 1, wx.ALL | wx.EXPAND, 10)
        sbox.SetSizerAndFit(inner_sizer)

        sizer.Add(sbox, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)
        self.Layout()

    def get_annotation_values(self):
        output_annots = []
        for el, original_annot in zip(self.annots_elements, self.model.annotations):
            if el["checkbox"].IsChecked():
                continue
            onset, duration, _ = original_annot
            content = el["input"].GetValue()
            output_annots.append((onset, duration, content))
        return output_annots
