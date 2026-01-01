#import argparse
#import sys


#from packaging.version import Version as v


import mflent.sds800x


# the intent here is to map a user's model and firmware version to the specific parser
# but i dont have enough sample files to even test this
# so here you go: TODO
#compat = {
#    "SDS100X": [v("0")],
#    "SDS200X": [v("0")],
#    "SDS1xx2X-E": [v("0"), v("1.3.20")],
#    "SDS1xx4X-E": [v("0")],
#    "SDS2000X-E": [v("0")],
#    "SDS5000X": [v("0")],
#    "SDS2000X+": [v("0")],
#    "SDS6000X": [v("0")],
#    "SDS800X-HD": [v("0")],
#    "SDS1000X-HD": [v("0")],
#    "SDS2000X-HD": [v("0")],
#    "SDS4000X-HD": [v("0")],
#    "SDS7000": [v("0")],
#}


# def setup_v0_parser(parser):
#    parser.add_argument("--test", type=str)
#
# def setup_v01_parser(parser):
#    parser.add_argument("--test", type=str)
#
# def setup_v02_parser(parser):
#    parser.add_argument("--test", type=str)
#
# def setup_v1_parser(parser):
#    parser.add_argument("--test", type=str)
#
# def setup_v2_parser(parser):
#    parser.add_argument("--test", type=str)


#def to_table2(b, params):
#    assert len(b) == 4, "length bad"
#
#    val = unpack(b, "i", params)
#
#    if val == 0 and params["model"] == "SDS1000X":
#        assert False, "SDS1000X does not support T/div value 0"
#
#    # seconds per division
#    match val:
#        case 0:
#            return 1e-9
#        case 1:
#            return 2e-9
#        case 2:
#            return 5e-9
#        case 3:
#            return 10e-9
#        case 4:
#            return 20e-9
#        case 5:
#            return 50e-9
#        case 6:
#            return 100e-9
#        case 7:
#            return 200e-9
#        case 8:
#            return 500e-9
#        case 9:
#            return 1e-6
#        case 10:
#            return 2e-6
#        case 11:
#            return 5e-6
#        case 12:
#            return 10e-6
#        case 13:
#            return 20e-6
#        case 14:
#            return 50e-6
#        case 15:
#            return 100e-6
#        case 16:
#            return 200e-6
#        case 17:
#            return 500e-6
#        case 18:
#            return 1e-3
#        case 19:
#            return 2e-3
#        case 20:
#            return 5e-3
#        case 21:
#            return 10e-3
#        case 22:
#            return 20e-3
#        case 23:
#            return 50e-3
#        case 24:
#            return 100e-3
#        case 25:
#            return 200e-3
#        case 26:
#            return 500e-3
#        case 27:
#            return 1
#        case 28:
#            return 2
#        case 29:
#            return 5
#        case 30:
#            return 10
#        case 31:
#            return 20
#        case 32:
#            return 50
#        case _:
#            assert False, f"v0 does not support table 2 value {b}"
#
#    value = unpack(content_slice(b, (0x0000, 0x0007)), "d", params)
#    value_mag = to_table3(content_slice(b, (0x0008, 0x000B)), params)
#    value_unit = to_table4(content_slice(b, (0x000C, 0x0027)), params)
#
#    # NOTE/TODO: value_unit shows V, A, S, and the number for them is the exponent
#    #            V: 2.0 means squared volts
#
#    return (value, value_mag, value_unit)
#
#
#def v0_headers(args, content):
#    table = {
#        "wave_length": (0x0000, 0x0003, dummy),
#        "mso_wave_length": (0x0004, 0x0007, "i"),
#        "_?1": (0x0009, 0x0009, dummy),
#        "mso_ch_open_num": (0x0010, 0x0013, "I"),
#        "mso_ch_open_stats": (0x0014, 0x0023, lambda b, p: to_array(b, p, "B", 1, 16)),
#        "_?2": (0x0024, 0x00BB, dummy),
#        "ch1_volt_div_val": (0x00BC, 0x00BF, to_table2),
#        "ch2_volt_div_val": (0x00C0, 0x00C3, to_table2),
#        "ch3_volt_div_val": (0x00C4, 0x00C7, to_table2),
#        "ch4_volt_div_val": (0x00C8, 0x00CB, to_table2),
#        "_?3": (0x00CC, 0x00DB, dummy),
#        "ch1_vert_offset": (0x00DC, 0x00DF, "i"),
#        "ch2_vert_offset": (0x00E0, 0x00E3, "i"),
#        "ch3_vert_offset": (0x00E4, 0x00E7, "i"),
#        "ch4_vert_offset": (0x00E8, 0x00EB, "i"),
#        "_?4": (0x00EC, 0x00FF, dummy),
#        "ch1_on": (0x0100, 0x0103, "i"),
#        "ch2_on": (0x0104, 0x0107, "i"),
#        "ch3_on": (0x0108, 0x010B, "i"),
#        "ch4_on": (0x010C, 0x010F, "i"),
#        "time_div": (0x0248, 0x024B, "i"),
#        "time_delay": (0x0250, 0x0253, "i"),
#        # "_?reserved": (0x0DC8, 0x07FF, dummy),
#    }
#
#    endianness = "<"
#    byte_order = 0
#    ret = {"version": 0, "byte_order": byte_order, "endianness": endianness}
#    params = {"endianness": endianness, "model": args["model"]}
#
#    for k, tup in table.items():
#        b = content_slice(content, tup)
#        params["key"] = k
#
#        if type("") is type(tup[-1]):
#            value = unpack(b, tup[-1], params)
#        else:
#            value = tup[-1](b, params)
#
#        ret[k] = value
#
#    return ret


def cli():
    return mflent.sds800x.cli()

