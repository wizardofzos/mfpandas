#!/usr/bin/env python3
"""Convert RACF ``SETROPTS LIST`` output to IRRXUTIL key/value lines.

The generated format is the one consumed by mfpandas/mfaudit:

    CLASSACT:DATASET
    INITSTAT:TRUE
    INTERVAL:030

Only settings represented by the IRRXUTIL SETROPTS extract are emitted.
Terminal prompts, Ctrl-Z characters, and repeated captures are ignored.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Optional


TRUE = "TRUE"
FALSE = "FALSE"


def _report(text: str) -> str:
    """Return the last SETROPTS LIST report from a terminal capture."""
    text = text.replace("\x1a", "\n")
    starts = list(
        re.finditer(
            r"(?im)^[ \t]*(?:1(?=SETROPTS))?SETROPTS[ \t]+LIST[ \t]*$",
            text,
        )
    )
    if not starts:
        raise ValueError("input does not contain a SETROPTS LIST report")

    # The last report is the most recent if a terminal capture contains several.
    report = text[starts[-1].end() :]
    end = re.search(r"(?im)^[ \t]*(?:READY|END)[ \t]*$", report)
    if end:
        report = report[: end.start()]
    return report


def _strip_asa_controls(report: str) -> str:
    """Remove ASA carriage-control columns from an SDSF/JES spool capture."""
    physical = report.splitlines()
    # A page eject can prefix a continuation line with "1" followed by its
    # original indentation, or a heading directly (for example
    # "1PASSWORD PROCESSING OPTIONS:"). This is distinctive inside SETROPTS
    # output and avoids modifying ordinary TSO captures.
    has_asa = any(
        re.match(r"^1(?:\s{2,}|PASSWORD PROCESSING OPTIONS:)", line, re.I)
        for line in physical
    )
    if not has_asa:
        return report

    return "\n".join(
        line[1:] if line and line[0] in " 01+-" else line for line in physical
    )


def _logical_lines(report: str) -> list[str]:
    """Join wrapped SETROPTS list values while retaining ordinary lines."""
    physical = report.splitlines()
    logical: list[str] = []
    i = 0
    wrapped_header = re.compile(
        r"^(?:"
        r"STATISTICS|AUDIT CLASSES|ACTIVE CLASSES|"
        r"GENERIC PROFILE CLASSES|GENERIC COMMAND CLASSES|"
        r"GENLIST CLASSES|GLOBAL CHECKING CLASSES|"
        r"SETR RACLIST CLASSES|GLOBAL=YES RACLIST ONLY|"
        r'LOGOPTIONS "(?:ALWAYS|NEVER|SUCCESSES|FAILURES|DEFAULT)" CLASSES'
        r")\s*=",
        re.IGNORECASE,
    )

    while i < len(physical):
        line = physical[i].rstrip()
        stripped = line.strip()
        if wrapped_header.match(stripped):
            value = stripped
            i += 1
            while i < len(physical):
                continuation = physical[i].rstrip()
                # Wrapped class names are indented and contain only tokens.
                if not re.match(r"^\s{2,}\S", continuation):
                    break
                candidate = continuation.strip()
                if not re.fullmatch(r"[A-Z0-9#$@*?+\- ]+", candidate, re.I):
                    break
                value += " " + candidate
                i += 1
            logical.append(value)
            continue
        if stripped:
            logical.append(stripped)
        i += 1
    return logical


def _class_values(lines: Iterable[str], label: str) -> list[str]:
    pattern = re.compile(rf"^{re.escape(label)}\s*=\s*(.*)$", re.I)
    for line in lines:
        match = pattern.match(line)
        if match:
            value = match.group(1).strip()
            return [] if value.upper() == "NONE" else value.upper().split()
    return []


def _bool_token(attributes: str, yes: str, no: str) -> Optional[str]:
    tokens = attributes.upper().split()
    if yes in tokens:
        return TRUE
    if no in tokens:
        return FALSE
    return None


def _has(report: str, pattern: str) -> bool:
    return re.search(pattern, report, re.I | re.M) is not None


def _match(report: str, pattern: str) -> Optional[re.Match[str]]:
    return re.search(pattern, report, re.I | re.M)


def convert(text: str) -> list[str]:
    """Convert one terminal capture and return ``KEY:VALUE`` output lines."""
    report = _strip_asa_controls(_report(text))
    lines = _logical_lines(report)
    # Terminal captures can prefix every output line with a blank. Wrapped
    # class lists need their original indentation above, but scalar matching
    # should not depend on terminal left margins.
    report = "\n".join(line.strip() for line in report.splitlines())
    output: list[str] = []

    def emit(key: str, value: Optional[object]) -> None:
        if value is not None:
            output.append(f"{key}:{value}")

    def emit_bool(key: str, positive: str, negative: str) -> None:
        if _has(report, positive):
            emit(key, TRUE)
        elif _has(report, negative):
            emit(key, FALSE)

    # Repeat fields are emitted in the same useful order as the sample
    # IRRXUTIL export. Empty/NONE repeat fields are absent from that export.
    repeat_fields = (
        ("CLASSACT", "ACTIVE CLASSES"),
        ("GENCMD", "GENERIC COMMAND CLASSES"),
        ("GENERIC", "GENERIC PROFILE CLASSES"),
        ("RACLIST", "SETR RACLIST CLASSES"),
        ("CLASSTAT", "STATISTICS"),
        ("AUDIT", "AUDIT CLASSES"),
        ("GENLIST", "GENLIST CLASSES"),
        ("GLOBAL", "GLOBAL CHECKING CLASSES"),
    )
    for key, label in repeat_fields:
        values = _class_values(lines, label)
        # mfpandas <= 1.6 determines whether a key is a repeat field from the
        # number of records instead of its field name. A valid one-item list
        # (for example GLOBAL:DATASET) is consequently treated as a scalar and
        # raises KeyError. Repeating the same value is semantically harmless:
        # mfpandas uses membership tests when it builds classInfo.
        if len(values) == 1:
            values *= 2
        for value in values:
            emit(key, value)

    attributes_match = _match(report, r"^\s*ATTRIBUTES\s*=\s*(.+)$")
    attributes = attributes_match.group(1) if attributes_match else ""
    emit("INITSTAT", _bool_token(attributes, "INITSTATS", "NOINITSTATS"))

    terminal = _match(attributes, r"\bTERMINAL\((READ|NONE)\)")
    # Current RACF output can omit the default from ATTRIBUTES, while the
    # extract still returns TERMINAL:READ
    emit("TERMINAL", terminal.group(1).upper() if terminal else "READ")

    emit("CMDVIOL", _bool_token(attributes, "CMDVIOL", "NOCMDVIOL"))
    emit("OPERAUDT", _bool_token(attributes, "OPERAUDIT", "NOOPERAUDIT"))
    emit("SAUDIT", _bool_token(attributes, "SAUDIT", "NOSAUDIT"))
    emit_bool(
        "APPLAUDT",
        r"^APPLAUDIT IS IN EFFECT\s*$",
        r"^APPLAUDIT IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "SLABAUDT",
        r"^SECLABEL AUDIT IS IN EFFECT\s*$",
        r"^SECLABEL AUDIT IS NOT IN EFFECT\s*$",
    )

    log_fields = (
        ("LOGALWYS", 'LOGOPTIONS "ALWAYS" CLASSES'),
        ("LOGNEVER", 'LOGOPTIONS "NEVER" CLASSES'),
        ("LOGSUCC", 'LOGOPTIONS "SUCCESSES" CLASSES'),
        ("LOGFAIL", 'LOGOPTIONS "FAILURES" CLASSES'),
        ("LOGDEFLT", 'LOGOPTIONS "DEFAULT" CLASSES'),
    )
    for key, label in log_fields:
        values = _class_values(lines, label)
        if len(values) == 1:
            values *= 2
        for value in values:
            emit(key, value)

    match = _match(report, r"^\s*(\d+)\s+GENERATIONS? OF PREVIOUS PASSWORDS")
    if match:
        emit("HISTORY", f"{int(match.group(1)):03d}")

    match = _match(report, r"PASSWORD CHANGE INTERVAL IS\s+(\d+)\s+DAYS")
    if match:
        emit("INTERVAL", f"{int(match.group(1)):03d}")

    match = _match(report, r"PASSWORD PHRASE CHANGE INTERVAL IS\s+(\d+)\s+DAYS")
    if match:
        emit("PHRINT", f"{int(match.group(1)):05d}")

    match = _match(report, r"PASSWORD MINIMUM CHANGE INTERVAL IS\s+(\d+)\s+DAYS")
    if match:
        emit("MINCHANG", f"{int(match.group(1)):03d}")

    emit_bool(
        "MIXDCASE",
        r"MIXED CASE PASSWORD SUPPORT IS IN EFFECT",
        r"MIXED CASE PASSWORD SUPPORT IS NOT IN EFFECT",
    )
    emit_bool(
        "PWDSPEC",
        r"SPECIAL CHARACTERS ARE ALLOWED",
        r"(?:SPECIAL CHARACTERS ARE NOT|NO SPECIAL CHARACTERS ARE) ALLOWED",
    )

    match = _match(report, r"ACTIVE PASSWORD ENCRYPTION ALGORITHM IS\s+(\S+)")
    if match:
        emit("PWDALG", match.group(1).upper().rstrip("."))

    for match in re.finditer(
        r"^\s*RULE\s+([1-8])\s+LENGTH\((\d+)(?::(\d+))?\)\s+(\S+)",
        report,
        re.I | re.M,
    ):
        number, minimum, maximum, sequence = match.groups()
        maximum = maximum or minimum
        emit(f"RULE{number}", f"{int(minimum)}:{int(maximum)} {sequence}")

    match = _match(
        report,
        r"AFTER\s+(\d+)\s+CONSECUTIVE UNSUCCESSFUL PASSWORD ATTEMPTS,"
        r"\s*A USERID WILL BE REVOKED",
    )
    if match:
        emit("REVOKE", f"{int(match.group(1)):03d}")

    match = _match(report, r"PASSWORD EXPIRATION WARNING LEVEL IS\s+(\d+)\s+DAYS")
    if match:
        emit("WARNING", f"{int(match.group(1)):03d}")

    emit_bool(
        "ADDCREAT",
        r"^ADDCREATOR IS IN EFFECT\s*$",
        r"^ADDCREATOR IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "ADSP",
        r"^AUTOMATIC DATASET PROTECTION IS IN EFFECT\s*$",
        r"^AUTOMATIC DATASET PROTECTION IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "COMPMODE",
        r"^COMPATIBILITY MODE IS IN EFFECT\s*$",
        r"^COMPATIBILITY MODE IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "EGN",
        r"^ENHANCED GENERIC NAMING IS IN EFFECT\s*$",
        r"^ENHANCED GENERIC NAMING IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "GENOWNER",
        r"^GENERIC OWNER ONLY IS IN EFFECT\s*$",
        r"^GENERIC OWNER ONLY IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "GRPLIST",
        r"^LIST OF GROUPS ACCESS CHECKING IS ACTIVE",
        r"^LIST OF GROUPS ACCESS CHECKING IS INACTIVE",
    )
    emit_bool(
        "MLQUIET",
        r"^MULTI-LEVEL QUIET IS IN EFFECT\s*$",
        r"^MULTI-LEVEL QUIET IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "MLSTABLE",
        r"^MULTI-LEVEL STABLE IS IN EFFECT\s*$",
        r"^MULTI-LEVEL STABLE IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "MLNAMES",
        r"^MULTI-LEVEL NAME HIDING IS IN EFFECT\s*$",
        r"^MULTI-LEVEL NAME HIDING IS NOT IN EFFECT\s*$",
    )
    emit_bool(
        "SLBYSYS",
        r"^SECURITY LABEL BY SYSTEM IS IN EFFECT\s*$",
        r"^SECURITY LABEL BY SYSTEM IS NOT IN EFFECT\s*$",
    )

    if _has(report, r"^MULTI-LEVEL INTERPROCESS COMMUNICATIONS IS NOT IN EFFECT"):
        emit("MLIPC", "INACTIVE")
    if _has(report, r"^MULTI-LEVEL FILE SYSTEM IS NOT IN EFFECT"):
        emit("MLFS", "INACTIVE")

    emit_bool(
        "REALDSN",
        r"^REAL DATA SET NAMES OPTION IS ACTIVE\s*$",
        r"^REAL DATA SET NAMES OPTION IS INACTIVE\s*$",
    )

    if _has(report, r"^PROTECT-ALL IS ACTIVE"):
        if _has(report, r"^\s*PROTECT-ALL WARNING OPTION IS IN EFFECT"):
            emit("PROTALL", "WARNING")
        else:
            # SETROPTS LIST calls the FAILURES mode "FAIL"; FAILURES is also
            # the RACF default when PROTECTALL is active without a suboption.
            emit("PROTALL", "FAILURES")

    match = _match(report, r"SECURITY RETENTION PERIOD IN EFFECT IS\s+(\d+)\s+DAYS")
    if match:
        emit("RETPD", f"{int(match.group(1)):05d}")

    for key, function in (("RVARSWPW", "SWITCH"), ("RVARSTPW", "STATUS")):
        if _has(
            report,
            rf"^DEFAULT RVARY PASSWORD IS IN EFFECT FOR THE {function} FUNCTION",
        ):
            emit(key, "DEFAULT")
        elif _has(
            report,
            rf"^INSTALLATION(?:[ -]DEFINED)? RVARY PASSWORD IS IN EFFECT "
            rf"FOR THE {function} FUNCTION",
        ):
            emit(key, "INSTLN")

    emit_bool(
        "SECLABCT",
        r"^SECLABEL CONTROL IS IN EFFECT\s*$",
        r"^SECLABEL CONTROL IS NOT IN EFFECT\s*$",
    )

    match = _match(
        report,
        r"PARTNER LU-VERIFICATION SESSIONKEY INTERVAL MAXIMUM/DEFAULT IS\s+"
        r"(\d+)\s+DAYS",
    )
    if match:
        emit("SESSINT", f"{int(match.group(1)):05d}")

    emit_bool(
        "TAPEDSN",
        r"^TAPE DATA SET PROTECTION IS ACTIVE\s*$",
        r"^TAPE DATA SET PROTECTION IS INACTIVE\s*$",
    )
    if re.search(r"\bNOWHEN\(PROGRAM", attributes, re.I):
        emit("WHENPROG", FALSE)
    elif re.search(r"\bWHEN\(PROGRAM(?:\s*--[^)]*)?\)", attributes, re.I):
        emit("WHENPROG", TRUE)

    no_model = _has(report, r"^NO DATA SET MODELLING BEING DONE")
    if no_model:
        emit("MODGDG", FALSE)
        emit("MODGROUP", FALSE)
        emit("MODUSER", FALSE)
        emit("MODEL", FALSE)
    else:
        emit_bool(
            "MODGDG",
            r"^DATA SET MODELLING IS BEING DONE FOR GDGS",
            r"^DATA SET MODELLING NOT BEING DONE FOR GDGS",
        )
        emit_bool(
            "MODGROUP",
            r"^GROUP DATA SET MODELLING IS BEING DONE",
            r"^GROUP DATA SET MODELLING IS NOT BEING DONE",
        )
        emit_bool(
            "MODUSER",
            r"^USER DATA SET MODELLING IS BEING DONE",
            r"^USER DATA SET MODELLING IS NOT BEING DONE",
        )

    emit_bool(
        "ERASE",
        r"^ERASE-ON-SCRATCH IS ACTIVE\s*$",
        r"^ERASE-ON-SCRATCH IS INACTIVE\s*$",
    )

    match = _match(report, r"^PRIMARY LANGUAGE DEFAULT\s*:\s*(\S+)")
    if match:
        emit("PRIMLANG", match.group(1).upper())
    match = _match(report, r"^SECONDARY LANGUAGE DEFAULT\s*:\s*(\S+)")
    if match:
        emit("SECLANG", match.group(1).upper())

    emit_bool(
        "JESBATCH",
        r"^JES-BATCHALLRACF OPTION IS ACTIVE\s*$",
        r"^JES-BATCHALLRACF OPTION IS INACTIVE\s*$",
    )
    emit_bool(
        "JESEARLY",
        r"^JES-EARLYVERIFY OPTION IS ACTIVE\s*$",
        r"^JES-EARLYVERIFY OPTION IS INACTIVE\s*$",
    )
    emit_bool(
        "JESXBM",
        r"^JES-XBMALLRACF OPTION IS ACTIVE\s*$",
        r"^JES-XBMALLRACF OPTION IS INACTIVE\s*$",
    )

    match = _match(report, r"^USER-ID FOR JES NJEUSERID IS\s*:\s*(\S+)")
    if match:
        emit("JESNJE", match.group(1))
    match = _match(report, r"^USER-ID FOR JES UNDEFINEDUSER IS\s*:\s*(\S+)")
    if match:
        emit("JESUNDEF", match.group(1))
    match = _match(report, r"^KERBLVL\s*=\s*(\d+)")
    if match:
        emit("KERBLVL", f"{int(match.group(1)):03d}")

    return output


def _read(path: Path, encoding: str) -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError as error:
        raise ValueError(
            f"cannot decode {path} as {encoding}; specify the transferred "
            "text file's encoding with --encoding"
        ) from error


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert RACF SETROPTS LIST text to mfpandas/mfaudit KEY:VALUE format"
        )
    )
    parser.add_argument("input", type=Path, help="SETROPTS LIST text file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output file (default: standard output)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="input/output text encoding (default: utf-8)",
    )
    args = parser.parse_args(argv)

    try:
        result = "\n".join(convert(_read(args.input, args.encoding))) + "\n"
        if args.output:
            with args.output.open("w", encoding=args.encoding, newline="\n") as stream:
                stream.write(result)
        else:
            sys.stdout.write(result)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
