"""Static analysis engine for OSS detection in C/C++ source trees."""

from .copyright import CopyrightInfo, extract_copyright_info
from .scanner import FileInfo, ScanResult, scan_tree
from .classifier import Classification, ClassifiedFile, ClassificationResult, classify
from .models import Component, FunctionSummary
from .grouper import group_into_components

__all__ = [
    "CopyrightInfo",
    "extract_copyright_info",
    "FileInfo",
    "ScanResult",
    "scan_tree",
    "Classification",
    "ClassifiedFile",
    "ClassificationResult",
    "classify",
    "Component",
    "FunctionSummary",
    "group_into_components",
]
