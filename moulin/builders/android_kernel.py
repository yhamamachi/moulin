# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 EPAM Systems
"""
Android kernel builder module
"""

import os.path
from typing import List
from moulin.yaml_wrapper import YamlValue
from moulin import ninja_syntax
from moulin import utils


def get_builder(conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                generator: ninja_syntax.Writer):
    """
    Return configured AndroidKernel class
    """
    return AndroidKernel(conf, name, build_dir, src_stamps, generator)


def gen_build_rules(generator: ninja_syntax.Writer):
    """
    Generate yocto build rules for ninja
    """
    cmd = " && ".join([
        "export $env",
        "cd $build_dir",
        "build/build.sh",
    ])
    generator.rule("android_kernel_build",
                   command=f'bash -c "{cmd}"',
                   description="Invoke Android Kernel build script",
                   pool="console")
    generator.newline()


class AndroidKernel:
    """
    AndroidBuilder class generates Ninja rules for given Android build configuration
    """
    def __init__(self, conf: YamlValue, name: str, build_dir: str, src_stamps: List[str],
                 generator: ninja_syntax.Writer):
        self.conf = conf
        self.name = name
        self.generator = generator
        self.src_stamps = src_stamps
        self.build_dir = build_dir

    def gen_build(self):
        """Generate ninja rules to build AOSP"""

        env_node = self.conf.get("env", None)
        if env_node:
            env_values = [x.as_str for x in env_node]
        else:
            env_values = []
        env = " ".join(env_values)

        env = utils.escape(env)

        variables = {
            "build_dir": self.build_dir,
            "env": env,
        }
        targets = self.get_targets()
        self.generator.build(targets, "android_kernel_build", self.src_stamps, variables=variables)
        self.generator.newline()

        return targets

    def get_targets(self):
        "Return list of targets that are generated by this build"
        return [os.path.join(self.build_dir, t.as_str) for t in self.conf["target_images"]]

    def capture_state(self):
        """
        This method should capture Android Kernel state for a reproducible builds.
        Luckily, there is nothing to do, as Android state is controlled solely by
        its repo state. And repo state is captured by repo fetcher code.
        """
