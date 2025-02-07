#!/usr/bin/env python3

import os
import struct
import subprocess
from sonic_py_common import device_info
from mmap import *


class APIHelper():

    def __init__(self):
        (self.platform, self.hwsku) = device_info.get_platform_and_hwsku()

    def is_host(self):
        return not os.path.isfile('/.dockerenv')

    def pci_get_value(self, resource, offset):
        status = True
        result = ""
        try:
            fd = os.open(resource, os.O_RDWR)
            mm = mmap(fd, 0)
            mm.seek(int(offset))
            read_data_stream = mm.read(4)
            result = struct.unpack('I', read_data_stream)
        except Exception as E:
            print(str(E))
            status = False
        return status, result

    def run_command(self, cmd):
        status = True
        result = ""
        try:
            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_data, err = p.communicate()
            if err == b'':
                result = raw_data.strip()
        except Exception as E:
            print(str(E))
            status = False
        return status, result

    def run_interactive_command(self, cmd):
        try:
            os.system(cmd)
        except Exception as E:
            print(str(E))
            return False
        return True

    def read_txt_file(self, file_path):
        try:
            with open(file_path, 'r') as fd:
                data = fd.read()
                return data.strip()
        except IOError:
            pass
        return None

    def read_one_line_file(self, file_path):
        try:
            with open(file_path, 'r') as fd:
                data = fd.readline()
                return data.strip()
        except IOError:
            pass
        return None

    def write_txt_file(self, file_path, value):
        try:
            with open(file_path, 'w') as fd: 
                fd.write(str(value))
        except Exception as E:
            print(str(E))
            return False
        return True

    def get_cpld_reg_value(self, getreg_path, register):
        cmd = "echo {1} > {0}; cat {0}".format(getreg_path, register)
        status, result = self.run_command(cmd)
        return result if status else None

    def ipmi_raw(self, netfn, cmd):
        status = True
        result = ""
        try:
            cmd = "ipmitool raw {} {}".format(str(netfn), str(cmd))
            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_data, err = p.communicate()
            if err == b'':
                result = raw_data.strip()
            else:
                status = False
        except Exception as E:
            print(str(E))
            status = False
        return status, result

    def ipmi_fru_id(self, id, key=None):
        status = True
        result = ""
        try:
            cmd = "ipmitool fru print {}".format(str(
                id)) if not key else "ipmitool fru print {0} | grep '{1}' ".format(str(id), str(key))

            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_data, err = p.communicate()
            if err == b'':
                result = raw_data.strip()
            else:
                status = False
        except Exception as E:
            print(str(E))
            status = False
        return status, result

    def ipmi_set_ss_thres(self, id, threshold_key, value):
        status = True
        result = ""
        try:
            cmd = "ipmitool sensor thresh '{}' {} {}".format(
                str(id), str(threshold_key), str(value))
            p = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_data, err = p.communicate()
            if err == '':
                result = raw_data.strip()
            else:
                status = False
        except Exception as E:
            print(str(E))
            status = False
        return status, result
