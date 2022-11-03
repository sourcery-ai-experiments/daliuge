#
#    ICRAR - International Centre for Radio Astronomy Research
#    (c) UWA - The University of Western Australia, 2017
#    Copyright by UWA (in the framework of the ICRAR)
#    All rights reserved
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston,
#    MA 02111-1307  USA
#
"""
This module defines the fields each drop takes for each reproducibility standard defined.
Consider this module partially documentation, partially code.
Data generated by instanced drops at runtime are defined with that drop's implementation.
"""

from enum import Enum

from dlg.common import Categories
from dlg.common.reproducibility.constants import ReproducibilityFlags


class FieldOps(Enum):
    """
    Defines the operations possible on drop data for provenance collection.
    """

    STORE = 0
    COUNT = 1
    REMOVE_FIRST = 2  # Removes the first char of an assumed string


def extract_fields(drop: dict, fields: dict):
    """
    Attempts to extract fields with the names in fields from the drop description.
    If not found, the key will not be present in the returned dictionary.
    """
    data = {}
    for key, operation in fields.items():
        if drop.get(key) is not None:
            if operation == FieldOps.STORE:
                data[key] = drop.get(key)
            elif operation == FieldOps.COUNT:
                data[key] = len(drop.get(key))
            elif operation == FieldOps.REMOVE_FIRST:
                data[key] = drop.get(key)[1:]
    return data


def lgt_block_fields(rmode: ReproducibilityFlags):
    """
    Collects dict of fields and operations for all drop types at the lgt layer for
    the supplied reproducibility standard.
    :param rmode: The reproducibility level in question
    :return: Dictionary of <str, FieldOp> pairs
    """
    if rmode == ReproducibilityFlags.NOTHING:
        return {}
    data = {
        "categoryType": FieldOps.STORE,
        "category": FieldOps.STORE,
        "inputPorts": FieldOps.COUNT,
        "outputPorts": FieldOps.COUNT,
        "inputLocalPorts": FieldOps.COUNT,
        "outputLocalPorts": FieldOps.COUNT,  # MKN Nodes
    }
    if rmode == ReproducibilityFlags.REPRODUCE:
        del data["inputPorts"]
        del data["outputPorts"]
        del data["inputLocalPorts"]
        del data["outputLocalPorts"]
    return data


def lg_block_fields(category_type: str, rmode: ReproducibilityFlags, custom_fields=None):
    """
    Collects dict of fields and operations for all drop types at the lg layer for
    the supplied reproducibility standard.
    :param category: The broad type of drop
    :param rmode: The reproducibility level in question
    :param custom_fields: Additional application args (used in custom components)
    :return: Dictionary of <str, FieldOp> pairs
    """
    data = {}
    if rmode in (
            ReproducibilityFlags.NOTHING,
            ReproducibilityFlags.RERUN,
            ReproducibilityFlags.REPRODUCE,
            ReproducibilityFlags.REPLICATE_SCI,
    ):
        return data
    # Drop category considerations - Just try to get everything we can, will be filtered later
    data["execution_time"] = FieldOps.STORE
    data["num_cpus"] = FieldOps.STORE
    data["inputApplicationName"] = FieldOps.STORE
    data["inputApplicationType"] = FieldOps.STORE
    data["data_volume"] = FieldOps.STORE

    # Drop type considerations
    if category_type == Categories.START:
        pass
    elif category_type == Categories.END:
        pass
    elif category_type == Categories.MEMORY:
        pass
    elif category_type == Categories.SHMEM:
        pass
    elif category_type == Categories.FILE:
        data["check_filepath_exists"] = FieldOps.STORE
        if rmode in (
                ReproducibilityFlags.RECOMPUTE,
                ReproducibilityFlags.REPLICATE_COMP,
        ):
            data["filepath"] = FieldOps.STORE
            data["dirname"] = FieldOps.STORE
    elif category_type == Categories.NULL:
        pass
    elif category_type == Categories.JSON:
        pass
    elif category_type == Categories.NGAS:
        pass
    elif category_type == Categories.S3:
        pass
    elif category_type == Categories.PLASMA:
        data["plasma_path"] = FieldOps.STORE
        data["object_id"] = FieldOps.STORE
    elif category_type == Categories.PLASMAFLIGHT:
        data["plasma_path"] = FieldOps.STORE
        data["object_id"] = FieldOps.STORE
        data["flight_path"] = FieldOps.STORE
    elif category_type == Categories.PARSET:
        pass
    elif category_type == Categories.ENVIRONMENTVARS:
        pass
    elif category_type == Categories.MKN:
        data["m"] = FieldOps.STORE
        data["k"] = FieldOps.STORE
        data["n"] = FieldOps.STORE
    elif category_type == Categories.SCATTER:
        data["num_of_copies"] = FieldOps.STORE
        data["scatter_axis"] = FieldOps.STORE
    elif category_type == Categories.GATHER:
        data["num_of_inputs"] = FieldOps.STORE
        data["gather_axis"] = FieldOps.STORE
    elif category_type == Categories.LOOP:
        data["num_of_iter"] = FieldOps.STORE
    elif category_type == Categories.GROUP_BY:
        data["group_key"] = FieldOps.STORE
        data["group_axis"] = FieldOps.STORE
    elif category_type == Categories.VARIABLES:
        pass
    elif category_type == Categories.BRANCH:
        data["appclass"] = FieldOps.STORE
    elif category_type == Categories.PYTHON_APP:
        data["appclass"] = FieldOps.STORE
    elif category_type == Categories.COMPONENT:
        data["appclass"] = FieldOps.STORE
    elif category_type == Categories.BASH_SHELL_APP:
        data["Arg01"] = FieldOps.STORE
    elif category_type == Categories.MPI:
        data["num_of_procs"] = FieldOps.STORE
    elif category_type == Categories.DOCKER:
        data["image"] = FieldOps.STORE
        data["command"] = FieldOps.STORE
        data["user"] = FieldOps.STORE
        data["ensureUserAndSwitch"] = FieldOps.STORE
        data["removeContainer"] = FieldOps.STORE
        data["additionalBindings"] = FieldOps.STORE
    elif category_type == Categories.DYNLIB_APP:
        data["libpath"] = FieldOps.STORE
    elif category_type == Categories.DYNLIB_PROC_APP:
        data["libpath"] = FieldOps.STORE
    if custom_fields is not None and rmode in (
            ReproducibilityFlags.RECOMPUTE, ReproducibilityFlags.REPLICATE_COMP):
        for name in custom_fields:
            data[name] = FieldOps.STORE
    return data


def pgt_unroll_block_fields(category_type, rmode: ReproducibilityFlags):
    """
    Collects dict of fields and operations for all drop types at the pgt unroll layer for
    the supplied reproducibility standard.
    :param category_type: The specific type of drop
    :param rmode: The reproducibility level in question
    :return: Dictionary of <str, FieldOp> pairs
    """
    data = {}
    if rmode == ReproducibilityFlags.NOTHING:
        return data
    if rmode != ReproducibilityFlags.NOTHING:
        data["type"] = FieldOps.STORE
    if rmode != ReproducibilityFlags.REPRODUCE:
        if category_type != "data":
            data["dt"] = FieldOps.STORE
    if category_type == "data":
        data["storage"] = FieldOps.STORE
    if rmode in (ReproducibilityFlags.RECOMPUTE, ReproducibilityFlags.REPLICATE_COMP):
        data["rank"] = FieldOps.STORE

    return data


def pgt_partition_block_fields(rmode: ReproducibilityFlags):
    """
    Collects dict of fields and operations for all drop types at the pgt partition layer for
    the supplied reproducibility standard.
    :param rmode: The reproducibility level in question
    :return: Dictionary of <str, FieldOp> pairs
    """
    data = {}
    if rmode in (ReproducibilityFlags.RECOMPUTE, ReproducibilityFlags.REPLICATE_COMP):
        data["node"] = FieldOps.REMOVE_FIRST
        data["island"] = FieldOps.REMOVE_FIRST
    return data


def pg_block_fields(rmode: ReproducibilityFlags):
    """
    Collects dict of fields and operations for all drop types at the pg layer for
    the supplied reproducibility standard.
    :param rmode: The reproducibility level in question
    :return: Dictionary of <str, FieldOp> pairs
    """
    # These two happen to have the same data.
    data = {}
    if rmode in (ReproducibilityFlags.RECOMPUTE, ReproducibilityFlags.REPLICATE_COMP):
        data["node"] = FieldOps.STORE
        data["island"] = FieldOps.STORE
    return data
