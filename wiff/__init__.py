"""
WIFF -- Waveform Interchange File Format

This is a combination of files that are similar to the generic EA IFF 85 chunk format.
However, IFF is limited to 32-bit chunk lengths which is inadequate.

The same chunk format is used for a couple types of files:
	- Informative that contains information about the entire dataset
	- Waveform files to permit slicing up large datasets into multiple files
	- Annotation files to add markers at various frames in the files

Terminology
* A recording is the entirety of recorded data with a specified number of channels and specified number of frames of data
* A frame consists of samples across all present channels at a given point in time
* A channel is a specific binary data source of data that is piece-wise present (not present sample-by-sample, but over a continous time period)
* Time index is the index into the frames from zero (start of recording) to N (last frame of the recording)
* An annotation is a marker associated to a frame or frames that gives meaning beyond the raw binary data; interpretive information

Assumptions
* Each channel has a fixed bit size and does not change throughout the recording
* Fixed number of channels throughout the recording
* Sampling rate is fixed throughout the recording and across channels
* Not all channels are required to be recorded at a given time, but different WIFFWAVE chunks are needed
  at boundaries where channel presence changes
* Essentially no limit on duration of recording; entire recording can span any number of files
  effectively limited by the WIFFWAVE.ChunkID 32-bit unique ID and 64-bit size of chunks
* Max 255 channels supported (8-bit index) but not unreasonable to support 16-bit indices
* Annotations are supported that can mark a specific frame, or range of frames


WIFF chunk format
	Offset	Length	Contents
	0		8		Chunk ID in ASCII characters
	8		8		Size of chunk not including the header
	16		8		Attribute flags unique to each chunk that can be used as needed
					Could be 32 one-bit flags, or 8 unsigned bytes, or whatever
					Regardless, all chunks have these 8 attribute bytes.
	24		N		Binary data
	Zero padding bytes to make entire chunk to be a multiple of 8

Chunks
	WIFFINFO -- Information
	Attributes
		[0] -- Version of WIFF
		[1-7] -- Reserved

	Info chunk that is used to coordinate high-level information.

	Data
		[0:1] -- Byte index of start time string
		[2:3] -- Byte index of end time string
		[4:5] -- Byte index of description
		[6:7] -- Byte index of channel definitions start (X)
		[8:9] -- Byte index of channel definitions end (Y)
		[10:11] -- 16-bit sampling rate in samples per second
		[12:13] -- Number of channels (max 256 supported)
		[14:15] -- Byte index of start of channel information
		[16:X-1] -- Start of string data for above
		[X:Y] -- Start of channel definitions as non-padded sequences of the definition below

		Thus, the indices of the strings' start and end can be calculated and the total size of the data block determined without having to parse actual content data (total size is in [8:9]). Strings are NOT null terminated.


	Channel definition:
		[0:1] -- Byte index of name of channel string
		[2] -- Size of samples in bits (actual storage space are upper-bit padded full bytes)
		[3:4] -- Byte index of physical units string
		[5:6] -- Byte index of comments string start
		[7:8] -- Byte index of comments string end (X)
		[9:X] -- Strings

		Channel definitions are in sequance right after each other, and so [X+1] marks the start of the next channel definition (if not the last channel).


	WIFFWAVE -- Waveform data
	Attributes
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2
		[1] -- Reserved
		[2] -- Reserved
		[3] -- Reserved
		[4:7] -- 32 bit chunk ID references in WIFFINFO to order the chunks
				 Chunk ID's need not be in numerical order, only unique within the same WIFF data set.

	If compression is used, the entire data block, except padding bytes, are decompressed first.

	Data
		[0:7] -- Bitfield identifying which channels are present from 0 to 255
		[8:15] -- First frame index
		[16:23] -- Last frame index
		[24:X] -- Frames




	WIFFANNO -- Annotations
		[0] -- First byte is an ASCII character indicating compression used
			0			No compression
			Z			zlib
			B			bzip2

	If compression is used, the entire data block, except padding bytes, are decompressed first.

	Annotations



"""

import os.path

import funpack

from .compress import WIFFCompress


class WIFF:
	def __init__(self, fname):
		# f is the WAVEINFO file
		self.f = None

		# List of files containing WIFFWAVE chunks
		self.files = []

		if os.path.exists(fname):
			self._open_read(fname)
		else:
			self._open_new(fname)

	def __enter__(self):
		return self

	def __exit__(self, *exc):
		self.close()
		return False

	def close(self):
		""" Close """
		pass

	def _open_read(self, fname):
		self.f = open(fname, '+b')

	def _open_new(self, fname):
		self.f = open(fname, 'wb')

class _WIFF_file:
	"""
	Contains information about a specific file.
	Reads the chunks and indexes them, and collects pertinent information about them.
	"""

	def __init__(self, fname):
		self.fname = fname
		with open(fname, 'rb') as f:
			header = f.read(24)

		fup = funpack.funpack(header, endian=funpack.Endianness.Big)
		self.magic = fup.string_ascii(4)
		self.length = fup.u64()
		self.attrs = fup.u8(8)
		self.file_size = os.path.getsize(fname)

class _WIFFINFO_file:
	def __init__(self, f):
		self.f = f

		with open(self.f.fname, 'rb') as f:
			header = f.read(8*8)

			fup = funpack.funpack(header, endian=funpack.Endianness.Big)

