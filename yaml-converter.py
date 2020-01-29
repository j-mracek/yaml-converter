#!/usr/bin/python3

import dnf
import dnf.cli
import errno
import os
import sys
import string
import re


def module_requires_to_string(module):
    req_list = []
    for req in module.getModuleDependencies():
        for require_dict in req.getRequires():
            for mod_require, streams in require_dict.items():
                req_list.append("{}:[{}]".format(mod_require, ",".join(streams)))
    return ";".join(sorted(req_list))


def modify_string(yaml, pattern, new):
    return re.subn(pattern, new, yaml)


def create_directory(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def merge_and_write_new_yamls(new_md_doc_repo_dict):
    output_dir = 'output_yamls'
    create_directory(output_dir)
    for repoid, md_doc_list in new_md_doc_repo_dict.items():
        repo_path = os.path.join(output_dir, repoid)
        create_directory(repo_path)
        new_yaml = "".join(sorted(md_doc_list))
        path = os.path.join(repo_path, 'modules.yaml')
        with open(path, mode='w') as file:
            file.write(new_yaml)


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
        raise ValueError("cannot detect md version for {}".format(module.getFullIdentifier()))
    module_stream_dict.setdefault(
        module.getNameStream(), {}).setdefault(md_version, []).append(module)

new_md_doc_repo_dict = {}  # { repoid: [new_md_doc]}
for module_stream in module_stream_dict.values():
    if 2 not in module_stream:
        for module_list in module_stream.values():
            for module_pkg in module_list:
                new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(module.getYaml())
    if 3 in module_stream:
        pass
    else:
        dependency_dict = {}  # { dependencies_string: [module_pkgs]}
        for module_list in module_stream.values():
            for module_pkg in module_list:
                dependency_dict.setdefault(
                    module_requires_to_string(module_pkg), []).append(module_pkg)
        x = 0
        for module_list in dependency_dict.values():
            new_string_context = "context: {}".format(string.ascii_lowercase[x])
            for module in module_list:
                new_md_doc = ""
                data_section_found = False
                for line in module.getYaml().split("\n"):
                    if not data_section_found:
                        if line.startswith("data:"):
                            data_section_found = True
                        continue
                    if not line.startswith(" "):
                        raise ValueError(
                            "cannot detect contect in {}".format(module.getFullIdentifier()))
                    match = re.match(r"  (context:\s*\S+)", line)
                    if match:
                        modified = modify_string(module.getYaml(), match.group(1), new_string_context)
                        if modified[1] == 0:
                            raise ValueError("Matched incorrectly context", match.group(1), line, modified[1], module.getYaml())
                        new_md_doc = modified[0]
                        break
                modified = modify_string(new_md_doc, r'\nversion:\s*\d+', '\nversion: 3')
                if modified[1] != 1:
                    raise ValueError("Matched incorrectly version")
                new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(modified[0])
            x += 1

merge_and_write_new_yamls(new_md_doc_repo_dict)
