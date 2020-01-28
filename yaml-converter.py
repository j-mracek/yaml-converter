#!/usr/bin/python3

import dnf
import dnf.cli
import sys

base = dnf.base.Base()
base.conf.releasever='30'
base.read_all_repos()
# add internal callback from dnf
base.repos.all().set_progress_bar(dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout))

base.fill_sack(load_system_repo=False)
modules = base._moduleContainer.getModulePackages()
module_stream_dict = {}  # name_stream: { md_version : [module_pkgs]}
for module in modules:
    md_version = 0
    for line in module.getYaml().split("\n"):
        if line.startswith("version:"):
            md_version = int(line[8:].strip())
            break
    if not md_version:
        raise ValueError("cannot detect md version for {}".format(module.getFullIdentifier()) )
    module_stream_dict.setdefault(
        module.getNameStream(), {}).setdefault(md_version, []).append(module)
