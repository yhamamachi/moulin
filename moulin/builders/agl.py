# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Yocto builder module
"""

import os.path
import shlex
from typing import List, Tuple, cast
from moulin.utils import create_stamp_name, construct_fetcher_dep_cmd
from moulin import ninja_syntax
from moulin.yaml_wrapper import YamlValue
from moulin.yaml_helpers import YAMLProcessingError


def get_builder(conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                generator: ninja_syntax.Writer):
    """
    Return configured AGLBuilder class
    """
    return AGLBuilder(conf, name, build_dir, src_stamps, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """
    Generate AGL build rules for ninja
    """
    # Create build dir by calling poky/oe-init-build-env script
    cmd = " && ".join([
        "cd $agl_dir",
        "source meta-agl/scripts/aglsetup.sh -m $agl_machine -b $work_dir $agl_features",
    ])
    generator.rule("agl_init_env",
                   command=f'bash -c "{cmd}"',
                   description="Initialize AGL build environment",
                   restat=True)
    generator.newline()

    # Invoke bitbake. This rule uses "console" pool so we can see the bitbake output.
    cmd = " && ".join([
        # Generate fetcher dependency file
        construct_fetcher_dep_cmd(),
        "cd $agl_dir",
        "source $work_dir/agl-init-build-env",
        "bitbake $target",
    ])
    generator.rule("agl_build",
                   command=f'bash -c "{cmd}"',
                   description="AGL Build: $name",
                   pool="console",
                   deps="gcc",
                   depfile=".moulin_$name.d",
                   restat=True)


def _flatten_yocto_conf(conf: YamlValue) -> List[Tuple[str, str]]:
    """
    Flatten conf entries. While using YAML *entries syntax, we will get list of conf
    entries inside of other list. To overcome this, we need to move inner list 'up'
    """

    # Problem is conf entries that it is list itself
    result: List[Tuple[str, str]] = []
    for entry in conf:
        if not entry.is_list:
            raise YAMLProcessingError("Exptected array on 'conf' node", entry.mark)
        if entry[0].is_list:
            result.extend([(x[0].as_str, x[1].as_str) for x in entry])
        else:
            result.append((entry[0].as_str, entry[1].as_str))
    return result


class AGLBuilder:
    """
    AGLBuilder class generates Ninja rules for given build configuration
    """
    def __init__(self, conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                 generator: ninja_syntax.Writer):
        print('conf:= ', conf)
        print('name:= ', name)
        print('generator:= ', generator)
        print('src_stamps:= ', src_stamps)
        print('build_dir:= ', build_dir)
        print('agl_features:= ', conf.get("agl_features", "build").as_str)
        print('agl_machine:= ', conf.get("agl_machine", "build").as_str)
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        # With yocto builder it is possible to have multiple builds with the same set of
        # layers. Thus, we have two variables - build_dir and work_dir
        # - yocto_dir is the upper directory where layers are stored. Basically, we should
        #   have "poky" in our yocto_dir
        # - work_dir is the build directory where we can find conf/local.conf, tmp and other
        #   directories. It is called "build" by default
        self.agl_dir = build_dir
        self.work_dir: str = conf.get("work_dir", "build").as_str
        self.agl_features: str = conf.get("agl_features", "build").as_str
        self.agl_machine: str = conf.get("agl_machine", "build").as_str

    def gen_build(self):
        """Generate ninja rules to build agl"""
        common_variables = {
            "agl_dir": self.agl_dir,
            "work_dir": self.work_dir,
            "agl_features": self.agl_features,
            "agl_machine": self.agl_machine,
        }

        # First we need to ensure that "conf" dir exists
        env_target = os.path.join(self.agl_dir, self.work_dir, "agl-init-build-env")
        self.generator.build(env_target,
                             "agl_init_env",
                             self.src_stamps,
                             variables=common_variables)
        self.generator.newline()

        # Next step - invoke bitbake. At last :)
        targets = self.get_targets()
        deps = env_target
        # deps.append(local_conf_target)
        self.generator.build(targets,
                             "agl_build",
                             deps,
                             variables=dict(common_variables,
                                            target=self.conf["build_target"].as_str,
                                            name=self.name))

        return targets

    def get_targets(self):
        "Return list of targets that are generated by this build"
        return [
            os.path.join(self.agl_dir, self.work_dir, t.as_str)
            for t in self.conf["target_images"]
        ]

    def capture_state(self):
        """
        Update stored local conf with actual SRCREVs for VCS-based recipes.
        This should ensure that we can reproduce this exact build later
        """
