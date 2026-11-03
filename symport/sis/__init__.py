"""Native SIS 9.x (SISX) reader/writer.

The layout follows the working reference implementation in
https://github.com/hpnkv/symbian-platform (cpp/symbian/sis/sis.cc, Apache-2.0), generalised to
arbitrary installed files. The writer is EXPERIMENTAL: its output is structurally checked by
``symport.sis.reader`` but has NOT been accepted by Symbian's own MakeSIS/SignSIS or by a phone.
"""
