import argparse
import sys


from packaging.version import Version as v


import mflent.sds800x


# the intent here is to map a user's model and firmware version to the specific parser
# but i dont have enough sample files to even test this
# so here you go: TODO
compat = {
        "SDS100X":     [v("0")],
        "SDS200X":     [v("0")],
        "SDS1xx2X-E":  [v("0"), v("1.3.20")],
        "SDS1xx4X-E":  [v("0")],
        "SDS2000X-E":  [v("0")],
        "SDS5000X":    [v("0")],
        "SDS2000X+":   [v("0")],
        "SDS6000X":    [v("0")],
        "SDS800X-HD":  [v("0")],
        "SDS1000X-HD": [v("0")],
        "SDS2000X-HD": [v("0")],
        "SDS4000X-HD": [v("0")],
        "SDS7000":     [v("0")],
}


#def setup_v0_parser(parser):
#    parser.add_argument("--test", type=str)
#
#def setup_v01_parser(parser):
#    parser.add_argument("--test", type=str)
#
#def setup_v02_parser(parser):
#    parser.add_argument("--test", type=str)
#
#def setup_v1_parser(parser):
#    parser.add_argument("--test", type=str)
#
#def setup_v2_parser(parser):
#    parser.add_argument("--test", type=str)


import argparse
import itertools
import pathlib
import struct
import sys


import numpy
import sigmf


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
            assert False, f"{v} is not a valid unit mapping"


def to_table2(b, params):
    assert len(b) == 4, "length bad"

    val = unpack(b, "i", params)

    if val == 0 and params["model"] == "SDS1000X":
        assert False, "SDS1000X does not support T/div value 0"

    # seconds per division
    match val:
        case 0:  return 1E-9
        case 1:  return 2E-9
        case 2:  return 5E-9
        case 3:  return 10E-9
        case 4:  return 20E-9
        case 5:  return 50E-9
        case 6:  return 100E-9
        case 7:  return 200E-9
        case 8:  return 500E-9
        case 9:  return 1E-6
        case 10: return 2E-6
        case 11: return 5E-6
        case 12: return 10E-6
        case 13: return 20E-6
        case 14: return 50E-6
        case 15: return 100E-6
        case 16: return 200E-6
        case 17: return 500E-6
        case 18: return 1E-3
        case 19: return 2E-3
        case 20: return 5E-3
        case 21: return 10E-3
        case 22: return 20E-3
        case 23: return 50E-3
        case 24: return 100E-3
        case 25: return 200E-3
        case 26: return 500E-3
        case 27: return 1
        case 28: return 2
        case 29: return 5
        case 30: return 10
        case 31: return 20
        case 32: return 50
        case _:
            assert False, f"v0 does not support table 2 value {b}"

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


def v0_headers(args, content):
    table = {
        "wave_length": (0x0000, 0x0003, dummy),
        "mso_wave_length": (0x0004, 0x0007, "i"),

        "_?1": (0x0009, 0x0009, dummy),

        "mso_ch_open_num": (0x0010, 0x0013, "I"),
        "mso_ch_open_stats": (0x0014, 0x0023, lambda b, p: to_array(b, p, "B", 1, 16)),

        "_?2": (0x0024, 0x00bb, dummy),

        "ch1_volt_div_val": (0x00bc, 0x00bf, to_table2),
        "ch2_volt_div_val": (0x00c0, 0x00c3, to_table2),
        "ch3_volt_div_val": (0x00c4, 0x00c7, to_table2),
        "ch4_volt_div_val": (0x00c8, 0x00cb, to_table2),

        "_?3": (0x00cc, 0x00db, dummy),

        "ch1_vert_offset": (0x00dc, 0x00df, "i"),
        "ch2_vert_offset": (0x00e0, 0x00e3, "i"),
        "ch3_vert_offset": (0x00e4, 0x00e7, "i"),
        "ch4_vert_offset": (0x00e8, 0x00eb, "i"),

        "_?4": (0x00ec, 0x00ff, dummy),

        "ch1_on": (0x0100, 0x0103, "i"),
        "ch2_on": (0x0104, 0x0107, "i"),
        "ch3_on": (0x0108, 0x010b, "i"),
        "ch4_on": (0x010c, 0x010f, "i"),

        "time_div": (0x0248, 0x024b, "i"),
        "time_delay": (0x0250, 0x0253, "i"),

        #"_?reserved": (0x0DC8, 0x07FF, dummy),
    }

    endianness = "<"
    byte_order = 0
    ret = {"version": 0, "byte_order": byte_order, "endianness": endianness}
    params = {"endianness": endianness, "model": args["model"]}

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
    return data.astype(numpy.dtype("int32"))


def convert(d, center, volt_div, code_per_div, vert_offset, probe_attenuation):
    # attempt to consolidate constants to reduce the number of calculations on the numpy array
    return ((probe_attenuation * volt_div / code_per_div) * (d - center)) - (
        probe_attenuation * vert_offset
    )

    # original formula
    # return ((((d - center) * volt_div) / code_per_div) - vert_offset) * probe_attenuation


def v4_channel(content, header, ch_key):
    # either 7 or 15, which is the bit number of the sign bit for 8/16 bit values
    data_width = 7 + (8 * header["data_width"])
    # this is the sign bit for the data
    center_code = 1 << data_width

    ch_volt_div = header[f"{ch_key}_volt_div_val"]
    ch_vert_offset = header[f"{ch_key}_vert_offset"]
    code_per_div = header[f"{ch_key}_vert_code_per_div"]
    probe_attenuation = header[f"{ch_key}_probe"]

    ch_volt_div_val = ch_volt_div[0]
    ch_vert_offset_val = ch_vert_offset[0]

    data = read(content, header)

    return convert(
        data,
        center_code,
        ch_volt_div_val,
        code_per_div,
        ch_vert_offset_val,
        probe_attenuation,
    )


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

    return convert(
        data, center_code, ch_volt_div_val, code_per_div, ch_vert_offset_val, 1.0
    )


def v4_digital(content, header, ch_key):
    return numpy.ndarray((0))


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
        return numpy.ndarray((0))

    return func(content, header, ch)


def check_input_headers(args):
    # check that the headers for each input channel file agrees on some things

    return list(map(lambda ch: v0_headers(args, ch), args["ch"]))


def parse(args, channel_headers, math_headers, digital_headers):
    f = None
    ret = {}

    if len(channel_headers) > 0:
        header = channel_headers[0]
    elif len(math_headers) > 0:
        header = math_headers[0]
    elif len(digital_headers) > 0:
        header = digital_headers[0]
    else:
        assert False, "no headers available"

    version = header["version"]
    sample_rate = header["sample_rate"][0]

    match version:
        case 4:
            f = v4
        case _:
            assert False, f"{version} parsing not supported"

    # channel/math numbers are 1-indexed, digital is 0-indexed
    for i, c in enumerate(args["ch"]):
        data = f(channel_headers[i], c, "ch", i + 1)
        ret[f"ch{i + 1}"] = (channel_headers[i], data)

    for i, c in enumerate(args["math"]):
        data = f(math_headers[i], c, "math", i + 1)
        ret[f"math{i + 1}"] = (math_headers[i], data)

    for i, c in enumerate(args["d"]):
        data = f(digital_headers[i], c, "d", i)
        ret[f"d{i}"] = (digital_headers[i], data)

    return version, sample_rate, ret


def sigmf_file(name, mode):
    path = pathlib.Path(name)
    suffix = path.suffix

    # the text of the exception doesn't seem to get propagated sadly
    if suffix not in [".sigmf-meta", ".sigmf-data"]:
        raise ValueError(f"{name} does not end in .sigmf-meta nor .sigmf-data")

    return open(path.absolute(), mode="w")


def sigmf_output_file(s):
    return sigmf_file(s, "wb")


def main(args):
    if 0 == len(args["ch"]) + len(args["math"]) + len(args["d"]):
        print("no files to process")
        exit(0)

    for i, c in enumerate(args["ch"]):
        args["ch"][i] = c.read()

    for i, c in enumerate(args["math"]):
        args["math"][i] = c.read()

    for i, c in enumerate(args["d"]):
        args["d"][i] = c.read()

    headers = check_input_headers(args)

    for (k, v) in headers[0].items():
        print(k, v)
    exit(0)

    version, sample_rate, data = parse(
        args, channel_headers, math_headers, digital_headers
    )

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
    for i, k in enumerate(key_list[1:], start=1):
        prior_key = key_list[i - 1]
        offsets[k] = offsets[prior_key] + len(data[prior_key][1])

    output_dtype = to_numpy_dtype(args["output_dtype"])

    # create output .sigmf-data file
    with open(data_file, "wb") as f:
        for i, key in enumerate(key_list):
            f.write(data[key][1].astype(output_dtype).tobytes())

    oscope_model = args["oscope_model"]
    fw_version = args["firmware"]
    recorder = f"SIGLENT v{version}"
    hardware = f"SIGLENT model {oscope_model}, firmware {fw_version}"
    extension_key = "siglent-headers"

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
        sigmf.SigMFFile.SAMPLE_RATE_KEY: sample_rate,
        sigmf.SigMFFile.EXTENSIONS_KEY: [
            {"name": extension_key, "version": "0.0.1", "optional": True}
        ],
    }

    meta = sigmf.SigMFFile(data_file=data_file, global_info=global_info)

    for i, key in enumerate(key_list):
        metadata = {f"{extension_key}:{version}:{key}": data[key][0]}

        annotation = {
            sigmf.SigMFFile.LABEL_KEY: key,
        }

        meta.add_capture(offsets[key], metadata=metadata)
        meta.add_annotation(offsets[key], len(data[key][1]), metadata=annotation)

    # i might prefer archives, but you still have to manually create the data file first
    # sigmf.archive.SigMFArchive(meta, name = "asdf.sigmf")
    meta.tofile(meta_file)

    if args["plot_capture"]:
        plot_capture_as_type(data, output_dtype)


def cli():
    #parser = argparse.ArgumentParser()

    #subparsers = parser.add_subparsers(dest="version")

    #v0_parser = subparsers.add_parser("v0", help="operate on v0 files")
    #v01_parser = subparsers.add_parser("v0.1", help="operate on v0.1 files")
    #v02_parser = subparsers.add_parser("v0.2", help="operate on v0.2 files")
    #v1_parser = subparsers.add_parser("v1.0", help="operate on v1.0 files")
    #v2_parser = subparsers.add_parser("v2+", help="operate on v2+ files")

    #setup_v0_parser(v0_parser)
    #setup_v4_parser(v4_parser)

    #parser.add_argument("model", type=str, choices=[
    #    "SDS100X", "SDS2000X", "SDS1xx2X-E", "SDS1xx4X-E", "SDS1xx2X-E", "SDS1xx4X-e"
    #])
    #parser.add_argument("output_file", type=str, help="the output sigmf file to generate")

    #args = parser.parse_args().__dict__
    #args = { "ch": [ open(sys.argv[1], "rb") ], "math": [], "d": []}

    # TODO: i dont have a 2000X-E capture
    #args["model"] = "SDS1000X-E"

    #main(args)

    return mflent.sds800x.cli()

