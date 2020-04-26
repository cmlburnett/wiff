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
	8		8		Size of chunk not including the header
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
		[12:13] -- 16-bit sampling rate in samples per second
		[14:15] -- Number of channels (max 256 supported)
		[16:17] -- Number of files
		[18:25] -- Number of frames
		[26:X-1] -- Start of string data for above
		[X:Y-1] -- Start of channel definitions as non-padded sequences of the definition below
		[X+2*num_channels:X+2*num_channels+2] -- Start of channel definition for channel 2
		[Y:Z] -- Start of file definitions as non-padded sequences of the definition below

		Thus, the indices of the strings' start and end can be calculated and the total size of the data block determined without having to parse actual content data (total size is in [8:9]). Strings are NOT null terminated.


	Channel definition:
		The channel definitions section starts with a jump table of byte indices for the specified number of channels.

		[0:1] -- Byte index of start of channel definition #0
		[2:3] -- Byte index of start of channel definition #1
		[4:5] -- Byte index of start of channel definition #2
		...

		Each channel then consists of:
		[0:1] -- Byte index of name of channel string
		[2] -- Size of samples in bits (actual storage space are upper-bit padded full bytes)
		[3:4] -- Byte index of physical units string
		[5:6] -- Byte index of comments string start
		[7:8] -- Byte index of comments string end (X)
		[9:X] -- Strings

		Channel definitions are in sequance right after each other, and so [X+1] marks the start of the next channel definition (if not the last channel).

	File definitions:
		[0:1] -- Byte index of start of file #0
		[2:3] -- Byte index of start of file #1
		[4:5] -- Byte index of start of file #2
		...

		Each file then consists of:
		[0:1] -- Byte index of file name string start
		[2:3] -- Byte index of file name string end (X)
		[4:11] -- Start frame index
		[12:19] -- End frame index (inclusive)
		[20:X] -- File name string


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

	If compression is used, the entire data block, except padding bytes, are decompressed first.

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

	If compression is used, the entire data block, except padding bytes, are decompressed first.

	Annotations


"""

import copy
import datetime
import json
import mmap
import os.path
import struct

import funpack

from .bits import bitfield
from .compress import WIFFCompress

DATE_FMT = "%Y%m%d %H%M%S.%f"
WIFF_VERSION = 1
ENDIAN = funpack.Endianness.Little

class WIFF:
	def __init__(self, fname, props=None):
		self._files = {}
		self._chunks = {}

		if os.path.exists(fname):
			self._open_existing(fname)
		else:
			self._open_new(fname, props)

	@property
	def fs(self): return self._props['fs']
	@fs.setter
	def fs(self, v): self._props['fs'] = v

	@property
	def start(self): return self._props['start']
	@start.setter
	def start(self, v): self._props['start'] = v

	@property
	def end(self): return self._props['end']
	@end.setter
	def end(self, v): self._props['end'] = v

	@property
	def description(self): return self._props['description']
	@description.setter
	def description(self, v): self._props['description'] = v

	@property
	def num_frames(self): return self._props['num_frames']

	@property
	def channels(self):
		return WIFF_channels(self._props['channels'])

	@property
	def files(self):
		return copy.deepcopy(self._props['files'])

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
		self._files.clear()
		self._chunks.clear()

		self._chunks[fname] = []

		# Wrap file
		f = self._files[fname] = _filewrap(fname)
		# Have to put something there as mmap cannot map an empty file
		f[0:8] = 'WIFFINFO'.encode('ascii')

		# Declare WIFFINO at the start of the file
		c = WIFF_chunk(f, 0)

		datoff = c.getoffset('data')

		start = props['start'].strftime(DATE_FMT)
		end = props['end'].strftime(DATE_FMT)
		num_frames = 0

		props['files'].append({
			'name': fname,
			'fidx_start': 0,
			'fidx_end': 0,
		})

		w = WIFFINFO(f, c, datoff)
		# Create the chunk and a header
		w.initchunk()
		w.initheader(start,end, props['description'], props['fs'], num_frames, props['channels'], props['files'])

		self._chunks[fname] = [w]

	def _open_existing(self, fname):
		# Blank all files
		self._files.clear()
		self._chunks.clear()
		self._chunks[fname] = []

		# Wrap file
		f = self._files[fname] = _filewrap(fname)

		chunks = _WIFF_file.FindChunks(f.f)
		for chunk in chunks:
			c = WIFF_chunk(f, chunk['offset header'])
			if chunk['magic'] == 'WIFFINFO':
				w = WIFFINFO(f, c, chunk['offset data'])
				self._chunks[fname].append(w)
			else:
				raise TypeError('Uknown chunk magic: %s' % chunk['magic'])

	# -----------------------------------------------
	# -----------------------------------------------
	# Add data

	def set_file(self, fname):
		self._current_file = fname
		self._current_segment = None

	def set_segment(self, segmentid):
		raise NotImplementedError

	def new_file(self, fname):
		raise NotImplementedError

	def new_segment(self, *chans, segmentid=None):
		if self._current_file is None:
			raise ValueError("Must set active file before creating a new segment")

		# Blank current segment pointer
		self._current_segment = None

		# Auto-generated segment ID's
		if segmentid is None:
			raise NotImplementedError("Pick an available segmentid")

		# No segments, this is the first
		if not len(self._segments):
			s = {
				'magic': "WIFFWAVE",
				'size': None,
				'_attrs': None, # Generate from attrs
				'attrs': {
					'compression': None,
					'segmentid': segmentid,
				},
				'channels': tuple(sorted([_.index for _ in chans])),
				'fidx_start': self.num_frames,
				'fidx_end': self.num_frames,
			}
			self._segments[segmentid] = s
			self._current_segment = segmentid

			# Create chunk for frames
			dat = _WIFFWAVE.Ser(None, segmentid, channels, self.num_frames, self.num_frames)

			# Alter the file
			_WIFF_file.AddChunk(self._current_file, dat)


		else:
			raise NotImplementedError

		

	def add_frame(self, *samps):
		raise NotImplementedError

	# -----------------------------------------------
	# -----------------------------------------------
	# Dump

	def dumps_dict(self):
		"""
		Dump WIFF meta data into a dict() for handling within Python.
		"""
		ret = {
			'start': self.start,
			'end': self.end,
			'description': self.description,
			'fs': self.fs,
			'num_frames': self.num_frames,
			'channels': [],
			'files': [],
			'segments': [],
		}

		for i in range(len(self.channels)):
			c = self.channels[i]
			ret['channels'].append({
				'idx': i,
				'name': c.name,
				'bit': c.bit,
				'unit': c.unit,
				'comment': c.comment,
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
		ret.append("")
		for c in d['channels']:
			ret.append("%20s %d" % ('Channel', c['idx']))
			ret.append("%25s | %s" % ('Name', c['name']))
			ret.append("%25s | %s" % ('Bit', c['bit']))
			ret.append("%25s | %s" % ('Unit', c['unit']))
			ret.append("%25s | %s" % ('Comment', c['comment']))

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
	def __init__(self, fname):
		if not os.path.exists(fname):
			f = open(fname, 'wb')
			f.write(b'0')
			f.close()

		self.fname = fname
		self.f = open(fname, 'r+b')
		self.mmap = mmap.mmap(self.f.fileno(), 0)
		self.size = os.path.getsize(fname)

	def __getitem__(self, k):
		return self.mmap[k]

	def __setitem__(self, k,v):
		# Resize map and file upward as needed
		if isinstance(k, slice):
			if k.stop > self.size:
				self.mmap.resize(k.stop)
				self.size = os.path.getsize(self.fname)
		else:
			if k > self.size:
				self.mmap.resize(k)
				self.size = os.path.getsize(self.fname)

		self.mmap[k] = v

class WIFF_channels:
	"""
	Simple wrapper class to the channels.
	Implements the item getter pattern that returns WIFF_channel instances that then
	 permits getting and setting channel properties.
	"""

	def __init__(self, channels):
		self._channels = channels

	def __getitem__(self, idx):
		# Throw error if bad index
		if type(idx) == slice:
			items = self._channels[idx]
			return [WIFF_channel(item['index'], self._channels) for item in items]
		else:
			x = self._channels[idx]
			return WIFF_channel(idx, self._channels)

	def __len__(self):
		return len(self._channels)

	def __repr__(self):
		return "<WIFF_channels count=%d>" % len(self)

class WIFF_channel:
	"""
	Simple wrapper around channel dictionary.
	Permits getting and setting channel properties.
	"""

	def __init__(self, index, channels):
		self._index = index
		self._channels = channels

	def __repr__(self):
		return "<WIFF_channel i=%d name='%s' bit=%d unit='%s' comment='%s'>" % (self._index, self.name, self.bit, self.unit, self.comment)

	@property
	def index(self): return self._index

	@property
	def name(self): return self._channels[self._index]['name']
	@name.setter
	def name(self, v): self._channels[self._index]['name'] = v

	@property
	def bit(self): return self._channels[self._index]['bit']
	@bit.setter
	def bit(self, v): self._channels[self._index]['bit'] = v

	@property
	def unit(self): return self._channels[self._index]['unit']
	@unit.setter
	def unit(self, v): self._channels[self._index]['unit'] = v

	@property
	def comment(self): return self._channels[self._index]['comment']
	@comment.setter
	def comment(self, v): self._channels[self._index]['comment'] = v



class _WIFF_file:
	@classmethod
	def FindChunks(cls, f):
		sz = os.path.getsize(f.name)

		chunks = []

		off = 0
		while off < sz:
			f.seek(off)
			head = f.read(24)
			p = cls.DeSer(head)

			# Include offsets
			p['offset header'] = off
			p['offset data'] = off + 24

			chunks.append(p)
			off += p['size'] + 24 # Add header size

		return chunks

	@classmethod
	def Ser(cls, magic, size, attrs):
		fp = funpack.fpack(endian=funpack.Endianness.Little)
		fp.string_ascii(magic)
		fp.u64(size)
		fp.u8(*attrs)

		return fp.Data

	@classmethod
	def DeSer(cls, dat):
		fup = funpack.funpack(dat, endian=funpack.Endianness.Little)

		magic = fup.string_ascii(8)
		size = fup.u64()
		attrs = fup.u8(8)

		return {'magic': magic, 'size': size, 'attrs': attrs}

class WIFF_chunk:
	def __init__(self, fw, offset):
		self.fw = fw
		self.offset = offset

	def getoffset(self, k):
		return self.offset + self.getreloffset(k)

	def getreloffset(self, k):
		if k == 'magic':
			return 0
		elif k == 'size':
			return 8
		elif k == 'attributes':
			return 16
		elif k == 'data':
			return 24
		else:
			raise ValueError("Unrecognized offset key '%s'" % k)

	@property
	def magic(self):
		of = self.getoffset('magic')
		return self.fw[of:of+8]
	@magic.setter
	def magic(self, v):
		of = self.getoffset('magic')
		self.fw[of:of+8] = v

	@property
	def size(self):
		of = self.getoffset('size')
		return self.fw[of:of+8]
	@size.setter
	def size(self, v):
		of = self.getoffset('size')

		if isinstance(v, bytes):
			self.fw[of:of+8] = v
		elif isinstance(v, int):
			self.fw[of:of+8] = struct.pack("<Q", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def attributes(self):
		of = self.getoffset('attributes')
		return self.fw[of:of+8]
	@size.setter
	def attributes(self, v):
		of = self.getoffset('attributes')

		if isinstance(v, bytes):
			self.fw[of:of+8] = v
		elif isinstance(v, int):
			self.fw[of:of+8] = struct.pack("<Q", v)
		elif isinstance(v, tuple):
			self.fw[of:of+8] = struct.pack("<BBBBBBBB", *v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))


class WIFFINFO:
	def __init__(self, fw, chunk, offset):
		"""
		Manage a WIFFINFO chunk using the _filewrap object @fw.
		Supply the absolute offset @offset the chunk is located at in the file.
		All operations are using an mmap and there is no caching.
		"""
		self.fw = fw
		self.chunk = chunk
		self.offset = offset

	def getoffset(self, k):
		"""
		Gets the absolute offset of the field within the file.
		Call getreloffset() to get the relative offset within a chunk.
		"""
		return self.offset + self.getreloffset(k)
	def getreloffset(self, k):
		"""
		Important function that controls the offsets of fields within the file.
		Often has to do indirect look up as well.
		All returned values are relative to within the chunk.
		Call getoffset() to add the absolute offset of the chunk within a file
		 to get somethin that can be used in the mmap object.
		"""

		if k == 'index start':
			return 0
		elif k == 'index end':
			return 2
		elif k == 'index description':
			return 4
		elif k == 'index channels':
			return 6
		elif k == 'index files start':
			return 8
		elif k == 'index files end':
			return 10
		elif k == 'fs':
			return 12
		elif k == 'num channels':
			return 14
		elif k == 'num files':
			return 16
		elif k == 'num frames':
			return 18

		elif k.startswith('index channel '):
			parts = k.split(' ')

			if len(parts) == 3:
				# k in ("index channel 1", "index channel 2" ... "index channel 255")
				of = self.index_channels

				# Get index (1,2,3.....255)
				cnum = int(parts[2])

				# Offset of the index for the channel definition
				return of + 2*cnum
			else:
				of = self.getreloffset('channel %s' % parts[2])

				if parts[3] == 'name':
					return of
				elif parts[3] == 'bit':
					return of+2
				elif parts[3] == 'unit':
					return of+3
				elif parts[3] == 'comment':
					if parts[4] == 'start':
						return of+5
					elif parts[4] == 'end':
						return of+7
					else:
						raise ValueError("Unrecognized offset key '%s'" % k)
				else:
					raise ValueError("Unrecognized offset key '%s'" % k)

		elif k.startswith('channel '):
			of = self.getoffset('index ' + k)
			ret = struct.unpack("<H", self.fw[of:of+2])[0]
			return ret

		elif k.startswith('index file '):
			parts = k.split(' ')

			if len(parts) == 3:
				# k in ("index file 1", "index file 2" ... "index file 255")
				of = self.index_files_start

				# Get index (1,2,3.....255)
				cnum = int(k.split(' ')[2])

				return of + 2*cnum
			else:
				of = self.getreloffset('file %s' % parts[2])

				if parts[3] == 'name':
					if parts[4] == 'start':
						return of
					elif parts[4] == 'end':
						return of+2
					else:
						raise ValueError("Unrecognized offset key '%s'" % k)
				elif parts[3] == 'fidx':
					if parts[4] == 'start':
						return of+4
					elif parts[4] == 'end':
						return of+12
					else:
						raise ValueError("Unrecognized offset key '%s'" % k)
				else:
					raise ValueError("Unrecognized offset key '%s'" % k)

		elif k.startswith('file '):
			of = self.getoffset('index ' + k)
			ret = struct.unpack("<H", self.fw[of:of+2])[0]
			return ret

		elif k in ('start', 'end', 'description', 'channels', 'files'):
			of = self.getoffset('index ' + k)
			return struct.unpack("<H", self.fw[of:of+2])[0]
		else:
			raise ValueError("Unrecognized offset key '%s'" % k)

	def initchunk(self):
		self.chunk.magic = 'WIFFINFO'.encode('ascii')
		self.chunk.size = 4096
		self.chunk.attributes = (1,0,0,0, 0,0,0,0)

	def initheader(self, start, end, desc, fs, num_frames, channels, files):
		"""
		Initializes a new header
		This requires explicit initialization of all the byte indices.
		"""

		self.index_start = 26
		self.index_end = self.index_start + len(start)
		self.index_description = self.index_end + len(end)
		self.index_channels = self.index_description + len(desc)

		self.fs = fs
		self.num_frames = num_frames
		self.num_channels = len(channels)
		self.num_files = len(files)

		self.start = start
		self.end = end
		self.description = desc

		# This also sets the index_files_start because it depends on length of the channels
		self.initchannels(channels)

		# This also sets the indes_files_end
		self.initfiles(files)

		of_end = self.getreloffset('file %d name end' % (len(files)-1,))

		# Index is last char of the file name, so one more is the next unusued space
		of_end += 1

		# Number of bytes left for a 4k block
		padlen = 4096 - of_end

		if padlen > 0:
			# Now get absolute offset to pad
			of_end = self.getoffset('file %d name end' % (len(files)-1,))
			# Index is last char of the file name, so one more is the next unusued space
			of_end += 1
			self.fw[of_end:of_end+padlen] = b'\0'*padlen

	def initchannels(self, chans):
		# Get relative offset of the channels definition
		cd_of = self.index_channels
		ln = len(chans)

		# Length of the jump table (offset to first channel
		jt_ln = 2*ln

		prior_len = 0
		prior_off = cd_of + jt_ln
		for i in range(len(chans)):
			of = self.getoffset('index channel %d' % i)

			# Set channels definition jump table
			if i == 0:
				self.fw[of:of+2] = struct.pack("<H", cd_of + jt_ln)
				prior_off = cd_of + jt_ln
			else:
				self.fw[of:of+2] = struct.pack("<H", prior_off + prior_len)
				prior_off += prior_len

			c = chans[i]

			prior_len = self.initchannel(i, c['name'].encode('utf8'), c['bit'], c['unit'].encode('utf8'), c['comment'].encode('utf8'))

		self.index_files_start = prior_off + prior_len

	def initchannel(self, idx, name, bit, unit, comment):
		of = self.getoffset('channel %d' % idx)
		rel_of = self.getreloffset('channel %d' % idx)

		self.fw[of+0 :of+2] = struct.pack("<H", rel_of+9)
		self.fw[of+2 :of+3] = struct.pack("<B", bit)
		self.fw[of+3 :of+5] = struct.pack("<H", rel_of+9 + len(name))
		self.fw[of+5 :of+7] = struct.pack("<H", rel_of+9 + len(name) + len(unit))
		# -1 because it points to the last character, not the spot after
		self.fw[of+7 :of+9] = struct.pack("<H", rel_of+9 + len(name) + len(unit) + len(comment) -1)

		off = of+9
		self.fw[off:off+len(name)] = name
		off += len(name)
		self.fw[off:off+len(unit)] = unit
		off += len(unit)
		self.fw[off:off+len(comment)] = comment
		off += len(comment)

		ret = off - of
		return ret

	def initfiles(self, files):
		f_of = self.index_files_start
		ln = len(files)

		# Length of the jump table (offset to first file)
		jt_ln = 2*ln

		prior_len = 0
		prior_off = f_of + jt_ln
		for i in range(len(files)):
			of = self.getoffset('index file %d' % i)

			if i == 0:
				self.fw[of:of+2] = struct.pack("<H", f_of + jt_ln)
				prior_off = f_of + jt_ln
			else:
				self.fw[of:of+2] = struct.pack("<H", prior_off + jt_ln)
				prior_off += prior_len

			f = files[i]

			prior_len = self.initfile(i, f['name'].encode('utf8'), f['fidx_start'], f['fidx_end'])

		# -1 because it points to the last character, not the spot after
		self.index_files_end = prior_off + prior_len -1

	def initfile(self, idx, name, fidx_start, fidx_end):
		of = self.getoffset('file %d' % idx)
		rel_of = self.getreloffset('file %d' % idx)

		self.fw[of+0 :of+2] = struct.pack("<H", rel_of+20)
		# -1 because it points to the last character, not the spot after
		self.fw[of+2 :of+4] = struct.pack("<H", rel_of+20 + len(name) -1)
		self.fw[of+4 :of+12]= struct.pack("<Q", fidx_start)
		self.fw[of+12:of+20]= struct.pack("<Q", fidx_end)

		off = of+20
		self.fw[off:off+len(name)] = name
		off += len(name)

		ret = off - of
		return ret

	@property
	def index_start(self):
		of = self.getoffset('index start')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_start.setter
	def index_start(self, v):
		of = self.getoffset('index start')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def index_end(self):
		of = self.getoffset('index end')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_end.setter
	def index_end(self, v):
		of = self.getoffset('index end')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def index_description(self):
		of = self.getoffset('index description')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_description.setter
	def index_description(self, v):
		of = self.getoffset('index description')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def index_channels(self):
		of = self.getoffset('index channels')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_channels.setter
	def index_channels(self, v):
		of = self.getoffset('index channels')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def index_files_start(self):
		of = self.getoffset('index files start')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_files_start.setter
	def index_files_start(self, v):
		of = self.getoffset('index files start')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def index_files_end(self):
		of = self.getoffset('index files end')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@index_files_end.setter
	def index_files_end(self, v):
		of = self.getoffset('index files end')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def fs(self):
		of = self.getoffset('fs')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@fs.setter
	def fs(self, v):
		of = self.getoffset('fs')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def num_frames(self):
		of = self.getoffset('num frames')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@num_frames.setter
	def num_frames(self, v):
		of = self.getoffset('num frames')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def num_channels(self):
		of = self.getoffset('num channels')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@num_channels.setter
	def num_channels(self, v):
		of = self.getoffset('num channels')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

	@property
	def num_files(self):
		of = self.getoffset('num files')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@num_files.setter
	def num_files(self, v):
		of = self.getoffset('num files')
		if isinstance(v, bytes):
			self.fw[of:of+2] = v
		elif isinstance(v, int):
			self.fw[of:of+2] = struct.pack("<H", v)
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))


	@property
	def start(self):
		of = self.getoffset('start')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@start.setter
	def start(self, v):
		of_s = self.getoffset('start')
		of_e = self.getoffset('end')

		if isinstance(v, str):
			v = v.encode('ascii')
		elif isinstance(v, bytes):
			pass
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

		# Possiblities:
		# 1) New value is same length as old
		# 2) New value is smaller than old
		# 3) New value is larger than old

		curlen = of_e - of_s
		print(['curlen', of_e, of_s, curlen, len(v)])

		# (1)
		if curlen == len(v):
			self.fw[of_s:of_s+len(v)] = v
		else:
			raise NotImplementedError

	@property
	def end(self):
		of = self.getoffset('end')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@end.setter
	def end(self, v):
		of_e = self.getoffset('end')
		of_d = self.getoffset('description')

		if isinstance(v, str):
			v = v.encode('ascii')
		elif isinstance(v, bytes):
			pass
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

		# Possiblities:
		# 1) New value is same length as old
		# 2) New value is smaller than old
		# 3) New value is larger than old

		curlen = of_d - of_e
		print(['curlen', of_d, of_e, curlen, len(v)])

		# (1)
		if curlen == len(v):
			self.fw[of_e:of_e+len(v)] = v
		else:
			raise NotImplementedError

	@property
	def description(self):
		of = self.getoffset('description')
		return struct.unpack("<H", self.fw[of:of+2])[0]
	@description.setter
	def description(self, v):
		of_d = self.getoffset('description')
		of_cd = self.getoffset('channels')

		if isinstance(v, str):
			v = v.encode('ascii')
		elif isinstance(v, bytes):
			pass
		else:
			raise TypeError("Unsupported type: '%s'" % type(v))

		# Possiblities:
		# 1) New value is same length as old
		# 2) New value is smaller than old
		# 3) New value is larger than old

		curlen = of_cd - of_d
		print(['curlen', of_cd, of_d, curlen, len(v)])

		# (1)
		if curlen == len(v):
			self.fw[of_d:of_d+len(v)] = v
		else:
			raise NotImplementedError

	def channel_name(self, idx):
		of_start = self.getoffset('channel %d name' % idx)
		of_end = self.getoffset('channel %d unit' % idx)

		return self.fw[of_start:of_end].decode('utf8')

	def channel_bit(self, idx):
		of = self.getoffset('index channel %d bit' % idx)

		return self.fw[of]

	def channel_unit(self, idx):
		of_start = self.getoffset('channel %d unit' % idx)
		of_end = self.getoffset('channel %d comment start' % idx)

		return self.fw[of_start:of_end].decode('utf8')

	def channel_comment(self, idx):
		of_start = self.getoffset('channel %d comment start' % idx)
		of_end = self.getoffset('channel %d comment end' % idx)

		# end points to the last character, so must go 1 more
		return self.fw[of_start:of_end+1].decode('utf8')

	def file_name(self, idx):
		of_start = self.getoffset('file %d name start' % idx)
		of_end = self.getoffset('file %d name end' % idx)

		return self.fw[of_start:of_end].decode('utf8')

	def file_fidx_start(self, idx):
		of = self.getoffset('index file %d fidx start' % idx)
		return self.fw[of]

	def file_fidx_end(self, idx):
		of = self.getoffset('index file %d fidx end' % idx)
		return self.fw[of]

class WIFFWAVE:
	pass

