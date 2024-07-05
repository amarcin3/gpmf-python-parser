#!/usr/bin/env python3

import struct
import math
import json

# https://github.com/gopro/gpmf-parser#gpmf-deeper-dive

# file name for the binary file extracted using ffmpeg
# ffprobe .\goproVideo.MP4
# find the stream with the metadata (gpmd, handler_name="GoPro MET"), usually 0:3
# ffmpeg -i .\goproVideo.MP4 -map 0:3 -c copy -f data goproMetadata.bin
# you will get a binary file with the metadata with the name typed above (goproMetadata.bin)

INPUT_FILE_NAME = 'out-0002.bin'
OUTPUT_FILE_NAME = 'output.json'

# JSON formatting options
MINIFY_JSON_NAMES = False  # change names in json to one letter names
INDENT_JSON = 0  # 0 for minified, 4 for pretty print (significantly bigger file - not recommended)
# 4 - 92,48 MB, 2 - 51,95 MB, 0 - 7,36 MB for an example 2,55 MB binary file (no minified names used)

# Console output options
PRINT_KEYS_TO_CONSOLE = False
PRINT_VALUES_TO_CONSOLE = False

# Global variables for parsing
hierarchy = []
python_json = []


def json_add_key(key_name, key_type, key_size, key_repeat):
    """Add a new key to the JSON structure."""
    global python_json, hierarchy
    key_info = {
        key_name: {
            "t" if MINIFY_JSON_NAMES else "Type": key_type,
            "s" if MINIFY_JSON_NAMES else "Size": key_size,
            "r" if MINIFY_JSON_NAMES else "Repeat": key_repeat,
            "v" if MINIFY_JSON_NAMES else "Values": []
        }
    }
    # Traverse hierarchy to find the correct place to insert the new key
    last_key = python_json
    if hierarchy:
        for key in hierarchy:
            last_key = [item for item in last_key if key[0] in item][-1][key[0]]["v" if MINIFY_JSON_NAMES else "Values"]
    last_key.append(key_info)
    hierarchy.append([key_name, key_type, key_size, key_repeat, key_size * key_repeat, math.ceil(key_size * key_repeat / 4) * 4])


def json_add_value(value):
    """Add a value to the most recent key in the hierarchy."""
    global python_json, hierarchy
    last_key = python_json
    for key in hierarchy:
        last_key = [item for item in last_key if key[0] in item][-1][key[0]]["v" if MINIFY_JSON_NAMES else "Values"]
    last_key.append(value)


def read_bytes(file, amount):
    """Read a specified number of bytes from the file and manage padding."""
    data = file.read(amount)
    for h in hierarchy:
        h[5] -= amount
        padding_bytes = math.ceil(h[4] / 4) * 4 - h[4]
        if h[5] == padding_bytes and padding_bytes != 0:
            read_bytes(file, padding_bytes)
    return data


def print_hierarchically(text):
    """Print text indented according to the hierarchy depth."""
    print('  ' * len(hierarchy), text)


def bytes_to_string(data, bytes_per_char=1):
    """Convert bytes to a string."""
    return ''.join(
        chr(int.from_bytes(data[i:i + bytes_per_char], byteorder="big")) for i in range(0, len(data), bytes_per_char))


def bytes_to_number(data, bytes_per_number, signed=False, dtype="int"):
    """Convert bytes to numbers."""
    if len(data) % bytes_per_number != 0:
        raise ValueError("Bytes length is not divisible by bytes_per_number")
    unpack_format = {
        "int": (lambda b: int.from_bytes(b, byteorder="big", signed=signed)),
        "float": (lambda b: struct.unpack(">f", b)[0]),
        "double": (lambda b: struct.unpack(">d", b)[0])
    }
    return [unpack_format[dtype](data[i:i + bytes_per_number]) for i in range(0, len(data), bytes_per_number)]


def handle_types(file):
    """
    Handle different types of data and add them to the JSON structure.
    https://github.com/gopro/gpmf-parser#type
    """
    type_code = hierarchy[-1][1]
    data = read_bytes(file, hierarchy[-1][2])
    if type_code == 'b':
        value = bytes_to_number(data, 1, signed=True)
    elif type_code == 'B':
        value = bytes_to_number(data, 1)
    elif type_code == 'c':
        value = bytes_to_string(data)
    elif type_code == 'd':
        value = bytes_to_number(data, 8, dtype="double")
    elif type_code == 'f':
        value = bytes_to_number(data, 4, dtype="float")
    elif type_code == 'j':
        value = bytes_to_number(data, 8, signed=True)
    elif type_code == 'J':
        value = bytes_to_number(data, 8)
    elif type_code == 'l':
        value = bytes_to_number(data, 4, signed=True)
    elif type_code == 'L':
        value = bytes_to_number(data, 4)
    elif type_code == 's':
        value = bytes_to_number(data, 2, signed=True)
    elif type_code == 'S':
        value = bytes_to_number(data, 2)
    elif type_code == 'U':
        time_str = bytes_to_string(data)
        value = f'{time_str[4:6]}.{time_str[2:4]}.20{time_str[0:2]} {time_str[6:8]}:{time_str[8:10]}:{time_str[10:12]}.{time_str[13:16]}'
    else:
        raise ValueError(f"Type '{type_code}' not implemented")  # F, G, q, Q, ?
    json_add_value(value if len(value) > 1 else value[0])
    if PRINT_VALUES_TO_CONSOLE:
        print_hierarchically(f'Value: {value}')
    hierarchy[:] = [h for h in hierarchy if h[5] != 0]


def main():
    print("Starting, opening file...")
    with open(INPUT_FILE_NAME, 'rb') as f:
        print("File opened, parsing...")
        while True:
            if not hierarchy or hierarchy[-1][1] == '0':
                key = read_bytes(f, 4).decode('ascii').rstrip('\0')
                type_code = read_bytes(f, 1)
                type_code = '0' if type_code == b'\x00' else type_code.decode('ascii')
                size = int.from_bytes(read_bytes(f, 1), byteorder='big')
                repeat = int.from_bytes(read_bytes(f, 2), byteorder='big')
                if size == 0 and repeat == 0:
                    break
                if PRINT_KEYS_TO_CONSOLE:
                    print_hierarchically(f'Key: {key}, Type: {type_code}, Size: {size}b, Repeat: {repeat}')
                json_add_key(key, type_code, size, repeat)
            else:
                handle_types(f)
        print("Parsed successfully, saving to json...")
        with open(OUTPUT_FILE_NAME, 'w') as json_file:
            json.dump(python_json, json_file, indent=INDENT_JSON if INDENT_JSON else None,
                      separators=(',', ':') if not INDENT_JSON else None)
        print("Saved successfully")


if __name__ == "__main__":
    main()
