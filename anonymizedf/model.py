import pyedflib
import datetime
from copy import deepcopy
from pyedflib import EdfReader
from pyedflib.highlevel import write_edf


class EDFModel:
    """ "The EDF recording model.

    Provides an interface to deal with header and annotation information
    present in a given EDF file.
    """

    _header_fields = [
        # label, field_name, field_type
        ("Patient code", "patientcode", "text"),
        ("Patient name", "patientname", "text"),
        ("Patient info", "patient_additional", "text"),
        ("Birthdate", "birthdate", "date"),
        ("Gender", "gender", "gender"),
        ("Admin code", "admincode", "text"),
        ("Recording date", "startdate", "datetime"),
        ("Technician", "technician", "text"),
        ("Equipment", "equipment", "text"),
        ("Recording info", "recording_additional", "text"),
    ]

    def __init__(self, path):
        try:
            with EdfReader(str(path)) as f:
                self._header = f.getHeader()
                self._annots = [annot for annot in zip(*f.readAnnotations())]
                self._signal_headers = f.getSignalHeaders()
                self._signals = [
                    f.readSignal(s, digital=True) for s in range(f.signals_in_file)
                ]
                edf_file_type = f.filetype

                if edf_file_type == pyedflib.FILETYPE_EDF:
                    # This is a legacy EDF file, so we copy the legacy header
                    # fields into the EDF+ “extra” fields.
                    self._header["patient_additional"] = f.patient
                    self._header["recording_additional"] = f.recording
        except OSError as err:
            raise InvalidFileError(str(err))

    @property
    def header_fields(self):
        for f_label, f_name, f_type in self._header_fields:
            yield {
                "label": f_label,
                "name": f_name,
                "type": f_type,
                "value": self.get_header_field_value(f_name),
            }

    def get_header_field_value(self, field_name):
        # Need to fix the birthdate field since pyEDFlib reads it
        # as text in EdfReader, but takes it as date in EdfWriter.
        if field_name == "birthdate":
            return self._parse_birthdate()

        return self._header.get(field_name)

    def _parse_birthdate(self):
        birthdate_str = self._header.get("birthdate")
        if birthdate_str == "":
            return None
        return datetime.datetime.strptime(birthdate_str, "%d %b %Y")

    @property
    def annotations(self):
        return self._annots

    def update_header(self, fields):
        for field_name, field in fields.items():
            if field["anonymize"]:
                self._header[field_name] = ""
            else:
                self._header[field_name] = (
                    field["value"] if field["value"] is not None else ""
                )
        if self._header["startdate"] == "":
            # Since we cannot completely remove the recording date and time,
            # we set it to an arbitrary value in the far future.
            self._header["startdate"] = datetime.datetime(3000, 1, 1, 0, 0, 0, 0)

    def update_annotations(self, annotations):
        self._annots = deepcopy(annotations)

    def write(self, filename):
        header = deepcopy(self._header)
        header["annotations"] = self.annotations

        write_edf(filename, self._signals, self._signal_headers, header, digital=True)


class InvalidFileError(IOError):
    """The EDF file is invalid or malformed."""
