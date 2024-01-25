"""
WIFF -- Waveform Interchange File Format

This is a combination of files that are similar to the generic EA IFF 85 chunk format (inspired AIFF, RIFF, PNG, JFIF, etc)
However, IFF is limited to 32-bit chunk lengths which is inadequate and this expands to 64-bit.

The same chunk format is used for a couple types of chunks:
	- Informative that contains information about the entire dataset ("recording")
	- Waveform files to permit slicing up ("segments") large datasets into multiple files
	- Annotation files to add markers at various frames in the files

Terminology
* A recording is the entirety of recorded data with a specified number of channels and specified number of frames of data
* A recording is broken into segments consisting of multiple frames
* A frame consists of samples across all present channels in a segment at a given point in time
* A channel is a specific binary data source of data that is piece-wise present (not present sample-by-sample, but over a continous time period)
* Frame index is the index into the frames from zero (start of recording) to N (last frame of the recording)
* An annotation is a marker associated to a frame or frames that gives meaning beyond the raw binary data; interpretive information

Assumptions
* Each channel has a fixed bit size and does not change throughout the recording
* Fixed number of total channels throughout the recording
* Sampling rate is fixed throughout the recording and across channels
* Segments can have different sets of active channels
* One segment per WIFFWAVE chunk, one WIFFWAVE chunk per segment
* Essentially no limit on duration of recording; entire recording can span any number of files
  effectively limited by the WIFFWAVE.ChunkID 32-bit unique ID and 64-bit size of chunks
* Annotations are supported that can mark a specific frame, or range of frames
"""

WIFF_VERSION = 2

from .wiff import WIFF
from .util import blob_builder, range2d, range3d

def open(fname):
	"""
	Open an existing WIFF file.
	"""
	return WIFF.open(fname)

def new(fname, props, force=False):
	"""
	@props -- dictionary including:
		'start'			datetime objects
		'end'			datetime objects
		'description'	string describing the recording
		'fs'			sampling frequency (int)
		'channels'		list of channels
			'idx'				channel index (zero based)
			'name'				name of the channel
			'bits'				bits (int) of each measurement
			'unit'				physical units of the measurement (str)
			'digitalminvalue'	Minimum digitized value
			'digitalmaxvalue'	Maximum digitized value
			'analogminvalue'	Minimum analog/physical value
			'analogmaxvalue'	Maximum analog/physical value
			'comment'			Arbitrary comment on the channel
		'files'			list of files, probably empty (except for INFO file) for a new recording
	"""

	w = WIFF.new(fname, props)
	return w

