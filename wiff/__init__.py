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
* A recording is broken into segments consisting of multiple frames
* A frame consists of samples across all present channels in a segment at a given point in time
* A channel is a specific binary data source of data that is piece-wise present (not present sample-by-sample, but over a continous time period)
* Time index is the index into the frames from zero (start of recording) to N (last frame of the recording)
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
	It is encouraged to put chunk boundaries on 4096 byte blocks, or larger.
	This permits modifying a file in place without having to rewrite the entire file.
	If streaming to the end of a chunk then this matters less.


	WIFFINFO -- Information
	Attributes
		[0] -- Version of WIFF
		[1-7] -- Reserved

	Info chunk that is used to coordinate high-level information.

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

		Thus, the indices of the strings' start and end can be calculated and the total size of the data block determined without having to parse actual content data (total size is in [8:9]). Strings are NOT null terminated.


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
		[13:20] -- End frame index (inclusive)
		[21:X] -- File name string


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

"""

import datetime
import json
import mmap
import os.path
import struct
import types

from .bits import bitfield
from .compress import WIFFCompress
from .structs import chunk_struct, info_struct, channel_struct, file_struct, wave_struct
from .structs import annos_struct, ann_struct, ann_C_struct, ann_D_struct, ann_M_struct

DATE_FMT = "%Y%m%d %H%M%S.%f"
WIFF_VERSION = 1

class WIFF:
	"""
	Primary interface class to a WIFF recording.
	All interactions should occur through this class.
	Supply the primary WIFF file that contains the information for the recording
	If creating a new file, properties in @props is needed to start the recording.

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
		'files'			list of files, probably empty for a new recording
	"""
	def __init__(self, fname, props=None):
		self._files = {}
		self._chunks = {}

		self._current_file = None
		self._current_segment = None
		self._current_annogations = None

		if os.path.exists(fname):
			self._open_existing(fname)
		else:
			self._open_new(fname, props)

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

	def __enter__(self):
		pass
	def __exit__(self, *exc):
		self.close()
		return False

	def close(self):
		for fname,o in self._files.items():
			o.close()

	def _open_new(self, fname, props):
		# Blank all files
		self._fname = fname
		self._files.clear()
		self._chunks.clear()

		self._chunks[fname] = []

		# Wrap file
		f = self._files[fname] = _filewrap(fname)
		# Initial 4096 block
		f.resize(4096)

		c = WIFF_chunk(f, 0)

		# No frames yet
		num_frames = 0

		props['files'].append({
			'name': fname,
			'fidx_start': 0,
			'fidx_end': 0,
		})

		c = WIFF_chunk(f, 0)
		w = WIFFINFO(self, f, c)
		w.initchunk()
		w.initheader(props['start'], props['end'], props['description'], props['fs'], 0,0, props['channels'], props['files'])


		self._chunks[fname] = [w]
		self._chunks['INFO'] = w

	def _open_existing(self, fname):
		# Blank all files
		self._fname = fname
		self._files.clear()
		self._chunks.clear()
		self._chunks[fname] = []

		# Wrap file
		f = self._files[fname] = _filewrap(fname)

		chunks = WIFF_chunk.FindChunks(f.f)
		for chunk in chunks:
			c = WIFF_chunk(f, chunk['offset header'])
			if chunk['magic'] == 'WIFFINFO':
				w = WIFFINFO(self, f, c)
				self._chunks[fname].append(w)

				if 'INFO' in self._chunks:
					raise NotImplementedError("Multiple WAVEINFO chunks is not supported")
				self._chunks['INFO'] = w
			elif chunk['magic'] == 'WIFFWAVE':
				w = WIFFWAVE(self, f, c)
				self._chunks[fname].append(w)
			elif chunk['magic'] == 'WIFFANNO':
				w = WIFFANNO(self, f, c)
				self._chunks[fname].append(w)

			else:
				raise TypeError('Uknown chunk magic: %s' % chunk['magic'])

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
				filts.append(lambda x: x.fidx_start.val <= fidx and x.fidx_end.val >= fidx)
			elif isinstance(fidx, types.FunctionType):
				filts.append(fidx)
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

	def get_frames(self, index):
		if isinstance(index, int):
			return [self.get_frame(index)]
		elif isinstance(index, slice):
			raise NotImplementedError
		else:
			raise TypeError("Unrecognize argument for index: '%s'" % (str(index),))

	def get_frame(self, index):
		chunks = self._GetWAVE()
		for chunk in chunks:
			if chunk.fidx_start > index:
				continue
			if chunk.fidx_end < index:
				continue

			# index is in this chunk
			off = index - chunk.fidx_start

			bs = chunk[off]
			# TODO: split into channels
			return bs

		raise KeyError("Frame index %d not found" % index)

	# -----------------------------------------------
	# -----------------------------------------------
	# Add data

	def set_file(self, fname):
		"""
		Change the current segment
		"""
		self._current_file = self._files[fname]
		self._current_segment = None

	def set_segment(self, segmentid):
		"""
		Change the current segment
		"""
		raise NotImplementedError

	def new_file(self, fname):
		"""
		Start a new WIFFWAVE file and segment in that file
		"""
		raise NotImplementedError

	def new_annotations(self):
		"""
		Start a new chunk for annotations.
		"""

		if self._current_file is None:
			raise ValueError("Must set active file before creating a new annotations chunk")

		# Blank current annotations pointer
		self._current_annogations = None

		# Get last chunk
		fname = self._current_file.fname
		cs = self._chunks[fname]
		lastchunk = cs[-1].chunk

		# End of the last chunk (offset + size) is where the next block begins
		nextoff = lastchunk.offset + lastchunk.size


		# Create new chunk
		self._current_file.resize_add(4096)
		c = WIFF_chunk(self._current_file, nextoff)
		w = WIFFANNO(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None)
		w.initheader()

		self._current_annogations = w

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
		lastchunk = cs[-1].chunk

		# End of the last chunk (offset + size) is where the next block begins
		nextoff = lastchunk.offset + lastchunk.size


		# Create new chunk
		c = WIFF_chunk(self._current_file, nextoff)

		# Create chunk data
		self._current_file.resize_add(4096)
		w = WIFFWAVE(self, self._current_file, c)
		cs.append(w)
		w.initchunk(None, segmentid)

		# Create WAVE header
		w.initheader(chans, self.num_frames, self.num_frames)

		# Current segment
		self._current_segment = w

	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment
		"""
		return self._current_segment.add_frame(*samps)

	def add_annotation(self, **kargs):
		"""
		Add an annotation to the current chunk.
		"""
		return self._current_annogations.add_annotation(**kargs)

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
			f = open(fname, 'wb')
			# Have to write something to memory map it
			f.write(b'0')
			f.close()

		self.fname = fname
		self.f = open(fname, 'r+b')
		self.mmap = mmap.mmap(self.f.fileno(), 0)
		self.size = os.path.getsize(fname)

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
	def data_offset(self): return self.offset + 24

	@property
	def magic(self): return self._s.magic.val
	@magic.setter
	def magic(self, v): self._s.magic.val = v

	@property
	def size(self): return self._s.size.val
	@size.setter
	def size(self, v): self._s.size.val = v

	@property
	def attributes(self):
		return struct.unpack("<BBBBBBBB", self._s.attributes.val)
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

			self._s.channels[i].index.val = i
			self._s.channels[i].index_name.val = off
			self._s.channels[i].index_unit.val = off + len(c['name'])
			self._s.channels[i].index_comment_start.val = off + len(c['name']) + len(c['unit'])
			self._s.channels[i].index_comment_end.val = off + len(c['name']) + len(c['unit']) + len(c['comment'])

			self._s.channels[i].bit.val = c['bit']

			self._s.channels[i].name.val = c['name']
			self._s.channels[i].unit.val = c['unit']
			self._s.channels[i].comment.val = c['comment']

		# Get the last byte used by the last entry as the start for the files
		self.index_file_start = self._s.channels_jumptable[-1][1] + self._s.channels_jumptable.offset


	def _initfiles(self, files):
		self.num_files = len(files)

		strt = self._s.files_jumptable.sizeof
		for i in range(len(files)):
			f = files[i]

			sz = file_struct.lenplan(f['name'])

			self._s.files_jumptable[i] = (strt, strt+sz)
			strt += sz


			off = file_struct.lenplan("")

			self._s.files[i].index.val = i
			self._s.files[i].index_name_start.val = off
			self._s.files[i].index_name_end.val = off + len(f['name'])
			self._s.files[i].fidx_start.val = f['fidx_start']
			self._s.files[i].fidx_end.val = f['fidx_end']
			self._s.files[i].name.val = f['name']

		# Get the last byte used for the files
		self.index_file_end = self._s.files_jumptable[-1][1] + self._s.files_jumptable.offset

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


	def add_annotation_C(self, fidx_start, fidx_end, comment):
		return self.add_annotation('C', fidx_start, fidx_end, comment=comment)
	def add_annotation_M(self, fidx_start, fidx_end, marker):
		return self.add_annotation('M', fidx_start, fidx_end, marker=marker)
	def add_annotation_D(self, fidx_start, fidx_end, marker, dat):
		return self.add_annotation('D', fidx_start, fidx_end, marker=marker, dat=dat)
	def add_annotation(self, typ, fidx_start, fidx_end, **parms):
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
			if 'dat' not in parms: raise ValueError("For a 'D' annotation, expected a dat parameter")
		else:
			raise KeyError("Unexpected annotation type '%s', not recognized" % (typ,))

		ln = ann_struct.lenplan(typ, **parms)

		# Convert 4-char string to a 32-bit number
		if 'marker' in parms and isinstance(parms['marker'], str):
			parms['marker'] = struct.unpack("<I", parms['marker'].encode('ascii'))[0]

		# Get the annotation number (same as the annotations[] index)
		ann_no = self.num_annotations

		if self.num_annotations == 0:
			# First annotation
			self.aidx_start = 0
			self.aidx_end = 0
			self.fidx_first = fidx_start
			self.fidx_last = fidx_end

			# Start first annotation at the next page boundary
			# But offset in the jumplist is relative to the start of the jump list
			_off = self._s.index_annotations.val
			# Subtract off the header
			_off += self._s.offset - self.chunk.offset

			# Set first jump
			self._s.annotations_jumplist[ann_no] = (4096-_off, 4096-_off+ln)

		else:
			# TODO Expand if needed

			# Get previous offsets
			prev = self._s.annotations_jumplist[ann_no-1]

			# Set new jump
			x = self._s.annotations_jumplist[ann_no] = (prev[1], prev[1] + ln)

		# Update counter
		self.num_annotations = ann_no + 1

		# Copy in annotation data
		a = self._s.annotations[ann_no]
		a.type.val = typ
		a.fidx_start.val = fidx_start
		a.fidx_end.val = fidx_end

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
		self.fidx_first = min(self.fidx_first, fidx_start)
		self.fidx_last = max(self.fidx_last, fidx_end)


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

		# Get just the indices
		indices = [c.index.val for c in channels]
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
		chan_size = [c.bit.val + (c.bit.val%8) for c in channels]

		# Total byte size of a frame
		frame_size = sum(chan_size)//8

		# Set frame size
		self._s.records.size = frame_size

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

	def __getitem__(self, index):
		return self._s.records[index]

	def add_frame(self, *samps):
		"""
		Add a frame of samples to the current segment.
		This updates the frame index counters and number of frames.
		"""
		return self.add_frames(samps)

	def add_frames(self, *frames):
		#FIXME: just a temp
		samps = frames[0]

		chans = self.channels

		if len(chans) != len(samps):
			raise ValueError("Mismatch between samples (%d) and number of channels (%d)" % (len(samps),len(chans)))

		# Get channel objects
		chans = [self.wiff.channels[_] for _ in chans]


		# Expand to full bytes and check they match data size
		chan_size = [c.bit.val + (c.bit.val%8) for c in chans]
		for i in range(len(samps)):
			if chan_size[i] != len(samps[i])*8:
				raise ValueError("Sample for channel %d is %d bytes but channel is %d bytes (%d bits)" % (chans[i].index, len(samps[i]), chan_size[i], chans[i].bit))

		# Total byte size of a frame
		frame_size = sum(chan_size)//8

		# Map frame into data block
		s = self.fidx_start
		e = self.fidx_end
		delta = e - s


		# Determine frame number
		frame_num = self.wiff.num_frames

		# Fringe case of no frames, thus s == 0, e == 0, delta == 0
		# and with 1 frame thus s == 0, e == 0, delta == 0 and frame 1 overwrites frames 0
		# The differentiating factor between these cases is that num_frames is non-zero
		if frame_num != 0:
			delta += 1

		# Assign frame
		try:
			self._s.records[delta] = b''.join(samps)
		except NeedResizeException:
			self.chunk.size += 4096
			self._s.fw.resize_add(4096)
			self._s.records[delta] = b''.join(samps)

		if frame_num == 0:
			self.fidx_start = frame_num
		self.fidx_end = frame_num

		self.wiff.num_frames = frame_num + 1

