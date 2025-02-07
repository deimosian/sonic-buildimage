#!/usr/bin/env python

#############################################################################
# Celestica (c) 2022
#
# Module contains an implementation of SONiC Platform Base API and
# provides the PSUs status which are available in the platform
#
#############################################################################

import os
import subprocess
import sys
import re
import math

try:
    from sonic_platform_base.psu_base import PsuBase
    from sonic_platform.fan import Fan
    from sonic_platform.helper import APIHelper
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

GREEN_LED_PATH = "/sys/devices/platform/leds_dx010/leds/dx010:green:p-{}/brightness"
HWMON_PATH = "/sys/bus/i2c/devices/i2c-{0}/{0}-00{1}/hwmon"
GPIO_DIR = "/sys/class/gpio"
GPIO_LABEL = "pca9505"
PSU_NAME_LIST = ["PSU-1", "PSU-2"]
PSU_NUM_FAN = [1, 1]
PSU_I2C_MAPPING = {
    0: {
        "num": 10,
        "addr": "5a"
    },
    1: {
        "num": 11,
        "addr": "5b"
    },
}

IPMI_OEM_NETFN = "0x39"
IPMI_SENSOR_NETFN = "0x04"
IPMI_SS_READ_CMD = "0x2D {}"
IPMI_SET_PSU_LED_CMD = "0x02 0x02 {}"
IPMI_GET_PSU_LED_CMD = "0x01 0x02"
IPMI_FRU_PRINT_ID = "ipmitool fru print {}"
IPMI_FRU_MODEL_KEY = "Board Product"
IPMI_FRU_SERIAL_KEY = "Board Serial "

PSU_LED_OFF_CMD = "0x00"
PSU_LED_GREEN_CMD = "0x01"
PSU_LED_AMBER_CMD = "0x02"

PSU1_VOUT_SS_ID = "0x2e"
PSU1_COUT_SS_ID = "0x2f"
PSU1_POUT_SS_ID = "0x30"
PSU1_STATUS_REG = "0x3a"
PSU1_TMP1_REG = "0x2c"
PSU1_TMP2_REG = "0x2d"
PSU1_TMP3_REG = "0x6a"

PSU2_VOUT_SS_ID = "0x37"
PSU2_COUT_SS_ID = "0x38"
PSU2_POUT_SS_ID = "0x39"
PSU2_STATUS_REG = "0x3b"
# TODO: Implement temperature reading
PSU2_TMP1_REG = "0x35"
PSU2_TMP2_REG = "0x36"
PSU2_TMP3_REG = "0x6b"

PSU1_FRU_ID = 3

SS_READ_OFFSET = 0
PSU_MAX_POWER = 1500

class Psu(PsuBase):
    """Platform-specific Psu class"""

    def __init__(self, psu_index):
        PsuBase.__init__(self)
        self.index = psu_index
        self._api_helper = APIHelper()
        self.green_led_path = GREEN_LED_PATH.format(self.index+1)

        self.ipmi_raw = "ipmitool raw 0x4 0x2d"

        self.psu1_id = "0x3a"
        self.psu2_id = "0x3b"


        self.dx010_psu_gpio = [
            {'base': self.__get_gpio_base()},
            {'prs': 27, 'status': 22},
            {'prs': 28, 'status': 25}
        ]
        self.i2c_num = PSU_I2C_MAPPING[self.index]["num"]
        self.i2c_addr = PSU_I2C_MAPPING[self.index]["addr"]
        self.hwmon_path = HWMON_PATH.format(self.i2c_num, self.i2c_addr)
        for fan_index in range(0, PSU_NUM_FAN[self.index]):
            fan = Fan(fan_index, 0, True, self.index)
            self._fan_list.append(fan)

    def __search_file_by_contain(self, directory, search_str, file_start):
        for dirpath, dirnames, files in os.walk(directory):
            for name in files:
                file_path = os.path.join(dirpath, name)
                if name.startswith(file_start) and search_str in self._api_helper.read_txt_file(file_path):
                    return file_path
        return None

    def __get_gpio_base(self):
        for r in os.listdir(GPIO_DIR):
            label_path = os.path.join(GPIO_DIR, r, "label")
            if "gpiochip" in r and GPIO_LABEL in self._api_helper.read_txt_file(label_path):
                return int(r[8:], 10)
        return 216  # Reserve

    def __get_gpio_value(self, pinnum):
        gpio_base = self.dx010_psu_gpio[0]['base']
        gpio_dir = GPIO_DIR + '/gpio' + str(gpio_base+pinnum)
        gpio_file = gpio_dir + "/value"
        retval = self._api_helper.read_txt_file(gpio_file)
        return retval.rstrip('\r\n')

    # TODO: Implement PSU voltage range
    def get_voltage(self):
        """
        Retrieves current PSU voltage output
        Returns:
            A float number, the output voltage in volts,
            e.g. 12.1
        """
        psu_vout_key = globals()['PSU{}_VOUT_SS_ID'.format(self.index + 1)]
        status, raw_ss_read = self._api_helper.ipmi_raw(
            IPMI_SENSOR_NETFN, IPMI_SS_READ_CMD.format(psu_vout_key))
        ss_read = raw_ss_read.split()[SS_READ_OFFSET]
        # Formula: Rx1x10^-1
        psu_voltage = int(ss_read, 16) * math.pow(10, -1)

        return psu_voltage

    def get_current(self):
        """
        Retrieves present electric current supplied by PSU
        Returns:
            A float number, the electric current in amperes, e.g 15.4
        """
        psu_cout_key = globals()['PSU{}_COUT_SS_ID'.format(self.index + 1)]
        status, raw_ss_read = self._api_helper.ipmi_raw(
            IPMI_SENSOR_NETFN, IPMI_SS_READ_CMD.format(psu_cout_key))
        ss_read = raw_ss_read.split()[SS_READ_OFFSET]
        # Formula: Rx5x10^-1
        psu_current = int(ss_read, 16) * 5 * math.pow(10, -1)

        return psu_current

    @staticmethod
    def get_maximum_supplied_power():
        return 1500.0

    def get_power(self):
        """
        Retrieves current energy supplied by PSU
        Returns:
            A float number, the power in watts, e.g. 302.6
        """
        psu_pout_key = globals()['PSU{}_POUT_SS_ID'.format(self.index + 1)]
        status, raw_ss_read = self._api_helper.ipmi_raw(
            IPMI_SENSOR_NETFN, IPMI_SS_READ_CMD.format(psu_pout_key))
        ss_read = raw_ss_read.split()[SS_READ_OFFSET]
        # Formula: Rx6x10^0
        psu_power = int(ss_read, 16) * 6
        return float(psu_power)

    def get_powergood_status(self):
        """
        Retrieves the powergood status of PSU
        Returns:
            A boolean, True if PSU has stablized its output voltages and passed all
            its internal self-tests, False if not.
        """
        return self.get_status()

    def set_status_led(self, color):
        """
        Sets the state of the PSU status LED
        Args:
            color: A string representing the color with which to set the PSU status LED
                   Note: Only support green and off
        Returns:
            bool: True if status LED state is set successfully, False if not
        Note
            Set manual
            ipmitool raw 0x3a 0x42 0x2 0x00
        """
        led_cmd = {
            self.STATUS_LED_COLOR_GREEN: PSU_LED_GREEN_CMD,
            self.STATUS_LED_COLOR_AMBER: PSU_LED_AMBER_CMD,
            self.STATUS_LED_COLOR_OFF: PSU_LED_OFF_CMD
        }.get(color)
        status, set_led = self._api_helper.ipmi_raw(
            IPMI_OEM_NETFN, IPMI_SET_PSU_LED_CMD.format(led_cmd))
        return bool(status)

    def get_status_led(self):
        """
        Gets the state of the PSU status LED
        Returns:
            A string, one of the predefined STATUS_LED_COLOR_* strings above
        """
        status, hx_color = self._api_helper.ipmi_raw(
            IPMI_OEM_NETFN, IPMI_GET_PSU_LED_CMD)

        status_led = {
            "00": self.STATUS_LED_COLOR_OFF,
            "01": self.STATUS_LED_COLOR_GREEN,
            "02": self.STATUS_LED_COLOR_AMBER,
        }.get(hx_color, self.STATUS_LED_COLOR_OFF)

        return status_led

    def get_name(self):
        """
        Retrieves the name of the device
            Returns:
            string: The name of the device
        """
        return PSU_NAME_LIST[self.index]

    def run_command(self, command):
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
        (out, err) = proc.communicate()

        if proc.returncode != 0:
            sys.exit(proc.returncode)

        return out

    def find_value(self, in_string):
        result = re.search(r"^.+ ([0-9a-f]{2}) .+$", in_string)
        if result:
            return result.group(1)
        else:
            return result

    def get_presence(self):
        """
        Retrieves the presence of the PSU
        Returns:
            bool: True if PSU is present, False if not
        """
        if self.index is None:
            return False

        psu_id = self.psu1_id if self.index == 1 else self.psu2_id
        res_string = self.run_command(self.ipmi_raw + ' ' + psu_id)
        status_byte = self.find_value(res_string.decode())

        if status_byte is None:
            return False

        return (((int(status_byte, 16) >> 0 ) & 1) != 0)

    def get_status(self):
        """
        Retrieves the operational status of the device
        Returns:
            A boolean value, True if device is operating properly, False if not
        """
        if self.index is None:
            return False

        psu_id = self.psu1_id if self.index == 0 else self.psu2_id
        res_string = self.run_command(self.ipmi_raw + ' ' + psu_id)
        status_byte = self.find_value(res_string.decode())

        if status_byte is None:
            return False

        failure_detected = (((int(status_byte, 16) >> 1) & 1) != 0)
        input_lost = (((int(status_byte, 16) >> 3) & 1) != 0)
        return not (failure_detected or input_lost)

    def get_model(self):
        """
        Retrieves the model number (or part number) of the device
        Returns:
            string: Model/part number of device
            eg.ipmitool fru print 4
            Product Manufacturer  : DELTA
            Product Name          : DPS-1300AB-6 J
            Product Part Number   : DPS-1300AB-6 J
            Product Version       : S1F
            Product Serial        : JDMD2111000125
            Product Asset Tag     : S1F
        """
        model = "Unknown"
        ipmi_fru_idx = self.index + PSU1_FRU_ID
        status, raw_model = self._api_helper.ipmi_fru_id(
            ipmi_fru_idx, IPMI_FRU_MODEL_KEY)

        fru_pn_list = raw_model.decode().split()
        if len(fru_pn_list) > 3:
            model = fru_pn_list[3]

        return model

    def get_serial(self):
        """
        Retrieves the serial number of the device
        Returns:
            string: Serial number of device
        """
        serial = "Unknown"
        ipmi_fru_idx = self.index + PSU1_FRU_ID
        status, raw_model = self._api_helper.ipmi_fru_id(
            ipmi_fru_idx, IPMI_FRU_SERIAL_KEY)

        fru_sr_list = raw_model.decode().split()
        if len(fru_sr_list) > 3:
            serial = fru_sr_list[3]

        return serial
