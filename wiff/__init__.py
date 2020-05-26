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

import datetime
import json
import mmap
import os
import os.path
import sys
import struct
import types

import bstruct

from .bits import bitfield
from .compress import WIFFCompress
from .structs import chunk_struct, info_struct, channel_struct, file_struct, wave_struct
from .structs import annos_struct, ann_struct, ann_C_struct, ann_D_struct, ann_M_struct

DATE_FMT = "%Y%m%d %H%M%S.%f"
WIFF_VERSION = 1

def twotuplecheck(x):
	"""Coerce a two-tuple of integers into an interval"""
	if isinstance(x, tuple):
		if len(x) == 2 and isinstance(x[0], int) and isinstance(x[1], int):
			return bstruct.interval(*x)
		else:
			raise ValueError("Tuple is not 2 integers")
	elif isinstance(x, bstruct.interval):
		return x
	else:
		raise TypeError("Not a 2-tuple or an interval")

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

class WIFF:
	"""
	Primary interface class to a WIFF recording.
	All interactions should occur through this class.
	Supply the primary WIFF file that contains the information for the recording
	If creating a new file, properties in @props is needed to start the recording.

	"""
	def __init__(self):
		"""
		Create a empty WIFF object.
		Call open() or new() to open an existing WIFF file or to create a new one, respectively.
		This is not meant to be called directly.
		"""

		self._files = {}
		self._chunks = {}

		self._current_file = None
		self._current_segment = None
		self._current_annotations = None

	@classmethod
	def open(cls, fname):
		"""
		Open an existing WIFF file.
		"""
		w = cls()

		# Blank all files
		w._fname = fname
		w._files.clear()
		w._chunks.clear()
		w._chunks[fname] = []

		# Wrap file
		f = w._files[fname] = _filewrap(fname)

		chunks = WIFF_chunk.FindChunks(f.f)
		for chunk in chunks:
			c = WIFF_chunk(f, chunk['offset header'])
			if chunk['magic'] == 'WIFFINFO':
				wi = WIFFINFO(w, f, c)
				w._chunks[fname].append(wi)

				if 'INFO' in w._chunks:
					raise NotImplementedError("Multiple WAVEINFO chunks is not supported")
				w._chunks['INFO'] = wi
			elif chunk['magic'] == 'WIFFWAVE':
				ww = WIFFWAVE(w, f, c)
				ww.setup()
				w._chunks[fname].append(ww)
			elif chunk['magic'] == 'WIFFANNO':
				wa = WIFFANNO(self, f, c)
				w._chunks[fname].append(wa)

			else:
				raise TypeError('Uknown chunk magic: %s' % chunk['magic'])

		return w

	@classmethod
	def new(cls, fname, props, force):
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

		if os.path.exists(fname):
			if not force:
				raise Exception("File '%s' exists, cannot open; pass force=True to override" % fname)

			# Have to open it to find all the files linked with it to completely delete it
			files = None
			try:
				w = cls.open(fname)
				files = [f.name.val for f in w.files]
				w.close()
			except Exception as e:
				pass

			if files is None:
				# Likely this isn't a WIFF file so delete just it
				os.unlink(fname)
			else:
				# Unlink all files, if they are present
				for f in files:
					if os.path.exists(f):
						os.unlink(f)

		# Make a shell object
		w = cls()

		# Blank all files
		w._fname = fname
		w._chunks[fname] = []

		# Wrap file
		f = w._files[fname] = _filewrap(fname)
		# Initial 4096 block
		f.resize(4096)

		c = WIFF_chunk(f, 0)

		# No frames yet
		num_frames = 0

		props['files'].append({
			'name': fname,
			'fidx_start': 0,
			'fidx_end': 0,
			'aidx_start': 0,
			'aidx_end': 0,
		})

		c = WIFF_chunk(f, 0)
		wi = WIFFINFO(w, f, c)
		wi.initchunk()
		wi.initheader(props['start'], props['end'], props['description'], props['fs'], 0,0, props['channels'], props['files'])


		w._chunks[fname] = [wi]
		w._chunks['INFO'] = wi

		return w

	@property
	def fs(self): return self._chunks['INFO'].fs
	@fs.setter
	def fs(self, v): self._chunks['INFO'].fs = v

	@property
	def start(self): return self._chunks['INFO'].start
	@start.setter
	def start(self, v): self._chunks['INFO'].start = v

	@property
	def end(self): return self._chunks['INFO'].end
	@end.setter
	def end(self, v): self._chunks['INFO'].end = v

	@property
	def description(self): return self._chunks['INFO'].description
	@description.setter
	def description(self, v): self._chunks['INFO'].description = v

	@property
	def num_channels(self): return self._chunks['INFO'].num_channels
	@num_channels.setter
	def num_channels(self, v): self._chunks['INFO'].num_channels = v

	@property
	def num_files(self): return self._chunks['INFO'].num_files
	@num_files.setter
	def num_files(self, v): self._chunks['INFO'].num_files = v

	@property
	def num_frames(self): return self._chunks['INFO'].num_frames
	@num_frames.setter
	def num_frames(self, v): self._chunks['INFO'].num_frames = v

	@property
	def num_annotations(self): return self._chunks['INFO'].num_annotations
	@num_annotations.setter
	def num_annotations(self, v): self._chunks['INFO'].num_annotations = v

	@property
	def channels(self): return self._chunks['INFO'].channels

	@property
	def files(self): return self._chunks['INFO'].files

	@property
	def current_segment(self): return self._current_segment

	def __enter__(self):
		pass
	def __exit__(self, *exc):
		self.close()
		return False

	def close(self):
		for fname,o in self._files.items():
			o.close()

	# Get all matching chunks
	def _GetINFO(self): return self._GetChunks('WIFFINFO')
	def _GetWAVE(self): return self._GetChunks('WIFFWAVE')
	def _GetANNO(self): return self._GetChunks('WIFFANNO')
	def _GetChunks(self, magic=None):
		"""
		Find all matching chunks for the magic (WIFFINFO, WIFFWAVE, WIFFANNO) or
		use a _GetINFO, _GetWAVE, _GetANNO.
		"""
		if magic == 'WIFFINFO':
			yield self._chunks['INFO']
		else:
			# Iterate over all files
			for fname in self._chunks.keys():
				if fname == 'INFO': continue

				# Iterate over the chunks in each file
				chunks = self._chunks[fname]
				for chunk in chunks:
					# Compare magic
					if magic is None:
						yield chunk
					elif chunk.magic == magic:
						yield chunk

	def get_annotations(self, typ=None, fidx=None):
		"""
		Get all annotations that match all supplied arguments.
		@typ -- Type of the annotation must match exactly
		@fidx -- Frame index must be between the start and stop indices of the annotation

		These options can take the appropriate type (string, int, etc).
		Alternatively, the value can be a function whose value is evaluated as a boolean.
		"""

		# Create filter functions based on arguments
		filts = []
		if typ is not None:
			if isinstance(typ, str):
				filts.append(lambda x: x.type.val == typ)
			elif isinstance(typ, types.FunctionType):
				filts.append(typ)
			else:
				raise TypeError('Unrecognize type for @typ argument (expect str or function): "%s"' % (str(typ),))

		if fidx is not None:
			if isinstance(fidx, int):
				filts.append(lambda x,fidx=fidx: x.fidx_start.val <= fidx and x.fidx_end.val >= fidx)
			elif isinstance(fidx, types.FunctionType):
				filts.append(fidx)
			elif isinstance(fidx, bstruct.interval):
				filts.append(lambda x, fidx=fidx: x.fidx_start.val in fidx or x.fidx_end.val in fidx)
			else:
				raise TypeError('Unrecognize type for @fidx argument (expect int or function): "%s"' % (str(fidx),))

		# If no filters provided as arguments, accept everything
		if not len(filts):
			filts.append(lambda x:True)

		# Iterate over all annotation chunks
		chunks = self._GetANNO()
		for annos in chunks:
			# Iterate over all annotations
			for ann in annos.annotations:
				# Apply filters and accept if all are True
				if all([_(ann) for _ in filts]):
					yield ann

	def get_frames(self, val, to_int=True):
		ret = {
			'start': None,
			'stop': None,
			'frames': None,
		}
		if isinstance(val, bstruct.interval):
			ret['start'] = val.start
			ret['stop'] = val.stop
			ret['interval'] = val
		elif isinstance(val, tuple):
			val = twotuplecheck(val)
			ret['start'] = val.start
			ret['stop'] = val.stop
			ret['interval'] = val
		else:
			raise TypeError("Unrecognized val type: %s" % (type(val),))

		ret['frames'] = list(self.iter_frames(val, to_int=to_int))
		ret['stop'] = ret['start'] + len(ret['frames']) - 1

		return ret

	def get_frame(self, index, to_int=True):
		"""
		Get a single frame of data as bytes (@to_int == False) or integers (@to_int == True).
		Not very efficient for repeated use.
		"""
		chunks = self._GetWAVE()
		for chunk in chunks:
			if chunk.fidx_start > index:
				continue
			if chunk.fidx_end < index:
				continue

			# index is in this chunk
			off = index - chunk.fidx_start

			if to_int:
				bs = chunk[off]
				return chunk.DeSer(bs)
			else:
				return chunk[off]

		raise KeyError("Frame index %d not found" % index)

	def iter_frames(self, val, to_int=True):
		"""
		Gets frames in sequence from @val frame indices.
		Get frames of data as bytes (@to_int == False) or integers (@to_int == True).
		"""

		# Get chunks and sort by start
		chunks = self._GetWAVE()
		chunks = sorted(chunks, key=lambda x:x.fidx_start)

		val = twotuplecheck(val)

		i = val.start

		for chunk in chunks:
			# Skip to first chunk
			if chunk.fidx_start > i:
				continue

			while i < chunk.fidx_end:
				# Get relative offset in the chunk and get frame
				off = i - chunk.fidx_start
				bs = chunk[off]

				if to_int:
					yield chunk.DeSer(bs)
				else:
					yield bs

				i += 1
				if i > val.stop:
					raise StopIteration


	# -----------------------------------------------
	# -----------------------------------------------
	# Add data

	def set_file(self, fname):
		"""
		Change the current segment
		"""
		self._current_file = self._files[fname]
		self._current_segment = None

		return self._current_file

	def set_segment(self, segment):
		"""
		Change the current segment
		"""
		if isinstance(segment, int):
			raise NotImplementedError
		elif isinstance(segment, WIFFWAVE):
			self._current_file = segment.fw
			self._current_segment = segment
		else:
			raise NotImplementedError

		return self._current_segment

	def new_file(self, fname, force=False):
		"""
		Start a new file without any segments
		"""
		if fname in self._files:
			raise Exception("File '%s' is already associated with this WIFF file, cannot create it" % fname)

		if os.path.exists(fname):
			if not force:
				raise Exception("File '%s' exists, cannot open; pass force=True to override" % fname)

			# Truncate file
			os.truncate(fname, 0)

		# Add file
		f = self._files[fname] = _filewrap(fname)
		self._chunks[fname] = []
		self.set_file(fname)

		fidx_start = fidx_end = self.num_frames
		aidx_start = aidx_end = self.num_annotations

		# Add file to INFO chunk
		self._chunks['INFO'].add_file(fname, fidx_start, fidx_end, aidx_start, aidx_end)

	def new_annotations(self):
		"""
		Start a new chunk for annotations.
		"""

		if self._current_file is None:
			raise ValueError("Must set active file before creating a new annotations chunk")

		# Blank current annotations pointer
		self._current_annotations = None

		# Get last chunk
		fname = self._current_file.fname
		cs = self._chunks[fname]
		if len(cs):
			lastchunk = cs[-1].chunk

			# End of the last chunk (offset + size) is where the next block begins
			nextoff = lastchunk.offset + lastchunk.size


			# Create new chunk
			self._current_file.resize_add(4096)
			c = WIFF_chunk(self._current_file, nextoff)
		else:
			# No chunks, this starts at the beginning of the file
			c = WIFF_chunk(self._current_file, 0)

		w = WIFFANNO(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None)
		w.initheader()

		self._current_annotations = w

	def new_segment(self, chans, segmentid=None):
		"""
		Start a new segment in the current file
		"""

		if self._current_file is None:
			raise ValueError("Must set active file before creating a new segment")

		# Blank current segment pointer
		self._current_segment = None

		# Auto-generated segment ID's
		if segmentid is None:
			raise NotImplementedError("Pick an available segmentid")

		# Get last chunk
		fname = self._current_file.fname
		cs = self._chunks[fname]
		if len(cs) == 0:
			firstsegment = True

			# No chunks yet (shouldn't happen on main file, but can happen just after new_file)
			c = WIFF_chunk(self._current_file, 0)
		else:
			firstsegment = False

			lastchunk = cs[-1].chunk

			# End of the last chunk (offset + size) is where the next block begins
			nextoff = lastchunk.offset + lastchunk.size

			# Create new chunk
			c = WIFF_chunk(self._current_file, nextoff)

		# Create chunk data
		if not firstsegment:
			# Have to create a file with some contents in order to mmap it, so use this first page if first segment
			self._current_file.resize_add(4096)

		w = WIFFWAVE(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None, segmentid)

		# Create WAVE header
		w.initheader(chans, self.num_frames, self.num_frames)

		# Current segment
		self._current_segment = w

		return w

	def add_frames(self, *frames):
		"""
		Add frames of samples to the current segment
		"""
		return self._current_segment.add_frames(*frames)

	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment
		"""
		return self._current_segment.add_frame(*samps)

	def add_annotation(self, **kargs):
		"""
		Add an annotation to the current chunk.
		"""
		return self._current_annotations.add_annotation(**kargs)

	# -----------------------------------------------
	# -----------------------------------------------
	# Dump

	def dumps_dict(self):
		"""
		Dump WIFF meta data into a dict() for handling within Python.
		"""
		ret = {
			'file': self._fname,
			'start': self.start,
			'end': self.end,
			'description': self.description,
			'fs': self.fs,
			'num_frames': self.num_frames,
			'num_annotations': self.num_annotations,
			'channels': [],
			'files': [],
			'segments': [],
		}

		for i in range(self.num_channels):
			c = self.channels[i]
			ret['channels'].append({
				'idx': c.index.val,
				'name': c.name.val,
				'bit': c.bit.val,
				'unit': c.unit.val,
				'comment': c.comment.val,
			})
		for i in range(self.num_files):
			f = self.files[i]
			ret['files'].append({
				'idx': f.index.val,
				'name': f.name.val,
				'fidx start': f.fidx_start.val,
				'fidx end': f.fidx_end.val,
			})

		return ret

	def dumps_str(self):
		"""
		Dump WIFF meta data into a string that can be printed.
		"""

		d = self.dumps_dict()

		ret = []
		ret.append("%20s | %s" % ("File", d['file']))
		ret.append("%20s | %s" % ("Description", d['description']))
		ret.append("%20s | %s" % ("Start", d['start']))
		ret.append("%20s | %s" % ("End", d['end']))
		ret.append("%20s | %s" % ("fs", d['fs']))
		ret.append("%20s | %s" % ("Number of Frames", d['num_frames']))
		ret.append("%20s | %s" % ("Number of Annotations", d['num_annotations']))
		ret.append("")
		for c in d['channels']:
			ret.append("%20s %d" % ('Channel', c['idx']))
			ret.append("%25s | %s" % ('Name', c['name']))
			ret.append("%25s | %s" % ('Bit', c['bit']))
			ret.append("%25s | %s" % ('Unit', c['unit']))
			ret.append("%25s | %s" % ('Comment', c['comment']))
		ret.append("")
		for f in d['files']:
			ret.append("%20s %d" % ('File', f['idx']))
			ret.append("%25s | %s" % ('Name', f['name']))
			ret.append("%25s | %s" % ('Frame Index Start', f['fidx start']))
			ret.append("%25s | %s" % ('Frame Index End', f['fidx end']))

		return "\n".join(ret)

	def dumps_json(self):
		"""
		Dump WIFF meta data into a json for handling within Python.
		"""

		def dtconv(o):
			if isinstance(o, datetime.datetime):
				return o.strftime(DATE_FMT)

		return json.dumps(self.dumps_dict(), default=dtconv)

class _filewrap:
	"""
	Internal file wrapper that memory maps (mmap) the file.
	This provides index access to the file.
	"""
	def __init__(self, fname):
		""" Wrap the file with name @fname """
		if not os.path.exists(fname):
			# Have to call open this way as it otherwise means the function defined above
			f = __builtins__['open'](fname, 'wb')
			# Have to write something to memory map it
			f.write(b'\0' *4096)
			f.close()

		self.fname = fname
		# Have to call open this way as it otherwise means the function defined above
		self.f = __builtins__['open'](fname, 'r+b')
		self.mmap = mmap.mmap(self.f.fileno(), 0)
		self.size = os.path.getsize(fname)

	def close(self):
		self.mmap.close()
		self.f.close()

	def resize(self, sz):
		"""Change the size of the memory map and the file"""
		self.mmap.resize(sz)
		self.size = os.path.getsize(self.fname)
	def resize_add(self, delta):
		"""Add bytes to the existing size"""
		self.resize(self.size + delta)

	def __getitem__(self, k):
		"""
		Supply an integer or slice to get binary data
		"""
		return self.mmap[k]

	def __setitem__(self, k,v):
		"""
		Supply an integer or slice and binary data.
		If the data is beyond the file size, NeedResizeException is thrown
		"""
		# Resize map and file upward as needed
		if isinstance(k, slice):
			if k.stop > self.size:
				raise NeedResizeException
		else:
			if k > self.size:
				raise NeedResizeException

		self.mmap[k] = v

class NeedResizeException(Exception):
	"""
	Exception thrown when the underlying file is too small and should be resized.
	"""
	pass

class WIFF_chunk:
	"""
	Helper class to interface with chunk headers.
	"""
	def __init__(self, fw, offset):
		self._s = chunk_struct(fw, offset)

	def resize_callback(self, sz):
		self.size = sz

	@property
	def offset(self): return self._s.offset

	@property
	def data_offset(self): return self.offset + self.len

	@property
	def magic(self): return self._s.magic.val
	@magic.setter
	def magic(self, v): self._s.magic.val = v

	@property
	def size(self): return self._s.size.val
	@size.setter
	def size(self, v): self._s.size.val = v

	@property
	def len(self): return 24

	@property
	def attributes(self):
		return struct.unpack("<BBBBBBBB", struct.pack("<Q", self._s.attributes.val))
	@attributes.setter
	def attributes(self, v):
		self._s.attributes.val = struct.unpack("<Q", struct.pack("<BBBBBBBB", *v))[0]


	@staticmethod
	def FindChunks(f):
		total_sz = os.path.getsize(f.name)

		chunks = []

		off = 0
		while off < total_sz:
			f.seek(off)

			p = {
				'magic': f.read(8).decode('utf8'),
				'size': None,
				'attrs': None,
			}

			dat = f.read(8)
			sz = struct.unpack("<Q", dat)[0]
			if sz == 0:
				raise ValueError("Found zero length chunk, non-sensical")
			p['size'] = sz

			dat = f.read(8)
			p['attrs'] = struct.unpack("<BBBBBBBB", dat)

			# Include offsets
			p['offset header'] = off
			p['offset data'] = off + 24

			chunks.append(p)
			off += p['size']

		return chunks

	@staticmethod
	def ResizeChunk(chk, new_size):
		"""
		Resize the chunk @chk to the new size indicated @new_size in bytes.
		If not the last chunk in the file, then everything after it must be moved
		"""

		# Work only in pages
		if new_size % 4096 != 0:
			raise ValueError("New size for a chunk must be in an increment of 4096: %d" % new_size)

		if chk.size == new_size:
			# NOP: done already...
			return
		elif chk.size > new_size:
			raise ValueError("Cannot shrink chunk size (currently %d, requested %d)" % (cur, val))

		# Current file size in bytes
		fsize = os.path.getsize(chk._s.fw.fname)

		# Size to increment by
		delta = new_size - chk.size

		# Get in pages
		## Start is the page start of this chunk
		pg_chk_start = chk.offset // 4096
		## Page offset of the page after the end of this chunk
		pg_chk_end = (chk.offset + chk.size) // 4096
		## Total size in pages
		pg_total = fsize // 4096

		# Increase file size
		chk._s.fw.resize_add(delta)

		# If not the last chunk, then need to move pages
		if fsize > chk.offset + chk.size:
			# Have to iterate backward overwise pages could overwrite
			# If moving pages 3 & 4 (eg, range(3,5)) then have to iterate 4 then 3 (eg, range(5-1,4-1,-1)
			for i in range(pg_total-1, pg_chk_end-1, -1):
				# Old offset is the start of the page
				of_old = i*4096
				# New offset is the delta of the new pages
				of_new = i*4096 + delta
				# Move the page
				chk._s.fw[of_new:of_new+4096] = chk._s.fw[of_old:of_old+4096]
		else:
			# Chunk at end; nothing to move (just expand the chunk and file at the end)
			pass

		for i in range(pg_chk_end, pg_chk_end+(delta//4096)):
			# Blank the now vacant page (strictly not necessary as data within a chunk shouldn't be parsed
			# but blank it anyway for good measure)
			chk._s.fw[i*4096:(i+1)*4096] = b'\0'*4096

		# Record the chunk size as bigger
		chk.size = new_size

class WIFFINFO:
	"""
	Helper class that interfaces the data portion of a WIFFINFO chunk.
	This chunk includes all of the meta data about the recording (start time, end time, sampling frequency, etc).
	"""

	def __init__(self, wiff, fw, chunk):
		"""
		Manage a WIFFINFO chunk using the _filewrap object @fw.
		Supply the absolute offset @offset the chunk is located at in the file.
		aLL OPErations are using an mmap and there is no caching.
		"""
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk

		self._s = info_struct(fw, self.chunk.data_offset)

	@property
	def offset(self): return self._s.offset

	def initchunk(self):
		"""
		Initiailizes a new chunk for this chunk type.
		"""
		self.chunk.magic = 'WIFFINFO'
		self.chunk.size = 4096
		# Version 1
		self.chunk.attributes = (1,0,0,0, 0,0,0,0)

	def initheader(self, start, end, desc, fs, num_frames, num_annotations, channels, files):
		"""
		Initializes a new header
		This requires explicit initialization of all the byte indices.
		"""

		self.index_start = info_struct.lenplan("","","", [], [])
		self.index_end = self.index_start + len(start.strftime(DATE_FMT))
		self.index_description = self.index_end + len(end.strftime(DATE_FMT))
		self.index_channels = self.index_description + len(desc)

		self.fs = fs
		self.num_frames = num_frames
		self.num_annotations = num_annotations
		self.num_channels = len(channels)
		self.num_files = len(files)

		self.start = start.strftime(DATE_FMT)
		self.end = end.strftime(DATE_FMT)
		self.description = desc

		# This also sets the index_files_start because it depends on length of the channels
		self._initchannels(channels)

		# This also sets the indes_files_end
		self._initfiles(files)


	def _initchannels(self, chans):
		self.num_channels = len(chans)

		# Size of the jumptable
		strt = self._s.channels_jumptable.sizeof
		for i in range(len(chans)):
			c = chans[i]

			sz = channel_struct.lenplan(c['name'], c['unit'], c['comment'])

			self._s.channels_jumptable[i] = (strt, strt+sz)
			strt += sz

			off = channel_struct.lenplan("","","")

			ln_name = len(c['name'])
			ln_unit = len(c['unit'])
			ln_comment = len(c['comment'])

			self._s.channels[i].index.val = i
			self._s.channels[i].index_name.val = off
			self._s.channels[i].index_unit.val = off + ln_name
			self._s.channels[i].index_comment_start.val = off + ln_name + ln_unit
			self._s.channels[i].index_comment_end.val = off + ln_name + ln_unit + ln_comment

			self._s.channels[i].bit.val = c['bit']

			self._s.channels[i].name.val = c['name']
			self._s.channels[i].unit.val = c['unit']
			self._s.channels[i].comment.val = c['comment']

		# Get the last byte used by the last entry as the start for the files
		self.index_file_start = self._s.channels_jumptable[-1][1] + self._s.channels_jumptable.offset


	def _initfiles(self, files):
		self.index_file_end = self.index_file_start

		self.num_files = 0

		for i in range(len(files)):
			f = files[i]
			self.add_file(f['name'], f['fidx_start'], f['fidx_end'], f['aidx_start'], f['aidx_end'])

	@property
	def magic(self): return self.chunk.magic

	@property
	def index_start(self): return self._s.index_start.val
	@index_start.setter
	def index_start(self, val): self._s.index_start.val = val

	@property
	def index_end(self): return self._s.index_end.val
	@index_end.setter
	def index_end(self, val): self._s.index_end.val = val

	@property
	def index_description(self): return self._s.index_description.val
	@index_description.setter
	def index_description(self, val): self._s.index_description.val = val

	@property
	def index_channels(self): return self._s.index_channels.val
	@index_channels.setter
	def index_channels(self, val): self._s.index_channels.val = val

	@property
	def index_file_start(self): return self._s.index_file_start.val
	@index_file_start.setter
	def index_file_start(self, val): self._s.index_file_start.val = val

	@property
	def index_file_end(self): return self._s.index_file_end.val
	@index_file_end.setter
	def index_file_end(self, val): self._s.index_file_end.val = val

	@property
	def fs(self): return self._s.fs.val
	@fs.setter
	def fs(self, val): self._s.fs.val = val

	@property
	def num_channels(self): return self._s.num_channels.val
	@num_channels.setter
	def num_channels(self, val): self._s.num_channels.val = val

	@property
	def num_files(self): return self._s.num_files.val
	@num_files.setter
	def num_files(self, val): self._s.num_files.val = val

	@property
	def num_frames(self): return self._s.num_frames.val
	@num_frames.setter
	def num_frames(self, val): self._s.num_frames.val = val

	@property
	def num_annotations(self): return self._s.num_annotations.val
	@num_annotations.setter
	def num_annotations(self, val): self._s.num_annotations.val = val


	@property
	def start(self):
		return self._s.start.val
	@start.setter
	def start(self, val):
		if isinstance(val, datetime.datetime):
			val = val.strftime(DATE_FMT)
		else:
			pass

		exist = self.index_end - self.index_start
		if len(val) == exist:
			self._s.start.val = val
		else:
			raise NotImplementedError

	@property
	def end(self):
		return self._s.end.val
	@end.setter
	def end(self, val):
		if isinstance(val, datetime.datetime):
			val = val.strftime(DATE_FMT)
		else:
			pass

		if len(val) == len(self._s.end.val):
			self._s.end.val = val
		else:
			raise NotImplementedError

	@property
	def description(self):
		return self._s.description.val
	@description.setter
	def description(self, val):
		if len(val) == len(self._s.description.val):
			self._s.description.val = val
		else:
			raise NotImplementedError

	@property
	def channels(self): return self._s.channels

	@property
	def files(self): return self._s.files

	def add_file(self, fname, fidx_start, fidx_end, aidx_start, aidx_end):
		"""
		Adds a new file to the list
		"""

		# Get length of new file entry
		ln = file_struct.lenplan(fname)

		# Get current size of chunk and end index of last file entry
		cur_size = self.chunk.size
		cur_end = self.index_file_end

		# If current end plus new file struct plus 4 for jumptable entry is more than current size, bump it up a page
		if cur_end + ln + 4 > cur_size:
			WIFF_chunk.ResizeChunk(self.chunk, cur_size + 4096)

		# Get current number of files, which is also the index of the next jumptable entry
		fnum = self._s.num_files.val


		# Add new entry to the jumptable
		idx = self._s.files.add(ln, start=12, page=12)
		entry = self._s.files_jumptable[idx]

		# Offset is relative to jumptable, so add in offset of the jumptable
		self.index_file_end = entry[1] + self._s.files_jumptable.offset

		# Offset into file_struct where name starts
		off = file_struct.lenplan("")

		# Set file information
		self._s.files[fnum].index.val = fnum
		self._s.files[fnum].index_name_start.val = off
		self._s.files[fnum].index_name_end.val = off + len(fname)
		self._s.files[fnum].fidx_start.val = fidx_start
		self._s.files[fnum].fidx_end.val = fidx_end
		self._s.files[fnum].aidx_start.val = aidx_start
		self._s.files[fnum].aidx_end.val = aidx_end
		self._s.files[fnum].name.val = fname


class WIFFANNO:
	"""
	Helper class that handles annotations.
	"""

	def __init__(self, wiff, fw, chunk):
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk
		self._s = annos_struct(fw, chunk.data_offset)

	def initchunk(self, compression):
		"""
		Initiailizes a new chunk for this chunk type.
		"""

		# All new chunks are given a 4096 block initially
		# Expand to 2 blocks (1 for jumptable, 1 for data)
		self.fw.resize_add(4096)

		self.chunk.magic = 'WIFFANNO'
		self.chunk.size = 4096*2
		self.chunk.attributes = (0,0,0,0, 0,0,0,0)

		attrs = [0]*8
		if compression is None:
			attrs[0] = ord('0')
		elif compression.lower() == 'z':
			attrs[0] = ord('Z')
		elif compression.lower() == 'b':
			attrs[0] = ord('B')
		else:
			raise ValueError('Unrecognized comppression type "%s"' % compression)

		self.chunk.attributes = tuple(attrs)

	def initheader(self):
		"""
		Initialize a new header.
		"""

		self.aidx_start = 0
		self.aidx_end = 0
		self.fidx_first = 0
		self.fidx_last = 0
		self.num_annotations = 0
		self._s.index_annotations.val = 38

	@property
	def magic(self): return self.chunk.magic

	@property
	def aidx(self): return bstruct.interval(self.aidx_start, self.aidx_end)
	def fidx(self): return bstruct.interval(self.fidx_first, self.fidx_last)

	@property
	def aidx_start(self): return self._s.aidx_start.val
	@aidx_start.setter
	def aidx_start(self, val): self._s.aidx_start.val = val

	@property
	def aidx_end(self): return self._s.aidx_end.val
	@aidx_end.setter
	def aidx_end(self, val): self._s.aidx_end.val = val

	@property
	def fidx_first(self): return self._s.fidx_first.val
	@fidx_first.setter
	def fidx_first(self, val): self._s.fidx_first.val = val

	@property
	def fidx_last(self): return self._s.fidx_last.val
	@fidx_last.setter
	def fidx_last(self, val): self._s.fidx_last.val = val

	@property
	def num_annotations(self): return self._s.num_annotations.val
	@num_annotations.setter
	def num_annotations(self, val): self._s.num_annotations.val = val

	@property
	def annotations(self): return self._s.annotations


	def add_annotation_C(self, fidx, comment):
		return self.add_annotation('C', fidx, comment=comment)
	def add_annotation_M(self, fidx, marker):
		return self.add_annotation('M', fidx, marker=marker)
	def add_annotation_D(self, fidx, marker, value):
		return self.add_annotation('D', fidx, marker=marker, value=value)
	def add_annotation(self, typ, fidx, **parms):
		"""
		Adds an annotation to the currently selected annotation segment.
		Can use this generic function, or one of the related functions to simplify coding.
		"""

		# Check for annotation type
		if typ == 'C':
			if 'comment' not in parms: raise ValueError("For a 'C' annotation, expected a comment parameter")
		elif typ == 'M':
			if 'marker' not in parms: raise ValueError("For a 'M' annotation, expected a marker parameter")
		elif typ == 'D':
			if 'marker' not in parms: raise ValueError("For a 'D' annotation, expected a marker parameter")
			if 'value' not in parms: raise ValueError("For a 'D' annotation, expected a value parameter")
		else:
			raise KeyError("Unexpected annotation type '%s', not recognized" % (typ,))

		# Coerce if able to an interval
		fidx = twotuplecheck(fidx)

		ln = ann_struct.lenplan(typ, **parms)

		# Convert 4-char string to a 32-bit number
		if 'marker' in parms and isinstance(parms['marker'], str):
			parms['marker'] = struct.unpack("<I", parms['marker'].encode('ascii'))[0]

		# Get the annotation number (same as the annotations[] index)
		ann_no = self.num_annotations

		# Initialize these
		if self.num_annotations == 0:
			# First annotation
			self.aidx_start = 0
			self.aidx_end = 0
			self.fidx_first = fidx.start
			self.fidx_last = fidx.stop

		# Add to jump table
		self._s.annotations.add(ln, start=4096-self._s.annotations_jumplist.offset-self.chunk.len, page=4096)

		# Copy in annotation data
		a = self._s.annotations[ann_no]
		a.type.val = typ
		a.fidx_start.val = fidx.start
		a.fidx_end.val = fidx.stop

		aa = a.condition_on('type')
		if typ == 'C':
			aoff = ann_C_struct.lenplan("")
			aa.index_comment_start.val = aoff
			aa.index_comment_end.val = aoff + len(parms['comment'])
			aa.comment.val = parms['comment']
		elif typ == 'D':
			aa.marker.val = parms['marker']
			aa.value.val = parms['value']
		elif typ == 'M':
			aa.marker.val = parms['marker']
		else:
			raise ValueError("Unrecognized annotation type '%s'" % typ)


		# Update annotations header
		self.aidx_end = self.aidx_start + ann_no
		# Update frame index range
		self.fidx_first = min(self.fidx_first, fidx.start)
		self.fidx_last = max(self.fidx_last, fidx.stop)


		# If this is the first frame, then need to set the start
		if ann_no == 0:
			self.aidx_start = ann_no

		# Add number of annotations to the end
		self.aidx_end = ann_no + 1

		# Update counter
		self.num_annotations = ann_no + 1
		self.wiff._chunks['INFO'].num_annotations += 1

		for f in self.wiff.files:
			if f.name.val == self.fw.fname:
				f.aidx_end.val = self.aidx_end


	def resize_add_page(self, val):
		"""
		Resize this chunk by adding @val pages of 4096 bytes.
		"""

		if val < 0:
			raise ValueError("Cannot shrink chunk by negative pages: %d" % val)

		self.resize_add(val * 4096)

	def resize_add(self, val):
		"""
		Resize this chunk by adding @val to the current size in bytes.
		If not a multiple of 4096 byte pages, it will be rounded up to the full page.
		"""

		if val < 0:
			raise ValueError("Cannot shrink chunk by negative bytes: %d" % val)

		# Take current size and add the supplied value
		self.resize(self.chunk.size + val)

	def resize(self, new_size):
		"""
		Resize this chunk to @val bytes.
		If not a multiple of 4096 byte pages, it will be rounded up to the full page.
		"""

		if new_size < self.chunk.size:
			raise ValueError("Cannot shrink chunk: %d" % val)

		# Get number of 4096 pages
		z = divmod(new_size, 4096)
		if z[1] != 0:
			# If a partial page, then incremeent to a full page
			pgs = z[0] + 1
		else:
			# Requested just the right number of frames to fill a full page (kudos)
			pgs = z[0]

		# Get new chunk size in bytes (4096 bytes per page)
		new_size = pgs * 4096

		# Actually resize the chunk
		WIFF_chunk.ResizeChunk(self.chunk, new_size)

class WIFFWAVE:
	"""
	Helper class that interfaces the data portion of a WIFFWAVE chunk.
	This chunk includes the raw binary data in the recording.
	"""

	def __init__(self, wiff, fw, chunk):
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk
		self._s = wave_struct(fw, chunk.data_offset)

		self._frame_size = None
		self._ser = None
		self._deser = None

	def setup(self):
		"""
		Must be called after creating object on an old chunk, or done automatically when calling initheader().
		This creates a serializer (_ser) and de-serializer (_deser) for converting frames to bytes/ints and vice versa.
		"""

		# Get channel indices
		mychans = self.channels

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in mychans]

		# Expand to full bytes
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans]
		chan_size = [_//8 for _ in chan_size]
		self._frame_size = sum(chan_size)

		# Evaluate if able to use struct to parse bytes or if must step manually.
		allsane = True
		structstr = "<"
		for chan in chan_size:
			if chan == 1: structstr += "B"
			elif chan == 2: structstr += "H"
			elif chan == 4: structstr += "I"
			elif chan == 8: structstr += "Q"
			else:
				allsane = False
				break

		if allsane:
			# All channel sizes are sane struct sizes (1, 2, 4, or 8 bytes each)
			# Form a struct object with string parsed once and used for both ser and deser
			s = struct.Struct(structstr)
			def sane_ser(*samps, _s=s):
				return _s.pack(*samps)
			def sane_deser(dat, _s=s):
				return _s.unpack(dat)

			self._ser = sane_ser
			self._deser = sane_deser
		else:
			# Non-sane sizes (at least one channel is not 1, 2, 4, or 8 bytes in size)
			# Have to manually step through and parse the bytes (can't use struct library)
			def insane_ser(samps, chans=chan_size):
				ret = []
				for i in range(len(chans)):
					ret.append( samps[i].to_bytes(chans[i], byteorder='little') )
				return b''.join(ret)
			def insane_deser(dat, chans=chan_size):
				ret = []
				off = 0
				for i in range(len(chans)):
					ret.append( int.from_bytes(dat[off:off+chans[i]], byteorder='little') )
					off += chans[i]
				return tuple(ret)

			self._ser = insane_ser
			self._deser = insane_deser

	def initchunk(self, compression, segmentid):
		"""
		Initiailizes a new chunk for this chunk type.
		"""

		self.chunk.magic = 'WIFFWAVE'
		self.chunk.size = 4096
		self.chunk.attributes = (0,0,0,0, 0,0,0,0)

		attrs = [0]*8
		if compression is None:
			attrs[0] = ord('0')
		elif compression.lower() == 'z':
			attrs[0] = ord('Z')
		elif compression.lower() == 'b':
			attrs[0] = ord('B')
		else:
			raise ValueError('Unrecognized comppression type "%s"' % compression)

		attrs[4:8] = list(memoryview(struct.pack("<I", segmentid)))

		self.chunk.attributes = tuple(attrs)

	def initheader(self, channels, fidx_start, fidx_end):
		"""
		Initialize a new header
		"""

		chans_nums = []
		chans_structs = []
		for c in channels:
			if isinstance(c, int):
				chans_nums.append(c)
				chans_structs.append( self.wiff.channels[c] )
			elif isinstance(c, channel_struct):
				chans_nums.append(c.index.val)
				chans_structs.append(c)
			else:
				raise TypeError("Unknown channel type provided: '%s'" % type(c))

		# Get just the indices
		indices = chans_nums
		# Make a bitfield of it
		b = bitfield()
		# Make 256 bits wide
		b.clear(255)
		b.set(*indices)
		bs = b.to_bytes()

		self.channels = bs
		self.fidx_start = fidx_start
		self.fidx_end = fidx_end

		# Expand to full bytes and check they match data size
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans_structs]

		# Total byte size of a frame
		frame_size = sum(chan_size)//8

		# Set frame size
		self._s.records.size = frame_size

		self.setup()

	@property
	def magic(self): return self.chunk.magic

	@property
	def channels(self):
		b = bitfield.from_bytes(self._s.channels[0:32])
		return b.set_indices()

	@channels.setter
	def channels(self, v):
		if isinstance(v, tuple):
			self._s.channels[0:32] = v
		elif isinstance(v, bytes):
			self._s.channels[0:32] = v
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def fidx_start(self): return self._s.fidx_start.val
	@fidx_start.setter
	def fidx_start(self, v):
		self._s.fidx_start.val = v

		# Copy to WIFF
		fs = self.wiff._chunks['INFO'].files
		for f in fs:
			if f.name.val == self.fw.fname:
				# only update if start is earlier
				# Eg, adding a second segment to the same file has a different
				# start frame index, so don't update if larger than the existing frame index
				if v < f.fidx_start.val:
					f.fidx_start.val = v
				return

		raise IndexError("File not found by name '%s'" % self.fw.fname)

	@property
	def fidx_end(self): return self._s.fidx_end.val
	@fidx_end.setter
	def fidx_end(self, v):
		self._s.fidx_end.val = v

		# Copy to WIFF
		fs = self.wiff._chunks['INFO'].files
		for f in fs:
			if f.name.val == self.fw.fname:
				f.fidx_end.val = v
				return

		raise IndexError("File not found by name '%s'" % self.fw.fname)

	@property
	def fidx(self): return bstruct.interval(self.fidx_start, self.fidx_end)

	def __getitem__(self, index):
		return self._s.records[index]

	@property
	def Ser(self):
		if self._ser is None: self.setup()
		return self._ser

	@property
	def DeSer(self):
		if self._deser is None: self.setup()
		return self._deser

	@property
	def channel_sizes(self):
		"""
		Get sizes of the channels as a tuple of full bytes.
		"""
		chans = self.channels

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in chans]

		# Expand to full bytes and check they match data size
		return tuple([c.bit.val + (c.bit.val%8) for c in chans])

	@property
	def frame_size(self):
		"""
		Get the size of a frame in bytes.
		"""

		# Total byte size of a frame
		return sum(self.channel_sizes)//8

	@property
	def frame_space(self):
		"""
		Return the number of frames available for the currently defined space.
		This number has nothing to do with the number of frames in the chunk, only total space available to them.
		"""
		# Chunk size includes chunk header, WIFFWAVE header, and all the frames
		chunksz = self.chunk.size
		# Frame size that includes all channels
		fsz = self.frame_size
		# Chunk header size
		headersz = self._s.offset - self.chunk.offset
		# WIFFWAVE header size
		waveheadersz = self._s.lenplan(0,0)

		# Chunk size minus chunk header size minus wave header size is space available to frames
		fspace = chunksz - headersz - waveheadersz

		# Total space left for frames divided by frame size (integer devision rounds to # of full frames in the space)
		return fspace // fsz

	@frame_space.setter
	def frame_space(self, val):
		"""
		Set the total number of frames possible to store in this chunk.
		This will round up to a full 4096 page for the chunk so the actual number of space may be equal or larger than @val.
		"""
		cur = self.frame_space
		if cur == val:
			# NOP: rare case requested frame space is what's already present
			return
		elif val < cur:
			raise ValueError("Cannot shrink chunk size (currently %d, requested %d)" % (cur, val))


		# Frame size that includes all channels
		fsz = self.frame_size
		new_frames_sz = val * fsz

		# Get number of 4096 pages
		z = divmod(new_frames_sz, 4096)
		if z[1] != 0:
			# If a partial page, then incremeent to a full page
			pgs = z[0] + 1
		else:
			# Requested just the right number of frames to fill a full page (kudos)
			pgs = z[0]

		# Get new chunk size in bytes (4096 bytes per page)
		new_size = pgs * 4096

		# Actually resize the chunk
		WIFF_chunk.ResizeChunk(self.chunk, new_size)

	@property
	def frame_space_available(self):
		"""
		Return the number of available frames that can be put in the remaining space.
		"""
		# Numer of total frames available less number of frames present is the number of frames available
		return self.frame_space - self.fidx.len


	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment.
		This updates the frame index counters and number of frames.
		"""
		return self.add_frames(samps)

	def add_frames(self, *frames):
		"""
		Add a set of frames
		"""

		if self.frame_space_available < len(frames):
			raise NeedResizeException("Cannot add frames, not enough space")

		chans = self.channels
		len_chans = len(chans)

		for i in range(len(frames)):
			if len(frames[i]) != len_chans:
				raise ValueError("Mismatch between samples (%d) and number of channels (%d) for frame %d" % (len(frames[i]),len_chans,i))

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in chans]

		# Expand to full bytes and check they match data size
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans]
		for j in range(len(frames)):
			samps = frames[j]
			for i in range(len(samps)):
				if chan_size[i] != len(samps[i])*8:
					raise ValueError("Sample %d for channel %d is %d bytes but channel is %d bytes (%d bits)" % (j,chans[i].index, len(samps[i]), chan_size[i], chans[i].bit))

		# Total byte size of a frame
		frame_size = sum(chan_size)//8


		# Map frame into data block
		s = self.fidx_start
		e = self.fidx_end
		delta = e - s


		# Determine frame number for next frame-to-be-added
		frame_num = self.wiff.num_frames

		# Edge case of no frames, thus s == 0, e == 0, delta == 0
		# and with 1 frame thus s == 0, e == 0, delta == 0 and frame 1 overwrites frames 0
		# The differentiating factor between these cases is that num_frames is non-zero

		for i in range(len(frames)):
			samps = frames[i]

			# Assign frame
			self._s.records[delta+i] = b''.join(samps)

		# If this is the first frame, then need to set the start
		if frame_num == 0:
			self.fidx_start = frame_num

		# Add number of frames to the end
		self.fidx_end = frame_num + len(frames)

		# Increment
		self.wiff.num_frames = frame_num + len(frames)

