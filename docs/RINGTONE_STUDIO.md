# Ringtone Studio

Upload MP3, M4A, MP4, WAV, FLAC, OGG/WebM, AIFF or another allowed audio container,
or choose **Create ringtone** on an audio/video item in Media Gallery. FFmpeg must
be installed in the Linux backend; the Docker image includes it. There are no
external audio services or CDN requests.

WaveSurfer.js 8.0.5 and its Regions plugin are shipped locally under BSD-3-Clause.
Drag/resize the region, set exact start/end times, zoom and loop the selection.
Ringtone preset: 30 seconds / MP3 mono / 128 kbps / 44.1 kHz. Notification:
5 seconds / MP3 mono / 96 kbps / 44.1 kHz. All values remain editable.

The editor uses a 16 kHz mono WAV preview to keep browser memory bounded. Export
always processes the **original** input with your chosen sample rate/channels,
optional two-pass LUFS normalization and fades. The output player and download
serve the exact processed MP3. Changing settings invalidates the old export.
Silent material remains silent; a LUFS target cannot make silence audible. Fades
can lower the final integrated loudness after normalization.

**Send to Nokia** uses DeviceManager media-upload with explicit confirmation.
Mounted volumes receive a new MP3 without overwrite; OBEX FTP stages/read-checks;
OPP reports receiver acknowledgement only and sends to inbox. Assign the tone in
phone settings. No unsupported operation is claimed as ringtone assignment.

Limits: input 64 MiB / 10 minutes, output selection 0.1–180 seconds, three open
sources, two simultaneous processing operations. Every FFprobe/FFmpeg process has
a wall timeout (20/80 seconds), 85 CPU seconds, 1 GiB address space, 64 MiB output
file limit and bounded diagnostics. FFmpeg uses two codec threads and one filter
thread. A normalization export can use two bounded passes plus metadata probing.
Arguments are validated numeric/enum values; subprocess never invokes a shell.
Only selected local demuxers and file/pipe protocols are enabled; playlists, network
URLs and user-supplied FFmpeg filter expressions are not accepted.

Inputs, preview and latest export live in private temporary folders. Close source
removes them immediately. They expire after one hour; a background janitor runs
every minute and startup removes old sessions. At most three bounded input/preview/
output sets are retained. Do not treat temporary exports as backups: download MP3
before closing or updating the container. Audio is never placed in operation logs.
