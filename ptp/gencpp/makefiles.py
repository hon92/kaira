#
#    Copyright (C) 2012 Stanislav Bohm
#
#    This file is part of Kaira.
#
#    Kaira is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License, or
#    (at your option) any later version.
#
#    Kaira is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Kaira.  If not, see <http://www.gnu.org/licenses/>.
#

import base.utils
import paths
import os

def prepare_makefile(project, libs = [], libdir = [], include = []):

    #Add defaults
    libs.append("cailie")
    libs.append("pthread")
    libs.append("rt")
    libdir.append(paths.CAILIE_LIB_DIR)
    include.append(paths.CAILIE_DIR)

    makefile = base.utils.Makefile()
    makefile.set_top_comment("This file is autogenerated.\nDo not edit directly this file.")
    makefile.set("CC", project.get_build_option("CC"))
    makefile.set("CFLAGS", project.get_build_option("CFLAGS"))

    makefile.set("LIBDIR", " ".join(("-L" + s for s in libdir)))
    makefile.set("LIBS", " ".join(("-l" + s for s in libs)) + " " + project.get_build_option("LIBS"))
    makefile.set("INCLUDE", " ".join(("-I" + s for s in include)))

    makefile.set("MPICC", "mpic++")
    makefile.set("MPILIBS", "-lcailiempi -lpthread -lrt " + project.get_build_option("LIBS"))
    makefile.set("MPILIBDIR", "-L" + paths.CAILIE_MPI_LIB_DIR)

    makefile.rule(".cpp.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
    makefile.rule(".cc.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")
    makefile.rule(".c.o", [], "$(CC) $(CFLAGS) $(INCLUDE) -c $< -o $@")

    return makefile

def get_other_dependancies(project):
    if project.get_build_option("OTHER_FILES"):
        return [ os.path.splitext(f)[0] + ".o" for f in project.get_build_option("OTHER_FILES").split("\n") ]
    else:
        return []

def write_program_makefile(project, directory):
    makefile = prepare_makefile(project)

    name = project.get_name()
    name_o = name + ".o"
    name_cpp = name + ".cpp"
    name_debug = name + "_debug"
    name_debug_o = name + "_debug.o"
    name_mpi_o = name + "_mpi.o"
    name_mpi_debug_o = name + "_mpi_debug.o"

    makefile.rule("all", [ name ], phony = True)
    makefile.rule("debug", [ name_debug ], phony = True)
    makefile.rule("mpi", [ name + "_mpi"], phony = True)
    makefile.rule("mpidebug", [name + "_mpidebug"], phony = True)

    other_deps = get_other_dependancies(project)

    deps = [ name_o ] + other_deps
    deps_debug = [ name_debug_o ] + other_deps
    deps_mpi = [ name_mpi_o ] + other_deps
    deps_mpi_debug = [ name_mpi_debug_o ] + other_deps
    makefile.rule(name, deps,
        "$(CC) " + " ".join(deps) + " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIBS) " )

    makefile.rule(name_debug, deps_debug,
        "$(CC) " + " ".join(deps_debug) + " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIBS) " )

    makefile.rule(name + "_mpi", deps_mpi, "$(MPICC) -D CA_MPI " + " ".join(deps_mpi)
        + " -o $@ $(CFLAGS) $(INCLUDE) $(MPILIBDIR) $(MPILIBS)" )
    makefile.rule(name + "_mpidebug", deps_mpi_debug, "$(MPICC) -D CA_MPI " + " ".join(deps_mpi_debug)
        + " -o $@ $(CFLAGS) $(INCLUDE) $(MPILIBDIR) $(MPILIBS)" )

    makefile.rule(name_o, [ name_cpp, "head.cpp" ], "$(CC) $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_o))

    makefile.rule(name_debug_o, [ name_cpp, "head.cpp" ],
        "$(CC) -DCA_LOG $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_debug_o))
    makefile.rule(name_mpi_o, [ name_cpp, "head.cpp" ],
        "$(MPICC) -DCA_MPI $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_mpi_o))
    makefile.rule(name_mpi_debug_o, [ name_cpp, "head.cpp" ],
        "$(MPICC) -DCA_MPI -DCA_LOG $(CFLAGS) $(INCLUDE) -c {0} -o {1}".format(name_cpp, name_mpi_debug_o))
    all = deps + [ name_o, name_mpi_o, name_debug_o, name_mpi_debug_o ]

    makefile.rule("clean", [],
        "rm -f {0} {0}_debug {0}_mpi {0}_mpidebug {1}".format(name," ".join(all)), phony = True)
    makefile.write_to_file(os.path.join(directory, "makefile"))

def write_server_makefile(project, directory):
    makefile = prepare_makefile(project, libs=["caserver"],
                                     libdir=[paths.CASERVER_DIR],
                                     include=[paths.CASERVER_DIR])

    makefile.set("CASERVER_INCLUDE", "-I" + paths.CASERVER_DIR)
    makefile.set("CASERVER_LIBDIR", "-L" + paths.CASERVER_DIR)

    name = project.get_name() + "_server"
    name_o = name + ".o"
    other_deps = get_other_dependancies(project)
    deps = [ name_o ] + other_deps
    makefile.rule(name, deps, "$(CC) " + " ".join(deps) +
            " -o $@ $(CFLAGS) $(INCLUDE) $(LIBDIR) $(LIBS)" )
    makefile.rule("clean", [], "rm -f {0} {1}".format(name," ".join(deps)))
    makefile.write_to_file(os.path.join(directory, "makefile"))

def write_library_makefile(project, directory, octave = False):

    makefile = prepare_makefile(project)
    other_deps = get_other_dependancies(project)

    name = project.get_name()
    name_o = name + ".o"
    libname_a = "lib{0}.a".format(name)

    targets = [ libname_a ]
    if octave:
        targets.append("octave")

    makefile.rule("all", targets, phony = True)

    if octave:
        name_oct = name + ".oct"
        name_oct_cpp = name + "_oct.cpp"
        makefile.rule("octave", [ name_oct ], phony = True)
        makefile.rule(name_oct, [ name_oct_cpp ], "mkoctfile $< $(INCLUDE) -L. $(LIBDIR) -l{0} $(LIBS) -o {1}".format(name,name_oct))

    deps = [ name_o ] + other_deps
    makefile.rule(libname_a, deps, "ar -cr lib{0}.a ".format(name) + " ".join(deps))

    all = deps + [ libname_a ]

    if octave:
        all.append(name_oct)

    makefile.rule("clean", [], "rm -f {0}".format(" ".join(all)), phony = True)
    makefile.write_to_file(os.path.join(directory, "makefile"))


def write_client_library_makefile(project, directory):
    makefile = prepare_makefile(project)
    other_deps = get_other_dependancies(project)

    name = project.get_name()
    name_o = name + ".o"
    libname_a = "lib{0}.a".format(name)

    makefile.rule("all", [ libname_a, "server" ], phony = True)
    makefile.rule("server", [], "make -C server", phony = True)

    deps = [ name_o ] + other_deps
    makefile.rule(libname_a, deps, "ar -cr lib{0}.a ".format(name) + " ".join(deps))

    all = deps + [ libname_a ]

    makefile.rule("clean", [], "rm -f {0}".format(" ".join(all)))

    makefile.write_to_file(os.path.join(directory, "makefile"))