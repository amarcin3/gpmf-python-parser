#!/usr/bin/env python3

import json

INPUT_FILE_NAME = 'output.json'
OUTPUT_FILE_NAME = 'output_streams.json'


def load_json(file_name):
    try:
        with open(file_name, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File {file_name} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: File {file_name} is not a valid JSON.")
        return None


def is_minified(json_data):
    return bool(json_data and json_data[0]["DEVC"].get('t'))


def extract_streams(json_data, minified_names):
    streams = []
    for device in json_data:
        values_key = "v" if minified_names else "Values"
        for entry in device["DEVC"][values_key]:
            if "STRM" in entry:
                stream_data = entry["STRM"][values_key]
                stream_name = list(stream_data[-1].keys())[0]
                if not any(stream_name in stream for stream in streams):
                    name, unit = extract_stream_metadata(stream_data, minified_names)
                    streams.append([stream_name, name, 0, unit])
                else:
                    increment_stream_count(streams, stream_name)
    return streams


def extract_stream_metadata(stream_data, minified_names):
    name = ''
    unit = ''
    for item in stream_data:
        if "STNM" in item:
            name = ''.join(item["STNM"]["v" if minified_names else "Values"]).rstrip('\x00')
        elif "SIUN" in item:
            unit = ''.join(item["SIUN"]["v" if minified_names else "Values"]).rstrip('\x00')
        elif "UNIT" in item:
            unit_values = item["UNIT"]["v" if minified_names else "Values"]
            unit = ', '.join(value.rstrip('\x00') for value in unit_values)
    return name, unit


def increment_stream_count(streams, stream_name):
    for stream in streams:
        if stream[0] == stream_name:
            stream[2] += 1


def display_streams(streams):
    for stream in streams:
        unit_info = f", Unit/s: {stream[3]}" if stream[3] else ""
        print(f'Name: {stream[0]}, Number of seconds recorded: {stream[2]}{unit_info}, Description: {stream[1]}')


def get_user_selected_stream(streams):
    while True:
        selected_stream_name = input("Which stream do you want to export? ").strip()
        if not selected_stream_name:
            continue
        for stream in streams:
            if stream[0] == selected_stream_name:
                return stream
        print("Stream not found.")


def create_output_json(stream, json_data, minified_names):
    output_json = {
        "name": stream[0],
        "description": stream[1],
        "seconds_recorded": stream[2],
        "unit": stream[3],
        "data": {}
    }

    keys = extract_keys_and_data(output_json, json_data, stream[0], minified_names)
    fill_stream_data(output_json, json_data, keys, stream[0], minified_names)
    return output_json


def extract_keys_and_data(output_json, json_data, stream_name, minified_names):
    keys = []
    for device in json_data:
        values_key = "v" if minified_names else "Values"
        for entry in device["DEVC"][values_key]:
            if "STRM" in entry and stream_name in entry["STRM"][values_key][-1]:
                stream_data = entry["STRM"][values_key]
                if not keys:
                    for data in stream_data:
                        key = list(data.keys())[0]
                        if key not in ["STNM", "SIUN", "UNIT"]:
                            keys.append(key)
                        if key not in ["STNM", "SIUN", "UNIT", "SCAL"]:
                            output_json["data"][key] = []
    return keys


def fill_stream_data(output_json, json_data, keys, stream_name, minified_names):
    scales = None
    for device in json_data:
        values_key = "v" if minified_names else "Values"
        for entry in device["DEVC"][values_key]:
            if "STRM" in entry and stream_name in entry["STRM"][values_key][-1]:
                stream_data = entry["STRM"][values_key]
                if scales is None:
                    for data in stream_data:
                        if "SCAL" in data:
                            scales = data["SCAL"]["v" if minified_names else "Values"]
                            break
                for data in stream_data:
                    key = list(data.keys())[0]
                    if key not in ["SCAL", "STNM", "SIUN", "UNIT"]:
                        if key == stream_name and scales:
                            output_json["data"][stream_name].append(
                                scale_values(data[stream_name]["v" if minified_names else "Values"], scales)
                            )
                        else:
                            output_json["data"][key].append(data[key]["v" if minified_names else "Values"])


def scale_values(values, scales):
    scaled_values = []
    for entry in values:
        scaled_values.append([])
        for i, value in enumerate(entry):
            scaled_values[-1].append(round(value / scales[i % len(scales)], 6))
    return scaled_values


def save_json(file_name, data):
    with open(file_name, 'w') as file:
        json.dump(data, file, separators=(',', ':'))


def main():
    json_data = load_json(INPUT_FILE_NAME)
    if json_data is None:
        return

    minified_names = is_minified(json_data)
    streams = extract_streams(json_data, minified_names)

    if not streams:
        print("No data in the JSON file.")
        return

    display_streams(streams)
    selected_stream = get_user_selected_stream(streams)
    output_json = create_output_json(selected_stream, json_data, minified_names)
    save_json(OUTPUT_FILE_NAME, output_json)
    print(f"Data for stream {selected_stream[0]} has been exported to {OUTPUT_FILE_NAME}.")


if __name__ == "__main__":
    main()
