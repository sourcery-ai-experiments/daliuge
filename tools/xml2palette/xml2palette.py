#!/usr/bin/python

import csv
import getopt
import json
import logging
import random
import os
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

next_key = -1

# NOTE: not sure if all of these are actually required
#       make sure to retrieve some of these from environment variables
DOXYGEN_SETTINGS = [
    ("OPTIMIZE_OUTPUT_JAVA", "YES"),
    ("AUTOLINK_SUPPORT", "NO"),
    ("IDL_PROPERTY_SUPPORT", "NO"),
    ("RECURSIVE", "YES"),
    ("EXCLUDE_PATTERNS", "*/web/*"),
    ("VERBATIM_HEADERS", "NO"),
    ("GENERATE_HTML", "NO"),
    ("GENERATE_LATEX", "NO"),
    ("GENERATE_XML", "YES"),
    ("XML_PROGRAMLISTING", "NO"),
    ("ENABLE_PREPROCESSING", "NO"),
    ("CLASS_DIAGRAMS", "NO"),
]

KNOWN_PARAM_DATA_TYPES = ["String", "Integer", "Float", "Complex", "Boolean", "Select", "Password", "Json"]

def get_options_from_command_line(argv):
    inputdir = ""
    tag = ""
    outputfile = ""
    try:
        opts, args = getopt.getopt(argv, "hi:t:o:", ["idir=", "tag=", "ofile="])
    except getopt.GetoptError:
        print("xml2palette.py -i <input_directory> -t <tag> -o <output_file>")
        sys.exit(2)

    if len(opts) < 2:
        print("xml2palette.py -i <input_directory> -t <tag> -o <output_file>")
        sys.exit()

    for opt, arg in opts:
        if opt == "-h":
            print("xml2palette.py -i <input_directory> -t <tag> -o <output_file>")
            sys.exit()
        elif opt in ("-i", "--idir"):
            inputdir = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    return inputdir, tag, outputfile


def check_environment_variables():
    required_environment_variables = ["PROJECT_NAME", "PROJECT_VERSION", "GIT_REPO"]

    for variable in required_environment_variables:
        value = os.environ.get(variable)

        if value is None:
            logging.error("No " + variable + " environment variable.")
            return False

    return True


def modify_doxygen_options(doxygen_filename, options):
    with open(doxygen_filename, "r") as dfile:
        contents = dfile.readlines()

    # print(contents)

    with open(doxygen_filename, "w") as dfile:
        for index, line in enumerate(contents):
            if line[0] == "#":
                continue
            if len(line) <= 1:
                continue

            parts = line.split("=")
            first_part = parts[0].strip()
            written = False

            for key, value in options:
                if first_part == key:
                    dfile.write(key + " = " + value + "\n")
                    written = True
                    break

            if not written:
                dfile.write(line)


def get_next_key():
    global next_key

    next_key -= 1

    return next_key + 1


def create_uuid(seed):
    rnd = random.Random()
    rnd.seed(seed)

    new_uuid = uuid.UUID(int=rnd.getrandbits(128), version=4)
    return new_uuid


def create_port(
    component_name, internal_name, external_name, direction, event, type, description
):
    seed = {
        "component_name": component_name,
        "internal_name": internal_name,
        "external_name": external_name,
        "direction": direction,
        "event": event,
        "type": type,
        "description": description,
    }

    port_uuid = create_uuid(str(seed))

    return {
        "Id": str(port_uuid),
        "IdText": internal_name,
        "text": external_name,
        "event": event,
        "type": type,
        "description": description,
    }


def find_field_by_name(fields, name):
    for field in fields:
        if field["name"] == name:
            return field
    return None


def add_required_fields_for_category(text, fields, category):
    if category in ["DynlibApp", "PythonApp", "Branch", "BashShellApp", "Mpi", "Docker"]:
        add_field_if_missing(
            text,
            fields,
            "execution_time",
            "Execution time",
            5,
            "Estimated execution time",
            "readwrite",
            "Float",
            False,
        )
        add_field_if_missing(
            text,
            fields,
            "num_cpus",
            "Num CPUs",
            1,
            "Number of cores used",
            "readwrite",
            "Integer",
            False,
        )

    if category in ["DynlibApp", "PythonApp", "Branch", "BashShellApp", "Docker"]:
        add_field_if_missing(
            text,
            fields,
            "group_start",
            "Group start",
            "false",
            "Component is start of a group",
            "readwrite",
            "Boolean",
            False,
        )

    if category == "DynlibApp":
        add_field_if_missing(text, fields, "libpath", "Library path", "", "", "readwrite", "String", False)

    if category in ["PythonApp", "Branch"]:
        add_field_if_missing(
            text,
            fields,
            "appclass",
            "Appclass",
            "dlg.apps.simple.SleepApp",
            "Application class",
            "readwrite",
            "String",
            False,
        )

    if category in ["File", "Memory", "NGAS", "ParameterSet", "Plasma", "PlasmaFlight", "S3"]:
        add_field_if_missing(
            text,
            fields,
            "data_volume",
            "Data volume",
            5,
            "Estimated size of the data contained in this node",
            "readwrite",
            "Integer",
            False,
        )

    if category in ["File", "Memory", "NGAS", "ParameterSet", "Plasma", "PlasmaFlight", "S3", "Mpi"]:
        add_field_if_missing(
            text,
            fields,
            "group_end",
            "Group end",
            "false",
            "Component is end of a group",
            "readwrite",
            "Boolean",
            False,
        )

    if category in ["BashShellApp", "Mpi", "Docker", "Singularity"]:
        add_field_if_missing(
            text,
            fields,
            "input_redirection",
            "Input redirection",
            "",
            "The command line argument that specifies the input into this application",
            "readwrite",
            "String",
            False,
        )
        add_field_if_missing(
            text,
            fields,
            "output_redirection",
            "Output redirection",
            "",
            "The command line argument that specifies the output from this application",
            "readwrite",
            "String",
            False,
        )
        add_field_if_missing(
            text,
            fields,
            "command_line_arguments",
            "Command line arguments",
            "",
            "Additional command line arguments to be added to the command line to be executed",
            "readwrite",
            "String",
            False,
        )
        add_field_if_missing(
            text,
            fields,
            "paramValueSeparator",
            "Param Value Separator",
            " ",
            "Separator character(s) between parameters on the command line",
            "readwrite",
            "String",
            False,
        )
        add_field_if_missing(
            text,
            fields,
            "argumentPrefix",
            "Argument prefix",
            "--",
            "Prefix to each keyed argument on the command line",
            "readwrite",
            "String",
            False,
        )


def create_field(internal_name, name, value, description, access, type, precious):
    return {
        "text": name,
        "name": internal_name,
        "value": value,
        "default": value,
        "description": description,
        "readonly": access == "readonly",
        "type": type,
        "precious": precious,
    }


def add_field_if_missing(text, fields, internal_name, name, value, description, access, type, precious):
    if find_field_by_name(fields, internal_name) is None:
        logging.warning(
            text + " component added missing " + internal_name + " cparam"
        )
        fields.append(
            create_field(internal_name, name, value, description, access, type, precious)
        )


def parse_key(key):
    # parse the key as csv (delimited by '/')
    parts = []
    reader = csv.reader([key], delimiter="/", quotechar='"')
    for row in reader:
        parts = row

    # init attributes of the param/port
    object = ""
    internal_name = ""

    # assign attributes (if present)
    if len(parts) > 0:
        object = parts[0]
    if len(parts) > 1:
        internal_name = parts[1]

    return (object, internal_name)


def parse_param_value(text, prefix, value):
    # parse the value as csv (delimited by '/')
    parts = []
    reader = csv.reader([value], delimiter="/", quotechar='"')
    for row in reader:
        parts = row

    # init attributes of the param
    external_name = ""
    default_value = ""
    type = "String"
    access = "readwrite"
    precious = False

    # assign attributes (if present)
    if len(parts) > 0:
        external_name = parts[0]
    if len(parts) > 1:
        default_value = parts[1]
    if len(parts) > 2:
        type = parts[2]
    if (
        len(parts) > 4
    ):  # NOTE: correct that we start looking for >4, but access element 3
        access = parts[3]
    else:
        logging.warning(
            text + " " +
            prefix
            + "param ("
            + external_name
            + ") has no 'access' descriptor, using default (readwrite) : "
            + value
        )
    if len(parts) > 5:
        precious = parts[4].lower() == "true"
    else:
        logging.warning(
            text + " " +
            prefix
            + "param ("
            + external_name
            + ") has no 'precious' descriptor, using default (False) : "
            + value
        )

    return (external_name, default_value, type, access, precious)


def parse_port_value(value):
    # parse the value as csv (delimited by '/')
    parts = []
    reader = csv.reader([value], delimiter="/", quotechar='"')
    for row in reader:
        parts = row

    # init attributes of the param
    name = ""
    type = "String"

    # assign attributes (if present)
    if len(parts) > 0:
        name = parts[0]
    if len(parts) > 1:
        type = parts[1]
    else:
        logging.warning(
            "port ("
            + name
            + ") has no 'type' descriptor, using default (String) : "
            + value
            + " "
            + str(len(parts))
            + " "
            + str(parts)
        )

    return (name, type)


def parse_description(value):
    # parse the value as csv (delimited by '/')
    parts = []
    reader = csv.reader([value], delimiter="/", quotechar='"')
    for row in reader:
        parts = row

    # if parts is empty
    if len(parts) == 0:
        logging.warning("unable to parse description from: " + value)
        return ""

    return parts[-1]


# NOTE: color, x, y, width, height are not specified in palette node, they will be set by the EAGLE importer
def create_palette_node_from_params(params):
    text = ""
    description = ""
    category = ""
    tag = ""
    categoryType = ""
    inputPorts = []
    outputPorts = []
    inputLocalPorts = []
    outputLocalPorts = []
    fields = []
    applicationArgs = []
    gitrepo = os.environ.get("GIT_REPO")
    version = os.environ.get("PROJECT_VERSION")

    # process the params
    for param in params:
        key = param["key"]
        direction = param["direction"]
        value = param["value"]

        if key == "category":
            category = value
        elif key == "tag":
            tag = value
        elif key == "text":
            text = value
        elif key == "description":
            description = value
        elif key.startswith("cparam/"):
            # parse the param key into name, type etc
            (param, internal_name) = parse_key(key)
            (name, default_value, type, access, precious) = parse_param_value(text, "c", value)

            # check that type is in the list of known types
            if type not in KNOWN_PARAM_DATA_TYPES:
                logging.warning(
                    text + " cparam '" + name + "' has unknown type: " + type
                )

            # parse description
            if "\n" in value:
                logging.info(
                    text + " " +
                    "cparam description ("
                    + value
                    + ") contains a newline character, removing."
                )
                value = value.replace("\n", " ")
            param_description = parse_description(value).strip()

            # check that access is a known value
            if access != "readonly" and access != "readwrite":
                logging.warning(
                    text + " cparam '" + name + "' has unknown 'access' descriptor: " + access
                )

            # add a field
            fields.append(
                create_field(
                    internal_name,
                    name,
                    default_value,
                    param_description,
                    access,
                    type,
                    precious,
                )
            )
        elif key.startswith("aparam/") or key.startswith("param/"):
            # parse the param key into name, type etc
            (param, internal_name) = parse_key(key)
            (name, default_value, type, access, precious) = parse_param_value(text, "a", value)

            # warn if doc string is still using param instead of aparam
            if key.startswith("param/"):
                logging.warning(
                    text + " param (" + internal_name + ") using obsolete 'param' description, defaulting to 'aparam'"
                )

            # check that type is in the list of known types
            if type not in KNOWN_PARAM_DATA_TYPES:
                logging.warning(
                    text + " aparam '" + name + "' has unknown type: " + type
                )

            # parse description
            if "\n" in value:
                logging.info(
                    text + " " +
                    "aparam description ("
                    + value
                    + ") contains a newline character, removing."
                )
                value = value.replace("\n", " ")
            param_description = parse_description(value).strip()

            # check that access is a known value
            if access != "readonly" and access != "readwrite":
                logging.warning(
                    text + " aparam '" + name + "' has unknown 'access' descriptor: " + access
                )

            # add a field
            applicationArgs.append(
                create_field(
                    internal_name,
                    name,
                    default_value,
                    param_description,
                    access,
                    type,
                    precious,
                )
            )
        elif key.startswith("port/"):
            (port, internal_name) = parse_key(key)
            (name, type) = parse_port_value(value)

            # parse description
            if "\n" in value:
                logging.info(
                    "port description ("
                    + value
                    + ") contains a newline character, removing."
                )
                value = value.replace("\n", " ")
            port_description = parse_description(value)

            # add the port
            if direction == "in":
                inputPorts.append(
                    create_port(
                        text,
                        internal_name,
                        name,
                        direction,
                        False,
                        type,
                        port_description,
                    )
                )
            elif direction == "out":
                outputPorts.append(
                    create_port(
                        text,
                        internal_name,
                        name,
                        direction,
                        False,
                        type,
                        port_description,
                    )
                )
            else:
                logging.warning("Unknown port direction: " + direction)

    # add extra fields that must be included for the category
    add_required_fields_for_category(text, fields, category)

    # create and return the node
    # TODO: we can remove a bunch of these attributes (isData etc)
    return {
        "category": category,
        "tag": tag,
        "isData": False,
        "isGroup": False,
        "canHaveInputs": True,
        "canHaveOutputs": True,
        "drawOrderHint": 0,
        "key": get_next_key(),
        "text": text,
        "description": description,
        "collapsed": False,
        "showPorts": False,
        "streaming": False,
        "subject": None,
        "selected": False,
        "expanded": False,
        "inputApplicationName": "",
        "outputApplicationName": "",
        "exitApplicationName": "",
        "inputApplicationType": "None",
        "outputApplicationType": "None",
        "exitApplicationType": "None",
        "inputPorts": inputPorts,
        "outputPorts": outputPorts,
        "inputLocalPorts": inputLocalPorts,
        "outputLocalPorts": outputLocalPorts,
        "inputAppFields": [],
        "outputAppFields": [],
        "fields": fields,
        "applicationArgs": applicationArgs,
        "git_url": gitrepo,
        "sha": version,
    }


def write_palette_json(outputfile, nodes, gitrepo, version):
    palette = {
        "modelData": {
            "fileType": "palette",
            "repoService": "GitHub",
            "repoBranch": "master",
            "repo": "ICRAR/EAGLE_test_repo",
            "readonly": True,
            "filePath": outputfile,
            "sha": version,
            "git_url": gitrepo,
        },
        "nodeDataArray": nodes,
        "linkDataArray": [],
    }

    with open(outputfile, "w") as outfile:
        json.dump(palette, outfile, indent=4)


def process_compounddef(compounddef):
    result = []
    found_eagle_start = False

    # get child of compounddef called "briefdescription"
    briefdescription = None
    for child in compounddef:
        if child.tag == "briefdescription":
            briefdescription = child
            break

    if briefdescription is not None:
        if len(briefdescription) > 0:
            if briefdescription[0].text is None:
                logging.warning("No brief description text")
                result.append({"key": "text", "direction": None, "value": ""})
            else:
                result.append(
                    {
                        "key": "text",
                        "direction": None,
                        "value": briefdescription[0].text.strip(" ."),
                    }
                )

    # get child of compounddef called "detaileddescription"
    detaileddescription = None
    for child in compounddef:
        if child.tag == "detaileddescription":
            detaileddescription = child
            break

    # check that detailed description was found
    if detaileddescription is None:
        return result

    # search children of detaileddescription node for a para node with "simplesect" children, who have "title" children with text "EAGLE_START" and "EAGLE_END"
    para = None
    description = ""
    for ddchild in detaileddescription:
        if ddchild.tag == "para":
            if ddchild.text is not None:
                description += ddchild.text + "\n"
            for pchild in ddchild:
                if pchild.tag == "simplesect":
                    for sschild in pchild:
                        if sschild.tag == "title":
                            if sschild.text.strip() == "EAGLE_START":
                                found_eagle_start = True

                    para = ddchild

    # add description
    if description != "":
        result.append(
            {"key": "description", "direction": None, "value": description.strip()}
        )

    # check that we found an EAGLE_START, otherwise this is just regular doxygen, skip it
    if not found_eagle_start:
        return []

    # check that we found the correct para
    if para is None:
        return result

    # find parameterlist child of para
    parameterlist = None
    for pchild in para:
        if pchild.tag == "parameterlist":
            parameterlist = pchild
            break

    # check that we found a parameterlist
    if parameterlist is None:
        return result

    # read the parameters from the parameter list
    for parameteritem in parameterlist:
        key = None
        direction = None
        value = None
        for pichild in parameteritem:
            if pichild.tag == "parameternamelist":
                key = pichild[0].text.strip()
                direction = pichild[0].attrib.get("direction", "").strip()
            elif pichild.tag == "parameterdescription":
                if key == "gitrepo" and isinstance(pichild[0], list):
                    # the gitrepo is a URL, so is contained within a <ulink> element,
                    # therefore we need to use pichild[0][0] here to look one level deeper
                    # in the hierarchy
                    if pichild[0][0] is None or pichild[0][0].text is None:
                        logging.warning("No gitrepo text")
                        value = ""
                    else:
                        value = pichild[0][0].text.strip()
                else:
                    if pichild[0].text is None:
                        logging.warning("No key text (key: " + key + ")")
                        value = ""
                    else:
                        value = pichild[0].text.strip()

        result.append({"key": key, "direction": direction, "value": value})

    return result


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S", level = logging.INFO)

    (inputdir, tag, outputfile) = get_options_from_command_line(sys.argv[1:])

    # create a temp directory for the output of doxygen
    output_directory = tempfile.TemporaryDirectory()

    # read environment variables
    if not check_environment_variables():
        sys.exit(1)

    # add extra doxygen setting for input and output locations
    DOXYGEN_SETTINGS.append(("PROJECT_NAME", os.environ.get("PROJECT_NAME")))
    DOXYGEN_SETTINGS.append(("INPUT", inputdir))
    DOXYGEN_SETTINGS.append(("OUTPUT_DIRECTORY", output_directory.name))

    # create a temp file to contain the Doxyfile
    doxygen_file = tempfile.NamedTemporaryFile()
    doxygen_filename = doxygen_file.name
    doxygen_file.close()

    # create a default Doxyfile
    subprocess.call(
        ["doxygen", "-g", doxygen_filename],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.info("Wrote doxygen configuration file (Doxyfile) to " + doxygen_filename)

    # modify options in the Doxyfile
    modify_doxygen_options(doxygen_filename, DOXYGEN_SETTINGS)

    # run doxygen
    # os.system("doxygen " + doxygen_filename)
    subprocess.call(
        ["doxygen", doxygen_filename],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # run xsltproc
    output_xml_filename = output_directory.name + "/xml/doxygen.xml"

    with open(output_xml_filename, "w") as outfile:
        subprocess.call(
            [
                "xsltproc",
                output_directory.name + "/xml/combine.xslt",
                output_directory.name + "/xml/index.xml",
            ],
            stdout=outfile,
            stderr=subprocess.DEVNULL,
        )

    # get environment variables
    gitrepo = os.environ.get("GIT_REPO")
    version = os.environ.get("PROJECT_VERSION")

    # init nodes array
    nodes = []

    # load the input xml file
    tree = ET.parse(output_xml_filename)
    xml_root = tree.getroot()

    for compounddef in xml_root:
        params = process_compounddef(compounddef)

        # if no params were found, or only the name and description were found, then don't bother creating a node
        if len(params) > 2:
            # print("params (" + str(len(params)) + "): " + str(params))

            # create a node
            n = create_palette_node_from_params(params)

            # if the node tag matches the command line tag, or no tag was specified on the command line, add the node to the list to output
            if n["tag"] == tag or tag == "":
                logging.info("Adding component: " + n["text"])
                nodes.append(n)

        # check if gitrepo and version params were found and cache the values
        for param in params:
            key = param["key"]
            value = param["value"]

            if key == "gitrepo":
                gitrepo = value
            elif key == "version":
                version = value

    # write the output json file
    write_palette_json(outputfile, nodes, gitrepo, version)
    logging.info("Wrote " + str(len(nodes)) + " component(s)")

    # cleanup the output directory
    output_directory.cleanup()
