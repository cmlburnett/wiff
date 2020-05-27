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
* Max 255 channels supported (8-bit index) but not unreasonable to support 16-bit indices
* Annotations are supported that can mark a specific frame, or range of frames


WIFF chunk format
	Offset	Length	Contents
	0		8		Chunk ID in ASCII characters
	8		8		Size of chunk including the header
	16		8		Attribute flags unique to each chunk that can be used as needed
					Could be 32 one-bit flags, or 8 unsigned bytes, or whatever
					Regardless, all chunks have these 8 attribute bytes.
	24		N		Binary data
	Zero padding bytes to make entire chunk to be a multiple of 8

Chunks
	It is encouraged to put chunk boundaries on 4096 byte blocks
	This permits modifying a file in place without having to rewrite the entire file for small edits.
	If streaming to the end of a chunk then this matters less.

	Chunks can be sequential in the same file, or can be split into different files.
	How chunks are organized is up to the caller.
	It is possible to use one file for information, waveform, and annotations.

	All byte indices used within are relative and are 16-bit values.
	Should an index overflow, then a new segment will be needed.
	Thus, if a chunk in its entirety is shifting within a file then no updates are needed
	 to a chunk to keep it consistent.

	Strings are not null-terminated.


	WIFFINFO -- Information
	Attributes
		[0] -- Version of WIFF
		[1-7] -- Reserved

	Info chunk that is used to coordinate high-level information and the organization of the recording.

	Data
		[0:1] -- Byte index of start time string
		[2:3] -- Byte index of end time string
		[4:5] -- Byte index of description
		[6:7] -- Byte index of channel definitions (X)
		[8:9] -- Byte index of files start (Y)
		[10:11] -- Byte index of files end (Z)
		[12:15] -- 32-bit sampling rate in samples per second
		[16:17] -- Number of channels (max 256 supported)
		[18:19] -- Number of files
		[20:27] -- Number of frames
		[28:35] -- Number of annotations
		[36:X-1] -- Start of string data for above
		[X:Y-1] -- Start of channel definitions as non-padded sequences of the definition below
		[Y:Z] -- Start of file definitions as non-padded sequences of the definition below

		Indices of strings are sequential.
		For example, the end time string index is the ending offset of the start time string.


	Channel definition:
		The channel definitions section starts with a jump table of byte indices for the specified number of channels. Each entry in the jump table is 4 bytes long with a 2-byte start and end index for each channel. Total size is thus 4*number of channels.

		[0:1] -- Byte index of start of channel definition #0
		[2:3] -- Byte index of end of channel definition #0
		[4:5] -- Byte index of start of channel definition #1
		[6:7] -- Byte index of end of channel definition #1
		[8:9] -- Byte index of start of channel definition #2
		...

		Each channel then consists of:
		[0] -- Index of channel
		[1:2] -- Byte index of name of channel string
		[3] -- Size of samples in bits (actual storage space are upper-bit padded full bytes)
		[4:5] -- Byte index of physical units string
		[6:7] -- Byte index of comments string start
		[8:9] -- Byte index of comments string end (X)
		[10:X] -- Strings

		Channel definitions are in sequance right after each other, and so [X+1] marks the start of the next channel definition (if not the last channel).

	File definitions:
		[0:1] -- Byte index of start of file #0
		[2:3] -- Byte inoex of end of file #0
		[4:5] -- Byte index of start of file #1
		[6:7] -- Byte inoex of end of file #1
		[8:9] -- Byte index of start of file #2
		...

		Each file then consists of:
		[0] -- Index of file
		[1:2] -- Byte index of file name string start
		[3:4] -- Byte index of file name string end (X)
		[5:12] -- Start frame index
		[13:20] -- End frame index
		[21:28] -- Start annotation index
		[29:36] -- End annotation index
		[36:X] -- File name string


	WIFFWAVE -- Waveform data
	Attributes
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2
		[1] -- Reserved
		[2] -- Reserved
		[3] -- Reserved
		[4:7] -- 32 bit segment ID references in WIFFINFO to order the chunks
				 Chunk ID's need not be in numerical order, only unique within the same WIFF data set.
				 Putting segment ID in attributes avoids having to decompress data first.

	Data
		[0:31] -- Bitfield identifying which channels are present from 0 to 255
		[32:39] -- First frame index
		[40:47] -- Last frame index
		[48:X] -- Frames

	The 256 channel limitation is due to the bitfield here.
	Supporting 256 channels only requires 32 bytes of space, but supporting 65k channels would require 8kb just for a bitfield.
	As this seemed excessive for my current needs, I opted against it and stuck with 8-bit (256 channels).



	WIFFANNO -- Annotations
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2

	Annotations
		[0:7] -- First annotation index
		[8:15] -- Last annotation index
		[16:23] -- First frame index referenced
		[24:31] -- Last frame index referenced
		[32:35] -- Number of annotations
		[36:X-1] -- Annotation jump table
		[X:Y] -- Annotation definitions

	The first and last frame indices are meant to aid in speeding up searching for annotations matching annotations to a frame index. Without this, all annotation sections would have to be searched.

	Annotations have different types with variable content each.
	Markers are character codes that apply to a single frame or a range of frames.
	Comments are freetext of variable length that add commentary to a single frame or a range of frames.

	Markers are intended to identify repeating types in the data (eg, with ECG the beat type or the frame range of the QRS complex). Comments are meant to be typed in by a user to signify something unusual not easily achieved by the marker type and may be out-of-band information (eg, manual blood pressure reading when recording ECG, medication administration).

	Annotation
		[0] -- Annotation type
		[1:8] -- Frame index start
		[9:15] -- Frame index end
		[16:X] -- Annotation data

	Annotation: comment ('C')
		[0]='C' -- Commentannotation
		[1:8] -- Frame index start
		[9:15] -- Frame index end
		[16:18] -- Comment start byte index
		[19:20] -- Comment end byte index
		[21:X] -- Comment

	Annotation: marker ('M')
		[0]='M' -- Marker annotation
		[1:8] -- Frame index start
		[9:15] -- Frame index end
		[16:19] -- 4 character marker

	Annotation: marker with data ('D')
		[0]='D' -- Data marker annotation
		[1:8] -- Frame index start
		[9:15] -- Frame index end
		[16:19] -- 4 character marker
		[20:27] -- 8 byte data value associated with the marker

All data is read/written using mmap without intermediate/buffered data in this library.
Doing this avoids issues of consistency as all modifications are written directly to the files
 and paging is handled by the OS.
It is encouraged to cache values locally in the code calling this module to avoid repeatedly parsing the same binary data.
This is intended because it is the caller that knows best what information is being re-used and where optimization
 can be done to minimize file operations.

Parsing of the files is done with a custom struct module called bstruct.
Each binary structure is defined as a separate class and the grunt work of packing and unpacking these binary
 structures is done in the background.
Keeping track of offsets within the file is tedious, and this layering makes handling offsets a breeze.
"""

WIFF_VERSION = 1

from .wiff import WIFF


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
			'name'			name of the channel
			'bit'			bits (int) of each measurement
			'unit'			physical units of the measurement (str)
			'comment'		Arbitrary comment on the channel
		'files'			list of files, probably empty (except for INFO file) for a new recording
	"""
	return WIFF.new(fname, props, force)

