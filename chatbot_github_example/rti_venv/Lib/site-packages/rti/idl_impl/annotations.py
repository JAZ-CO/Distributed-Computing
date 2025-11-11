# Copyright (c) 2005-2024 Real-Time Innovations, Inc.  All rights reserved.
# No duplications, whole or partial, manual or electronic, may be made
# without express written permission.  Any such copies, or revisions thereof,
# must display this notice unaltered.
# This code contains trade secrets of Real-Time Innovations, Inc.

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Union, Any, Optional
from functools import reduce
import rti.connextdds as dds

# --- Annotation classes ------------------------------------------------------


@dataclass
class KeyAnnotation:
    value: bool = False


AUTO_ID = 0x7FFFFFFF


@dataclass
class IdAnnotation:
    value: int = AUTO_ID


@dataclass
class ExtensibilityAnnotation:
    value: dds.ExtensibilityKind = dds.ExtensibilityKind.EXTENSIBLE


UNBOUNDED = 0x7FFFFFFF


@dataclass
class BoundAnnotation:
    value: int = UNBOUNDED


def get_total_size_from_dimensions(dimensions: Union[None, int, List[int]]) -> int:
    if dimensions is None:
        return 1
    elif isinstance(dimensions, list) or isinstance(dimensions, tuple):
        return reduce(lambda x, y: int(x) * int(y), dimensions)
    else:
        return int(dimensions)


@dataclass
class ArrayAnnotation:
    dimensions: Union[None, int, List[int]] = None

    @property
    def is_array(self) -> bool:
        return self.dimensions is not None

    @property
    def total_size(self) -> int:
        return get_total_size_from_dimensions(self.dimensions)

    @property
    def dimension_list(self) -> dds.Uint32Seq:
        if self.dimensions is None:
            return dds.Uint32Seq()
        elif isinstance(self.dimensions, list) or isinstance(self.dimensions, tuple):
            return dds.Uint32Seq([int(x) for x in self.dimensions])
        else:
            return dds.Uint32Seq([int(self.dimensions)])


class CharEncoding(IntEnum):
    UTF8 = 0
    UTF16 = 1


@dataclass
class CharEncodingAnnotation:
    value: CharEncoding = CharEncoding.UTF8


class AllowedDataRepresentationFlags(IntEnum):
    XCDR1 = 0x01
    XCDR2 = 0x04


@dataclass
class AllowedDataRepresentationAnnotation:
    value: AllowedDataRepresentationFlags = (
        AllowedDataRepresentationFlags.XCDR1 | AllowedDataRepresentationFlags.XCDR2
    )


@dataclass
class TypeNameAnnotation:
    value: Optional[str] = None


@dataclass
class ElementAnnotations:
    value: List[Any] = field(default_factory=list)

@dataclass
class DefaultAnnotation:
    value: Any = None

@dataclass
class MinAnnotation:
    value: Any = None

@dataclass
class MaxAnnotation:
    value: Any = None


def find_annotation(annotations, cls, default=None):
    if default is None:
        default = cls()

    if annotations is None:
        return default

    for annotation in annotations:
        if isinstance(annotation, cls):
            return annotation
    return default


def inherit_type_annotations(base_annotations: list, derived_annotations: list) -> list:
    """Combines the annotations of a base class and a derived class, throwing
    an exception if they are inconsistent
    """

    OVERRRIDABLE_ANNOTATIONS = [TypeNameAnnotation]

    result = derived_annotations.copy()
    for base_annotation in base_annotations:
        if type(base_annotation) in OVERRRIDABLE_ANNOTATIONS:
            # Overridable annotations are not inherited
            continue

        derived_annotation = find_annotation(
            derived_annotations, type(base_annotation), default=""
        )
        if derived_annotation != "":
            if derived_annotation != base_annotation:
                raise TypeError(
                    f"Inconsistent annotation in base class (base class: {base_annotation}, derived class: {derived_annotation})"
                )
        else:
            # The annotation is not present in the derived class, so we add it
            result.append(base_annotation)

    return result


def inherit_member_annotations(
    base_annotations: dict, derived_annotations: dict
) -> dict:
    """Combines the two dictionaries of member annotations"""

    return {**base_annotations, **derived_annotations}
