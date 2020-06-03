#
#    ICRAR - International Centre for Radio Astronomy Research
#    (c) UWA - The University of Western Australia, 2020
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

import os
import subprocess

from setuptools import find_packages
from setuptools import setup

# Version information
# We do like numpy: we have a major/minor/patch hand-written version written
# here. If we find the git commit (either via "git" command execution or in a
# dlg/version.py file) we append it to the VERSION later.
# The RELEASE flag allows us to create development versions properly supported
# by setuptools/pkg_resources or "final" versions.
MAJOR = 1
MINOR = 0
PATCH = 0
RELEASE = True
VERSION = "%d.%d.%d" % (MAJOR, MINOR, PATCH)
VERSION_FILE = "dlg/translator/version.py"


def get_git_version():
    out = subprocess.check_output(["git", "rev-parse", "HEAD"])
    return out.strip().decode("ascii")


def get_version_info():
    git_version = "Unknown"
    if os.path.exists(".git"):
        git_version = get_git_version()
    full_version = VERSION
    if not RELEASE:
        full_version = "%s.dev0+%s" % (VERSION, git_version[:7])
    return full_version, git_version


def write_version_info():
    tpl = """
# THIS FILE IS GENERATED BY SETUP.PY
# DO NOT MODIFY BY HAND
version = '%(version)s'
git_version = '%(git_version)s'
full_version = '%(full_version)s'
is_release = %(is_release)s

if not is_release:
    version = full_version
"""
    full_version, git_version = get_version_info()
    with open(VERSION_FILE, "w") as f:
        info = tpl % {
            "version": VERSION,
            "full_version": full_version,
            "git_version": git_version,
            "is_release": RELEASE,
        }
        f.write(info.strip())


# Every time we overwrite the version file
write_version_info()

install_requires = [
    "bottle",
    "daliuge-common==%s" % (VERSION,),
    "metis>=0.2a3",
    # Python 3.6 is only supported in NetworkX 2 and above
    # But we are not compatible with 2.4 yet, so we need to constrain that
    "networkx<2.4; python_version<'3.6'",
    "networkx<2.4,>= 2.0; python_version>='3.6.0'",
    "numpy",
    "psutil",
    "pyswarm",
    # 1.10 contains an important race-condition fix on lazy-loaded modules
    "six>=1.10",
    "cwlgen",
]

setup(
    name="daliuge-translator",
    version=get_version_info()[0],
    description=u"Data Activated \uF9CA (flow) Graph Engine - Graph Translation",
    long_description="The SKA-SDK prototype for the Execution Framework component",
    author="ICRAR DIA Group",
    author_email="rtobar@icrar.org",
    url="https://github.com/ICRAR/daliuge",
    license="LGPLv2+",
    install_requires=install_requires,
    packages=find_packages(),
    entry_points = {
        'dlg.tool_commands': ['translator=dlg.translator.tool_commands']
    },
    test_suite="test",
)
