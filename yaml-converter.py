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


def create_dependency_dict(list_list_modules):
    """
    :param list_list_modules:  [[modules] [modules]]
    :return: { dependencies_string: [module_pkgs]}
    """
    dependency_dict = {}  # { dependencies_string: [module_pkgs]}
    for module_list in list_list_modules:
        for module_pkg in module_list:
            dependency_dict.setdefault(
                module_requires_to_string(module_pkg), []).append(module_pkg)
    return dependency_dict


def modify_yaml(module, new_string_context):
    matched_context = find_context_string(module)
    if not matched_context:
        raise ValueError("Context not found: ", module.getFullIdentifier)
    modified = modify_string(module.getYaml(), matched_context, new_string_context)
    if modified[1] == 0:
        raise ValueError(
            "Context not matched", matched_context, module.getFullIdentifier)
    new_md_doc = modified[0]
    modified = modify_string(new_md_doc, r'\nversion:\s*\d+', '\nversion: 3')
    if modified[1] != 1:
        raise ValueError("Matched incorrectly version")
    return modified[0]


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


def find_context_string(module):
    yaml_md = module.getYaml()
    data_section_found = False
    for line in yaml_md.split("\n"):
        if not data_section_found:
            if line.startswith("data:"):
                data_section_found = True
            continue
        if not line.startswith(" "):
            raise ValueError(
                "cannot detect contect in {}".format(module.getFullIdentifier()))
        pattern = "\s+(context:\s*{})".format(module.getContext())
        match = re.match(pattern, line)
        if match:
            return match.group(1)
    return None


base = dnf.base.Base()
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
    if md_version not in [2, 3]:
        raise ValueError("cannot detect supported md version for {}: {}".format(
            module.getFullIdentifier(), md_version))
    module_stream_dict.setdefault(
        module.getNameStream(), {}).setdefault(md_version, []).append(module)

new_md_doc_repo_dict = {}  # { repoid: [new_md_doc]}
for module_stream in module_stream_dict.values():
    if 2 not in module_stream:
        for module_list in module_stream.values():
            for module in module_list:
                new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(module.getYaml())
    if 3 in module_stream:
        v3_list_modules = module_stream[3]
        dependency_v3_dict = create_dependency_dict([v3_list_modules])  # { dependencies_string: [module_pkgs]}
        # add v3 to output set
        for module in v3_list_modules:
            new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(module.getYaml())

        for md_version, module_list in module_stream.items():
            if md_version == 3:
                continue
            dependency_dict = create_dependency_dict([module_list])
            x = 0
            for dependencies_string, module_list in dependency_dict.items():
                if dependencies_string in dependency_v3_dict:
                    context = dependency_v3_dict[dependencies_string][0].getContext()
                    new_string_context = "context: {}".format(context)
                else:
                    new_string_context = "context: {}".format(string.ascii_lowercase[x])
                    x += 1
                for module in module_list:
                    modified_yaml = modify_yaml(module, new_string_context)
                    new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(modified_yaml)

    else:
        dependency_dict = create_dependency_dict(module_stream.values())
        x = 0
        for module_list in dependency_dict.values():
            new_string_context = "context: {}".format(string.ascii_lowercase[x])
            for module in module_list:
                modified_yaml = modify_yaml(module, new_string_context)
                new_md_doc_repo_dict.setdefault(module.getRepoID(), []).append(modified_yaml)
            x += 1

merge_and_write_new_yamls(new_md_doc_repo_dict)
