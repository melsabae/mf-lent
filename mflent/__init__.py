import argparse


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

    #print(args)

    return mflent.sds800x.cli()

