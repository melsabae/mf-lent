import argparse
import itertools
import pathlib
import struct
import sys


import matplotlib
import matplotlib.pyplot
import numpy
import sigmf


# let's play the guessing game
for b in ["GTK3Cairo", "TkCairo", "gtk3cairo"]:
    try:
        matplotlib.use(b)
        break
    except Exception as e:
        print(e)


def content_slice(content, descriptor):
    assert len(descriptor) >= 2

    b, e = descriptor[:2]

    return memoryview(content[b : e + 1])


def dummy(b, params):
    return 0xDEADBEEF


def content_slice_indexed(content, idx, size):
    return content_slice(content, (idx * size, ((idx + 1) * size) - 1))


def unpack(cs, fmt, params):
    endianness = params["endianness"]
    _fmt = f"{endianness}{fmt}"

    return struct.unpack(_fmt, cs)[0]


def to_table3(b, params):
    assert len(b) == 4

    v = unpack(b, "i", params)

    # exponents jump by 3 orders of magnitude
    exponent = 3 * (v - 8)

    return 1 * (10**exponent)


def to_array(b, params, fmt, size, length):
    """
    given buffer b and params
    unpack it into an array of length length
    each item having the size of size
    and unpacked via the struct formatter fmt
    """

    # assert len(b) == size * length, f"{len(b)} != {size * length}"
    assert len(b) >= size * length, f"{len(b)} ! >= {size * length}"

    return list(
        map(
            lambda i: unpack(content_slice_indexed(b, i, size), fmt, params),
            range(length),
        )
    )


def to_vas(v, params):
    assert len(v) == 6

    v_pow_den = v[1]
    a_pow_den = v[3]
    s_pow_den = v[5]

    units = {
        "V": v[0] / v_pow_den if v_pow_den != 0 else 0.0,
        "A": v[2] / a_pow_den if a_pow_den != 0 else 0.0,
        "S": v[4] / s_pow_den if s_pow_den != 0 else 0.0,
    }

    return units


def to_table4(b, params):
    assert len(b) == 7 * 4

    # NOTE: they do not specify the type of these values, these were something that fit well enough
    # v = to_array(b, params, "f", 4, len(b) // 4)
    # v = to_array(b, params, "I", 4, len(b) // 4)
    v = to_array(b, params, "i", 4, len(b) // 4)
    # print(params["key"], v)

    match v[0]:
        case 0:
            return to_vas(v[1:], params)
        case 1:
            return "DBV"
        case 2:
            return "DBA"
        case 3:
            return "DB"
        case 4:
            return "VPP"
        case 5:
            return "VDC"
        case 6:
            return "SBM"
        case 7:
            return "SA"
        case 8:
            return "DT_DIV"
        case 9:
            return "PTS"
        case 10:
            return "NULL_SENSE"
        case 11:
            return "DEGREE"
        case 12:
            return "PERCENT"
        case _:
            assert False, "f{v} is not a valid unit mapping"


def to_table2(b, params):
    assert len(b) == 40, "length bad"

    value = unpack(content_slice(b, (0x0000, 0x0007)), "d", params)
    value_mag = to_table3(content_slice(b, (0x0008, 0x000B)), params)
    value_unit = to_table4(content_slice(b, (0x000C, 0x0027)), params)

    # NOTE/TODO: value_unit shows V, A, S, and the number for them is the exponent
    #            V: 2.0 means squared volts

    return (value, value_mag, value_unit)


def to_array_table2(b, params, length):
    # NOTE: v4 memory_hpos_val is an array of 4 Table2, each Table2 is 0x28 == 40 bytes long
    #       v4 memory_hpos_val is 192 bytes long for some reason
    # assert 40 * length == len(b), f"40 * {length} != {len(b)}"
    assert 40 * length <= len(b), f"40 * {length} ! <= {len(b)}"

    return list(
        map(
            lambda i: to_table2(content_slice_indexed(b, i, 0x28), params),
            range(length),
        )
    )


def v4_header(content, byte_order, endianness):
    table = {
        "data_offset_byte": (0x0004, 0x0007, "i"),
        "ch1_on": (0x0008, 0x000B, "i"),
        "ch2_on": (0x000C, 0x000F, "i"),
        "ch3_on": (0x0010, 0x0013, "i"),
        "ch4_on": (0x0014, 0x0017, "i"),
        "ch1_volt_div_val": (0x0018, 0x003F, to_table2),
        "ch2_volt_div_val": (0x0040, 0x0067, to_table2),
        "ch3_volt_div_val": (0x0068, 0x008F, to_table2),
        "ch4_volt_div_val": (0x0090, 0x00B7, to_table2),
        "ch1_vert_offset": (0x00B8, 0x00DF, to_table2),
        "ch2_vert_offset": (0x00E0, 0x0107, to_table2),
        "ch3_vert_offset": (0x0108, 0x012F, to_table2),
        "ch4_vert_offset": (0x0130, 0x0157, to_table2),
        "digital_on": (0x0158, 0x015B, "i"),
        "d0_d15_on": (0x015C, 0x019B, lambda b, p: to_array(b, p, "i", 4, 16)),
        "time_div": (0x019C, 0x01C3, to_table2),
        "time_delay": (0x01C4, 0x01EB, to_table2),
        "wave_length": (0x01EC, 0x01EF, "i"),
        "sample_rate": (0x01F0, 0x0217, to_table2),
        "digital_wave_length": (0x0218, 0x021B, "i"),
        "digital_sample_rate": (0x021C, 0x0243, to_table2),
        "ch1_probe": (0x0244, 0x024B, "d"),
        "ch2_probe": (0x024C, 0x0253, "d"),
        "ch3_probe": (0x0254, 0x025B, "d"),
        "ch4_probe": (0x025C, 0x0263, "d"),
        "data_width": (0x0264, 0x0264, "B"),
        "_?1": (0x0266, 0x026B, dummy),
        "Hori_div_num": (0x026C, 0x026F, "i"),
        "ch1_vert_code_per_div": (0x0270, 0x0273, "i"),
        "ch2_vert_code_per_div": (0x0274, 0x0277, "i"),
        "ch3_vert_code_per_div": (0x0278, 0x027B, "i"),
        "ch4_vert_code_per_div": (0x027C, 0x027F, "i"),
        "math1_switch": (0x0280, 0x0283, "i"),
        "math2_switch": (0x0284, 0x0287, "i"),
        "math3_switch": (0x0288, 0x028B, "i"),
        "math4_switch": (0x028C, 0x028F, "i"),
        "math1_vdiv_val": (0x0290, 0x02B7, to_table2),
        "math2_vdiv_val": (0x02B8, 0x02DF, to_table2),
        "math3_vdiv_val": (0x02E0, 0x0307, to_table2),
        "math4_vdiv_val": (0x0308, 0x032F, to_table2),
        "math1_vpos_val": (0x0330, 0x0357, to_table2),
        "math2_vpos_val": (0x0358, 0x037F, to_table2),
        "math3_vpos_val": (0x0380, 0x03A7, to_table2),
        "math4_vpos_val": (0x03A8, 0x03CF, to_table2),
        "math1_store_len": (0x03D0, 0x03D3, "i"),
        "math2_store_len": (0x03D4, 0x03D7, "i"),
        "math3_store_len": (0x03D8, 0x03DB, "i"),
        "math4_store_len": (0x03DC, 0x03DF, "i"),
        "math1_f_time": (0x03E0, 0x03E7, "d"),
        "math2_f_time": (0x03E8, 0x03EF, "d"),
        "math3_f_time": (0x03F0, 0x03F7, "d"),
        "math4_f_time": (0x03F8, 0x03FF, "d"),
        "math_vert_code_per_div": (0x0400, 0x0403, "i"),
        "ch5_on": (0x0404, 0x0407, "i"),
        "ch6_on": (0x0408, 0x040B, "i"),
        "ch7_on": (0x040C, 0x040F, "i"),
        "ch8_on": (0x0410, 0x0413, "i"),
        "ch5_volt_div_val": (0x0414, 0x043B, to_table2),
        "ch6_volt_div_val": (0x043C, 0x0463, to_table2),
        "ch7_volt_div_val": (0x0464, 0x048B, to_table2),
        "ch8_volt_div_val": (0x048C, 0x04B3, to_table2),
        "ch5_vert_offset": (0x04B4, 0x04DB, to_table2),
        "ch6_vert_offset": (0x04DC, 0x0503, to_table2),
        "ch7_vert_offset": (0x0504, 0x052B, to_table2),
        "ch8_vert_offset": (0x052C, 0x0553, to_table2),
        "ch5_probe": (0x0554, 0x055B, "d"),
        "ch6_probe": (0x055C, 0x0563, "d"),
        "ch7_probe": (0x0564, 0x056B, "d"),
        "ch8_probe": (0x056C, 0x0573, "d"),
        "ch5_vert_code_per_div": (0x0574, 0x0577, "i"),
        "ch6_vert_code_per_div": (0x0578, 0x057B, "i"),
        "ch7_vert_code_per_div": (0x057C, 0x057F, "i"),
        "ch8_vert_code_per_div": (0x0580, 0x0583, "i"),
        "ch_insert": (0x0584, 0x05A3, lambda b, p: to_array(b, p, "i", 4, 8)),
        "math_insert": (0x05A4, 0x05B3, lambda b, p: to_array(b, p, "i", 4, 4)),
        "digital_insert": (0x05B4, 0x05F3, lambda b, p: to_array(b, p, "i", 4, 16)),
        "ch_move": (0x05F4, 0x0613, lambda b, p: to_array(b, p, "i", 4, 8)),
        "math_move": (0x0614, 0x0623, lambda b, p: to_array(b, p, "i", 4, 4)),
        "digital_move": (0x0624, 0x0663, lambda b, p: to_array(b, p, "i", 4, 16)),
        "memory_switch": (0x0664, 0x0673, lambda b, p: to_array(b, p, "i", 4, 4)),
        "memory_wave_format": (0x0674, 0x067B, lambda b, p: to_array(b, p, "H", 2, 4)),
        "_?2": (0x067C, 0x0683, dummy),
        "memory_vdiv_val": (0x0684, 0x0723, lambda b, p: to_array_table2(b, p, 4)),
        "memory_vpos_val": (0x0724, 0x07C3, lambda b, p: to_array_table2(b, p, 4)),
        "_?3": (0x07C4, 0x0903, dummy),
        "memory_hdiv_val": (0x0904, 0x09A3, lambda b, p: to_array_table2(b, p, 4)),
        "memory_hpos_val": (0x09A4, 0x0A63, lambda b, p: to_array_table2(b, p, 4)),
        "memory_store_len": (0x0A64, 0x0A73, lambda b, p: to_array(b, p, "i", 4, 4)),
        "memory_f_time": (0x0A74, 0x0A93, lambda b, p: to_array(b, p, "d", 8, 4)),
        "memory_vert_code_per_div": (
            0x0A94,
            0x0AA3,
            lambda b, p: to_array(b, p, "i", 4, 4),
        ),
        "memory_insert": (0x0AA4, 0x0AB3, lambda b, p: to_array(b, p, "i", 4, 4)),
        "memory_move": (0x0AB4, 0x0AC3, lambda b, p: to_array(b, p, "i", 4, 4)),
        "memory_probe_fval": (0x0AC4, 0x0AF3, lambda b, p: to_array(b, p, "d", 8, 4)),
        "zoom_switch": (0x0AF4, 0x0AF7, "i"),
        "zoom_td_val": (0x0AF8, 0x0B1F, to_table2),
        "zoom_trig_delay_val": (0x0B20, 0x0B47, to_table2),
        "zoom_vdiv_val": (0x0B48, 0x0C87, lambda b, p: to_array_table2(b, p, 8)),
        "zoom_vpos_val": (0x0C88, 0x0DC7, lambda b, p: to_array_table2(b, p, 8)),
        "_?reserved": (0x0DC8, 0x07FF, dummy),
    }

    ret = {"version": 4, "byte_order": byte_order, "endianness": endianness}
    params = {"endianness": endianness}

    for k, tup in table.items():
        b = content_slice(content, tup)
        params["key"] = k

        if type("") is type(tup[-1]):
            value = unpack(b, tup[-1], params)
        else:
            value = tup[-1](b, params)

        ret[k] = value

    return ret


def read(content, header):
    # NOTE: the specific oscope im using has 12 bit ADCs, so im assuming that the output values are signed
    #       im also assuming the output values are sign extended too

    # NOTE: the data conversion code provided by SIGLENT is not clear why it does what it does
    #       it subtract the "center code" which works out to be the sign bit for whatever data width
    #           f.e. 128 for 8-bit values, 32768 for 16-bit values
    #       which makes me think the values are stored in unsigned format
    data_width = header["data_width"]

    match data_width:
        case 0:
            base_dt = numpy.uint8
        case 1:
            base_dt = numpy.uint16
        case _:
            assert (
                False
            ), f"{data_width} is not 0 nor 1, you must have a $$$$ oscilloscope with $$$ ADCs"

    dt = numpy.dtype(base_dt).newbyteorder(header["endianness"])
    data = numpy.frombuffer(content, dtype=dt, offset=header["data_offset_byte"])
    return data.astype(numpy.dtype("i"))


def convert(d, center, volt_div, code_per_div, vert_offset):
    return (((d - center) * volt_div) / code_per_div) - vert_offset


def calculate_time(num_points, time_div, grid, time_delay, sample_rate):
    return (
        -(time_div * (grid / 2.0))
        - time_delay
        + numpy.arange(num_points) * (1.0 / sample_rate)
    )


def v4_channel(content, header, ch_key):
    # either 7 or 15, which is the bit number of the sign bit for 8/16 bit values
    data_width = 7 + (8 * header["data_width"])
    # this is the sign bit for the data
    center_code = 1 << data_width

    ch_volt_div = header[f"{ch_key}_volt_div_val"]
    ch_vert_offset = header[f"{ch_key}_vert_offset"]
    code_per_div = header[f"{ch_key}_vert_code_per_div"]

    ch_volt_div_val = ch_volt_div[0]
    ch_vert_offset_val = ch_vert_offset[0]

    data = read(content, header)

    # time isn't used in sigmf
    time = []
    #time = calculate_time(
    #    len(data),
    #    header["time_div"][0],
    #    header["Hori_div_num"],
    #    header["time_delay"][0],
    #    header["sample_rate"][0],
    #)
    data = convert(data, center_code, ch_volt_div_val, code_per_div, ch_vert_offset_val)

    return data, time


def v4_math(content, header, ch_key):
    # either 7 or 15, which is the bit number of the sign bit for 8/16 bit values
    data_width = 7 + (8 * header["data_width"])
    # this is the sign bit for the data
    center_code = 1 << data_width

    # there is no explicit "vert_code_per_div" for math channels but i assume is's just a hardcoded number
    # in the metadata anyway
    # also this wouldn't handle 2 or more digits for channel numbers
    ch_num = ch_key[-1]

    ch_volt_div = header[f"{ch_key}_vdiv_val"]
    ch_vert_offset = header[f"{ch_key}_vpos_val"]
    code_per_div = header[f"ch{ch_num}_vert_code_per_div"]
    ch_volt_div_val = ch_volt_div[0]
    ch_vert_offset_val = ch_vert_offset[0]

    data = read(content, header)

    # time isn't used in sigmf
    time = []
    #time = calculate_time(
    #    len(data),
    #    header["time_div"][0],
    #    header["Hori_div_num"],
    #    header["time_delay"][0],
    #    header["sample_rate"][0],
    #)
    data = convert(data, center_code, ch_volt_div_val, code_per_div, ch_vert_offset_val)

    return data, time


def v4_digital(content, header, ch_key):
    return ([], [])


def v4(header, content, source, channel_num):
    ch = f"{source}{channel_num}"

    table = {
        "ch": (f"{ch}_on", v4_channel),
        "math": (f"{ch}_switch", v4_math),
        "d": ("d0_d15_on", v4_digital),
    }

    if source not in table:
        assert False, f"{source} is not a valid v4 source"

    key, func = table[source]

    if source in ["ch", "math"]:
        enabled = key in header and bool(header[key])
    else:
        # TODO: digital is untested
        enabled = all(
            [
                "digital_on" in header,
                bool(header["digital_on"]),
                "d0_d15_on" in header,
                bool(header["d0_d15_on"][channel_num]),
            ]
        )

    if not enabled:
        return [], []

    return func(content, header, ch)


def get_header(content):
    params = {"endianness": "<"}
    version = unpack(content_slice(content, (0, 4 - 1)), "i", params)
    byte_order = 0

    # TODO: i only happen to use v4 for now
    #       i happen to know that in v4, the version is the first 4 bytes, and it's little endian
    #       just in case i happen to use other versions later, im leaving this note here
    #       the upcoming logic does not assume endianness of your machine or the file, so it checks both
    #       in short:
    #           parsing the version needs to know the endianness, and sort of also needs to know the version
    #           to find and parse the endianness, we need to know the version
    #           great job SIGLENT /sarcasm

    match version:
        case 0x04 | 0x04000000:
            # happens to be a single byte, so "B" doesn't care about the endianness
            byte_order = unpack(content_slice(content, (0x0265, 0x0265)), "B", params)

            # it's possible that parsing this is version dependent too
            endianness = "<" if byte_order == 0 else ">"

            return v4_header(content, byte_order, endianness)
        case _:
            assert False, f"version {version} parsing not implemented"

    return version, byte_order, endianness


def check_input_headers(args):
    # check that the headers for each input channel file agrees on some things

    channel_headers = list(map(get_header, args["ch"]))
    math_headers = list(map(get_header, args["math"]))
    digital_headers = list(map(get_header, args["d"]))
    disagreements = []
    first_header = channel_headers[0]

    for i, other in enumerate(channel_headers[1:], start=1):
        for k in ["version", "byte_order", "endianness", "wave_length", "data_width"]:
            if first_header[k] != other[k]:
                disagreements.append(
                    f"0[{k}] = {first_header[k]}, does not match {i}[{k}] = {other[k]}"
                )

    # TODO: sanity check the math/digital headers too

    return disagreements, channel_headers, math_headers, digital_headers


def parse(args, channel_headers, math_headers, digital_headers):
    f = None
    ret = {}
    version = channel_headers[0]["version"]

    match version:
        case 4:
            f = v4
        case _:
            assert False, f"{version} parsing not supported"

    # channel/math numbers are 1-indexed, digital is 0-indexed
    for i, c in enumerate(args["ch"]):
        data, time = f(channel_headers[i], c, "ch", i + 1)
        ret[f"ch{i + 1}"] = (channel_headers[i], data, time)

    for i, c in enumerate(args["math"]):
        dat, time = f(math_headers[i], c, "math", i + 1)
        ret[f"math{i + 1}"] = (math_headers[i], data, time)

    for i, c in enumerate(args["d"]):
        data, time = f(digital_headers[i], c, "d", i)
        ret[f"d{i}"] = (digital_headers[i], data, time)

    return ret


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("output_file", type=argparse.FileType(mode="w"))

    parser.add_argument(
        "--analog",
        dest="ch",
        type=argparse.FileType(mode="rb"),
        nargs="+",
        help="input binary file(s) for analog channels",
        default=[],
    )
    parser.add_argument(
        "--math",
        dest="math",
        type=argparse.FileType(mode="rb"),
        nargs="+",
        help="input binary file(s) for math functions",
        default=[],
    )
    parser.add_argument(
        "--digital",
        dest="d",
        type=argparse.FileType(mode="rb"),
        nargs="+",
        help="input binary file(s) for digital channels",
        default=[],
    )

    args = dict(
        filter(lambda kv: kv[1] is not None, parser.parse_args().__dict__.items())
    )

    if 0 == len(args["ch"]) + len(args["math"]) + len(args["d"]):
        print("no files to process")
        exit(0)

    for i, c in enumerate(args["ch"]):
        args["ch"][i] = c.read()

    for i, c in enumerate(args["math"]):
        args["math"][i] = c.read()

    for i, c in enumerate(args["d"]):
        args["d"][i] = c.read()

    disagreements, channel_headers, math_headers, digital_headers = check_input_headers(
        args
    )

    for (k, v) in channel_headers[0].items():
        print(k, v, type(v))

    if len(disagreements) > 0:
        print(f"headers don't agree on {disagreements}", file=sys.stderr)
        exit(-1)

    data = parse(args, channel_headers, math_headers, digital_headers)

    # obtain output paths
    output_file = pathlib.Path(args["output_file"].name)
    output_dir = output_file.parents[0]
    output_file = output_file.stem
    data_file = output_dir.joinpath(f"{output_file}.sigmf-data").absolute()
    meta_file = output_dir.joinpath(f"{output_file}.sigmf-meta").absolute()

    # don't assume the keys are sorted
    key_list = sorted(data.keys())
    offsets = dict(zip(key_list, itertools.repeat(0)))

    # calculate the binary file offsets per key in the keylist
    for (i, k) in enumerate(key_list[1:], start=1):
        prior_key = key_list[i - 1]
        offsets[k] = offsets[prior_key] + len(data[prior_key][1])

    # enforce output values are f32
    output_dtype = numpy.dtype("f")

    # create output .sigmf-data file
    with open(data_file, "wb") as f:
        for i, key in enumerate(key_list):
            f.write(data[key][1].astype(output_dtype).tobytes())

    # set up metadata for .sigmf-meta
    version = channel_headers[0]["version"]

    # this is almost certainly the same for all analog/math channels
    sample_rate = channel_headers[0]["sample_rate"][0]
    recorder = f"SIGLENT v{version}"
    hardware = "SIGLENT SDS804X HD, firmware version unspecified"

    # sample rates may vary between analog/math and digital
    # since i dont have the digital module, im going to assume for now it runs at the same sample rate
    # in other words, if i sample 1 channel at 2 GS/s, then digital is also 2GS/s for all 16 channels
    # this is likely a very not good assumption
    global_info = {
        sigmf.SigMFFile.DATATYPE_KEY: sigmf.utils.get_data_type_str(
            numpy.array([], dtype=output_dtype)
        ),
        sigmf.SigMFFile.RECORDER_KEY: recorder,
        sigmf.SigMFFile.START_OFFSET_KEY: 0,
        # each captured channel is a separate capture in the output file
        # in other words, they are NOT interleaved
        sigmf.SigMFFile.NUM_CHANNELS_KEY: 1,
        sigmf.SigMFFile.HW_KEY: hardware,
        sigmf.SigMFFile.SAMPLE_RATE_KEY: sample_rate
    }

    meta = sigmf.SigMFFile(data_file=data_file, global_info=global_info)

    for i, key in enumerate(key_list):
        metadata = {}

        annotation = {
            sigmf.SigMFFile.LABEL_KEY: key,
        }

        meta.add_capture(offsets[key], metadata = metadata)
        meta.add_annotation(offsets[key], len(data[key][1]), metadata = annotation)

    meta.tofile(meta_file)

    fig, ax = matplotlib.pyplot.subplots()

    for k, v in data.items():
        print(k, len(v[1]), v[0]["data_width"])
        print(v[1])
        print()

        ax.plot(v[1], label=k)

    legend = ax.legend(loc="lower right")
    matplotlib.pyplot.show()

