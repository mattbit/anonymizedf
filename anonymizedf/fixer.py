import re
import shutil
import chardet
import dateparser
from copy import copy
from pathlib import Path
from pyedflib import EdfReader
from unidecode import unidecode


def guess_patient_fields(fields):
    """Heuristic guess of the local patient information field."""
    field_type_guesses = []
    for n, field in enumerate(fields):
        if field.lower() in ["m", "f"]:
            field_type_guesses.append(
                {
                    "type": "sex",
                    "value": field.upper(),
                    "confidence": 0.5,
                    "field": n,
                }
            )
        date = dateparser.parse(field)
        if date is not None:
            conf_ = 0.5
            if re.match(r"^\d{2}-[^\d\W]+-\d{4}$", field):
                conf_ = 0.8
            field_type_guesses.append(
                {"type": "birthdate", "value": date, "confidence": conf_, "field": n}
            )
    return field_type_guesses


def guess_recording_fields(fields):
    """Heuristic guess of the local recording information field."""
    field_type_guesses = []
    for n, field in enumerate(fields):
        date = dateparser.parse(field)
        if date is not None:
            conf_ = 0.5
            if re.match(r"^\d{2}-[^\d\W]+-\d{4}$", field):
                conf_ = 0.8
            field_type_guesses.append(
                {"type": "startdate", "value": date, "confidence": conf_, "field": n}
            )
    return field_type_guesses


def process_field_guesses(fields, guesses):
    """Processes the heuristic guesses and tries to produce the best compliant field string."""
    fields = copy(fields)  # work on copy
    compliant_fields = dict()

    field_type_guesses = sorted(guesses, key=lambda x: x["confidence"])

    while field_type_guesses:
        g = field_type_guesses.pop()

        cfield = compliant_fields.get(g["type"])
        if cfield is None:
            compliant_fields[g["type"]] = g
        elif cfield["confidence"] == g["confidence"] and cfield["value"] != g["value"]:
            # Conflicting guesses, remove
            del compliant_fields[g["type"]]

    for n in sorted((cf["field"] for _, cf in compliant_fields.items()), reverse=True):
        del fields[n]

    return dict((k, v["value"]) for k, v in compliant_fields.items()), fields


class FieldFormatError(ValueError):
    """Error in the EDF+ field format"""


MONTHS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]


def format_edf_long_date(date):
    return f"{date.day:02}-{MONTHS[date.month - 1]}-{date.year:04}"


def basic_fix_lpi_format(lpi):
    """Field by field reformatting of local patient information."""
    fields = re.split(r" +", lpi)

    if len(fields) < 4:
        fields.extend(["X"] * (4 - len(fields)))

    if fields[1].lower() not in ["m", "f", "x"]:
        raise FieldFormatError("Invalid sex field")

    if fields[2].lower() != "x":
        birthdate = dateparser.parse(fields[2])
        if birthdate is None:
            raise FieldFormatError("Invalid birthdate field")
        fields[2] = format_edf_long_date(birthdate)

    return unidecode(" ".join(fields))


def heuristic_fix_lpi_format(lpi):
    """Reconstruction of local patient information based on heuristic guess."""
    fields = re.split(r" +", lpi)
    guesses = guess_patient_fields(fields)
    best_guesses, extra_fields = process_field_guesses(fields, guesses)
    print(best_guesses)
    # Merge
    compliant_fields = [
        best_guesses.get("code", "X"),
        best_guesses.get("sex", "X"),
        format_edf_long_date(best_guesses["birthdate"])
        if "birthdate" in best_guesses
        else "X",
        best_guesses.get("name", "X"),
    ]
    compliant_fields.extend(extra_fields)

    return unidecode(" ".join(compliant_fields))


def basic_fix_lri_format(lri):
    """Field by field reformatting of local patient information."""
    fields = re.split(r" +", lri)

    if len(fields) < 5:
        fields.extend(["X"] * (5 - len(fields)))

    if fields[0].lower() != "startdate":
        raise FieldFormatError("Missing Startdate")

    fields[0] = "Startdate"

    if fields[1].lower() != "x":
        startdate = dateparser.parse(fields[1])
        if startdate is None:
            raise FieldFormatError("Invalid startdate field")
        fields[1] = format_edf_long_date(startdate)

    return unidecode(" ".join(fields))


def heuristic_fix_lri_format(lri):
    """Reconstruction of local recording information based on heuristic guess."""
    fields = re.split(r" +", lri)
    guesses = guess_recording_fields(fields)
    best_guesses, extra_fields = process_field_guesses(fields, guesses)

    # Merge
    compliant_fields = [
        "Startdate",
        format_edf_long_date(best_guesses["startdate"])
        if "startdate" in best_guesses
        else "X",
        best_guesses.get("code", "X"),
        best_guesses.get("technician", "X"),
        best_guesses.get("equipment", "X"),
    ]
    compliant_fields.extend(extra_fields)

    return unidecode(" ".join(compliant_fields))


def fix_edfplus_header(header):
    # Detect the character set. EDF header must be ASCII encoded but this
    # specification is not respected by some implementations.
    detection = chardet.detect(header)
    dec_header = header.decode(detection["encoding"])

    # Read and try to fix local patient/recording information
    lpi = dec_header[8 : 8 + 80].strip()
    lri = dec_header[88 : 88 + 80].strip()

    try:
        compliant_lpi = basic_fix_lpi_format(lpi)
    except FieldFormatError:
        compliant_lpi = heuristic_fix_lpi_format(lpi)

    try:
        compliant_lri = basic_fix_lri_format(lri)
    except FieldFormatError:
        compliant_lri = heuristic_fix_lri_format(lri)

    corr_header = (
        "0".ljust(8)
        + compliant_lpi[:80].ljust(80)
        + compliant_lri[:80].ljust(80)
        + dec_header[168 : 168 + 24]
        + "EDF+C".ljust(44)
        + dec_header[236:]
    )

    return corr_header.encode("ascii")


def _get_copy_path_with_suffix(path: Path, suffix: str):
    dst_path = path.with_name(path.stem + f"_{suffix}.edf")
    n = 2
    while dst_path.exists():
        dst_path = dst_path.with_name(path.stem + f"_{suffix}_{n}.edf")
        n += 1
    return dst_path


def fix_edf_file(file_path, output_path=None, check_valid=True):
    """Tries to fix an invalid EDF+ file."""
    file_path = Path(file_path)

    if output_path is None:
        output_path = _get_copy_path_with_suffix(file_path, "fixed")

    with file_path.open("rb") as f:
        header = f.read(256)

    # Fix the header
    fixed_header = fix_edfplus_header(header)

    # Write fixed file
    shutil.copy(file_path, output_path)
    with output_path.open("r+b") as f:
        f.write(fixed_header)

    # Verify we can open the fixed file without errors
    if check_valid:
        try:
            with EdfReader(str(output_path)) as f:
                f.getHeader()
        except OSError:
            output_path.unlink()
            raise RuntimeError("Could not fix the EDF file")

    return output_path
