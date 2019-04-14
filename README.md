# sigrokAD
Analog/Digital converter script for sigrok *.sr files

This python script parses the analog voltages from a sigrok *.sr session file,
compares them to a threshold and outputs a new *.sr file containing a logic 0/1
file representing the analog values as binary values.
This is useful if you are trying to decode protocols in sigrok, but you only
have an oscilloscope without a logic analyzer.
