# ASAP
The Aerospace Structural Analysis Program (ASAP) is an airframe modeling and
FEM generation tool developed by Laughlin Research, LLC. ASAP enables the use
of high-order structural analysis in the early phases of aircraft design.

# Installation
ASAP is currently developed for Python 3.5. Anaconda Python is recommended
for package management and since pre-built binaries are available for the
ASAP prerequisites using the Anaconda cloud (only for Windows 32- and 64-bit).


# Prerequisites
ASAP relies on a number of LGPL licensed open-source tools, including:

* [OpenCASCADE Community Edition](https://github.com/tpaviot/oce/releases/tag/OCE-0.18.1)
* [pythonocc-core](https://github.com/trelau/pythonocc-core/releases/tag/0.18.2)
* [Netgen](https://github.com/trelau/netgen/releases/tag/6.3)
* [SMESH](https://github.com/trelau/smesh/releases/tag/7.7.2)

Pre-built binaries for these tools are available through the Anaconda cloud
for Python 3.5 Windows 32- and 64-bit. It is recommended that a designated
environment be created and used for ASAP. An example of creating this
environment for Anaconda Python within an Anaconda command prompt is:

    conda create -n asap python=3.5

This will create an environment named "asap" with Python 3.5. Make sure this
environment is active when using ASAP. For Anaconda Python, activating this
environment may look like:

    activate asap

within an Anaconda command prompt. At this point the prerequisites can be
installed using specified channels on the Anaconda cloud:

    conda install -c trelau -c oce -c dlr-sc -c conda-forge pythonocc-core=0.18.2

This should automatically resolve all dependencies and install all the
required packages.

Other dependencies such as NumPy and SciPy can be installed as needed using
the conda package manager:

    conda install numpy scipy

# Installing ASAP
Be sure to activate the designed ASAP environment before installation.

ASAP is a pure Python package and can be installed using the command:

    python setup.py develop

within the ASAP root folder. The "develop" option links to the source code
at runtime so changes in the source are reflected in any programs using ASAP.

# Getting Started
The best way to get started is to examine and run the files in the examples and
test folders.

# Notice
Copyright (c) 2017, Laughlin Research, LLC

Terms of Use:

The ASAP Code, including its source code and related software
documentation (collectively, the "ASAP Code"), as distributed herein
and as may be subsequently revised, in whole and in part, is for
government use only pursuant to development agreements between NASA,
Georgia Institute of Technology, and Laughlin Research, LLC. At the
time of distribution hereof, none of the ASAP Code is believed or
intended to be open source. Disclosure of the ASAP Code is strictly
subject to one or more restrictive covenants, including
non-disclosure and non-circumvention covenants, and any use of the
whole or a part of the ASAP Code constitutes acknowledgement and
acceptance of said covenants. Any unauthorized use, disclosure,
and/or sale of the ASAP Code or any portion thereof may be actionable
under current law.

Laughlin Research, LLC retains all commercial rights to the ASAP Code.
