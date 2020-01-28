#!/usr/bin/python3

import dnf

base = dnf.base.Base()
base.conf.releasever='30'
base.read_all_repos()

base.fill_sack(load_system_repo=False)
modules = base._moduleContainer.getModulePackages()
for module in modules:
    print(dir(module))
    break
