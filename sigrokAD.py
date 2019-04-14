import struct, sys, zipfile, re as regex
from optparse import OptionParser
from os.path import exists, getsize, basename
from os import remove, rename
from tempfile import TemporaryDirectory
from glob import glob
from configparser import ConfigParser

version = "0.1 alpha"
description = """
This python script parses the analog voltages from a sigrok *.sr session file,
compares them to a threshold and outputs a new *.sr file containing a logic 0/1
file representing the analog values as binary values.
This is useful if you are trying to decode protocols in sigrok, but you only
have an oscilloscope without a logic analyzer.
"""

oparse = OptionParser(usage="usage: %prog [options] <input file.sr> <output file.sr>", version=version, description=description)
# parse.add_option("-i","--input",dest="src_file",help="Input sigrok session filename (*.sr)")
# oparse.add_option("-o","--output",dest="dst_file",help="Output sigrok session filename (*.sr)")
oparse.add_option("-t", "--threshold", dest="threshold", help="Threshold (volts) for 1 (above threshold) or 0 (below threshold)")

opts, args = oparse.parse_args(sys.argv[1:])

try:
    src_file = args[0]
    dst_file = args[1]
except:
    oparse.print_help()
    sys.exit(1)

if not exists(src_file):
    print("ERROR! Source file does not exist!", file=sys.stderr)
    sys.exit(1)
if not zipfile.is_zipfile(src_file):
    print("ERROR! Source file is not in ZIP file format!", file=sys.stderr)
    sys.exit(1)
if exists(dst_file):
    print("WARN! Destination file exists and will be overwritten!", file=sys.stderr)

##################################################################################################
# Unzip

tempDir = TemporaryDirectory()
sr_file = zipfile.ZipFile(src_file, "r")
print("Unzipping " + src_file + " into " + tempDir.name)
sr_file.extractall(path=tempDir.name)
sr_file.close()

##################################################################################################
# read matafile

metafile = ConfigParser()
metafile.read(tempDir.name + "/metadata")
metafile.remove_section("global")
devices = metafile.sections()

##################################################################################################

for device in devices:
    r = regex.search('device ([0-9]+)', device)
    device_number = r.group(1)
    if not metafile.getint(device, "total analog", fallback=0) > 0:
        print("ERROR! Source file does not contain any analog data!", file=sys.stderr)
        sys.exit(1)

    unitsize = 1
    metafile.set(device, "unitsize", str(unitsize))
    #if not unitsize > 0:
    #    print("ERROR! Source file does not contain unitsize!", file=sys.stderr)
    #    sys.exit(1)

    analog_channels = list(opt for opt in metafile.options(device) if opt.startswith("analog"))
    analog_channel_numbers = map(lambda n: n[6:], analog_channels)
    analog_channel_count = len(analog_channels)

    for f in glob(tempDir.name + "/logic-*"):
        remove(f)
    open(tempDir.name + "/logic-" + device_number, "ab").close()

    metafile.set(device, "capturefile", "logic-" + device_number)
    with open(tempDir.name + "/logic-" + device_number, "r+b") as logic_file:
        for chan_number in analog_channel_numbers:
            logic_file.seek(0)
            analog_channel_count += 1
            analog_files = sorted(glob(tempDir.name + "/analog-" + device_number + "-" + chan_number + "-*"))
            file_cnt = 0
            for analog_filename in analog_files:
                file_cnt += 1
                print("Reading " + analog_filename)
                analog_file_size = getsize(analog_filename)
                with open(analog_filename, "rb") as analog_file:
                    bin_analog = analog_file.read(4)
                    while bin_analog:
                        try:
                            bin_logic = int(logic_file.read(unitsize))
                        except:
                            bin_logic = 0
                        volts = struct.unpack('f', bin_analog)[0]
                        if volts > float(opts.threshold):
                            bin_logic |= 1 << (int(chan_number) - 1)
                        if logic_file.tell() > 0:
                            logic_file.seek(unitsize * -1, 1)
                        logic_file.write(bytes([bin_logic]))
                        logic_file.seek(unitsize * 2, 1)
                        bin_analog = analog_file.read(4)
                        # print(str(analog_file.tell()*100/analog_file_size)+"\r",end="")
                rename(analog_filename, tempDir.name + "/analog-" + device_number + "-" + str(analog_channel_count) + "-" + str(file_cnt))
            metafile.remove_option(device, "analog"+chan_number)
            metafile.set(device, "probe" + str(analog_channel_count - len(analog_channels)), "D" + str(analog_channel_count - len(analog_channels)))
            metafile.set(device, "analog" + str(analog_channel_count), "A" + str(analog_channel_count - len(analog_channels)))

    metafile.set(device, "total probes", str(len(analog_channels)))
    metafile.set(device, "total analog", str(len(analog_channels)))

print("Writing metadata")

metafile.add_section("global")
metafile.set("global", "sigrok version", "0.5.0")

with open(tempDir.name + "/metadata", "w") as metadata_file:
    metafile.write(metadata_file)

print("Zipping " + tempDir.name + " into " + dst_file)

with zipfile.ZipFile(dst_file, "w",compression=zipfile.ZIP_DEFLATED) as sr_file:
    for f in glob(tempDir.name + "/*"):
        sr_file.write(f,basename(f))

print("Done.")
